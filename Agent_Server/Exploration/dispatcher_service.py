from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .cache_service import ExplorationCacheService
from .task_service import ExplorationTaskService
from .strategy.session_state_machine import ExplorationSessionState, ExplorationSessionStateMachine

logger = logging.getLogger(__name__)


class ExplorationDispatcherService:
    """Server-side exploration dispatcher for session/page/task lifecycle."""

    def __init__(self, cache_service: Optional[ExplorationCacheService] = None):
        self.cache = cache_service or ExplorationCacheService()

    def start_exploration_session(
        self,
        session_id: str,
        entry_mode: str,
        goal: str,
        entry_url: str,
        session_ref: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "session_id": session_id,
            "entry_mode": entry_mode,
            "goal": goal,
            "entry_url": entry_url,
            "status": "created",
            "current_page_key": "",
            "engine_version": "v3",
            "created_at": int(time.time()),
            "visited_page_count": 0,
            "completed_task_count": 0,
            "failed_task_count": 0,
        }
        self.cache.start_session(session_id, payload)
        self.cache.append_session_artifact(
            session_id,
            {
                "kind": "session.started",
                "session_id": session_id,
                "entry_mode": entry_mode,
                "entry_url": entry_url,
                "goal": goal,
                "ts": int(time.time()),
            },
        )
        if entry_url:
            page_key = self._frontier_page_key(session_id, entry_url=entry_url)
            self.cache.append_frontier(
                session_id,
                {
                    "page_key": page_key,
                    "url": entry_url,
                    "depth": 0,
                    "enqueue_reason": "entry_page",
                    "status": "queued",
                },
            )
        if session_ref is not None:
            session_ref["exploration_session_id"] = session_id
        return {
            "session_id": session_id,
            "entry_page_key": self._frontier_page_key(session_id, entry_url=entry_url) if entry_url else "",
            "status": ExplorationSessionState.CREATED,
        }

    def register_page_scan(
        self,
        session_id: str,
        page_key: str,
        page_url: str,
        page_title: str,
        interactive_elements: List[Dict[str, Any]],
        dom_summary: Optional[Dict[str, Any]] = None,
        depth: int = 0,
    ) -> Dict[str, Any]:
        summary = dom_summary or {}
        page_summary = ExplorationTaskService.build_page_summary(page_key, interactive_elements, summary)
        generated_tasks = ExplorationTaskService.build_page_tasks(
            session_id=session_id,
            page_key=page_key,
            interactive_elements=interactive_elements,
            dom_summary=summary,
        )
        existing_tasks = self.cache.get_page_tasks(page_key)
        tasks = ExplorationTaskService.merge_page_tasks(existing_tasks, generated_tasks) if existing_tasks else generated_tasks
        task_summary = ExplorationTaskService.summarize_task_status(tasks)

        self.cache.add_session_page(session_id, page_key)
        self.cache.save_page_meta(
            page_key,
            {
                "page_key": page_key,
                "session_id": session_id,
                "url": page_url,
                "title": page_title,
                "depth": depth,
                "status": "scanned",
                "page_summary": page_summary,
                "scanned_at": int(time.time()),
            },
        )
        self.cache.save_page_scan(
            page_key,
            {
                "page_key": page_key,
                "page_id": page_key.split(":", 1)[-1],
                "title": page_title,
                "url": page_url,
                "interactive_elements": interactive_elements,
                "forms": summary.get("forms") or [],
                "tables": summary.get("tables") or [],
                "dialogs": summary.get("dialogs") or [],
                "page_sections": summary.get("page_sections") or [],
                "page_summary": page_summary,
            },
        )
        self.cache.save_page_tasks(page_key, tasks)
        self.cache.update_session(
            session_id,
            {
                **ExplorationSessionStateMachine.page_scanned(page_key),
                "visited_page_count": len(self.cache.list_session_pages(session_id)),
            },
        )
        self.cache.update_frontier_entry(
            session_id,
            page_key,
            {
                "url": page_url,
                "title": page_title,
                "depth": depth,
                "status": "scanned",
            },
        )
        self.cache.append_page_artifact(
            page_key,
            {
                "kind": "page.scanned",
                "page_key": page_key,
                "url": page_url,
                "title": page_title,
                "buttons": [self._label_from_interactive(item) for item in interactive_elements if self._is_button_like(item)],
                "links": [self._label_from_interactive(item) for item in interactive_elements if self._is_link_like(item)],
                "dynamic_elements": summary.get("dialogs") or [],
                "page_sections": summary.get("page_sections") or [],
                "page_summary": page_summary,
                "task_status_summary": task_summary,
            },
        )
        self.cache.append_session_artifact(
            session_id,
            {
                "kind": "tasks.generated",
                "session_id": session_id,
                "page_key": page_key,
                "url": page_url,
                "depth": depth,
                "in_page_tasks": sum(1 for task in tasks if task.get("task_group") == "in_page"),
                "navigation_tasks": sum(1 for task in tasks if task.get("task_group") == "navigation"),
                "task_total": len(tasks),
                "ts": int(time.time()),
            },
        )
        logger.info(
            "[ExplorationDispatcher] page.scanned session_id=%s page_key=%s in_page_tasks=%s navigation_tasks=%s reused_tasks=%s",
            session_id,
            page_key,
            sum(1 for task in tasks if task.get("task_group") == "in_page"),
            sum(1 for task in tasks if task.get("task_group") == "navigation"),
            sum(1 for task in tasks if str(task.get("status") or "") in ExplorationTaskService.TERMINAL_TASK_STATUSES),
        )
        return {
            "page_status": "scanned",
            "task_count": len(tasks),
            "in_page_count": sum(1 for task in tasks if task.get("task_group") == "in_page"),
            "navigation_count": sum(1 for task in tasks if task.get("task_group") == "navigation"),
            "tasks": tasks,
            "page_summary": page_summary,
            "task_status_summary": task_summary,
        }

    def dispatch_next_task(self, session_id: str, page_key: str) -> Dict[str, Any]:
        if not self.can_dispatch_next_task(session_id, page_key):
            status = self.get_session_status(session_id)
            self.cache.append_session_artifact(
                session_id,
                {
                    "kind": "dispatch.blocked",
                    "session_id": session_id,
                    "page_key": page_key,
                    "status": status,
                    "ts": int(time.time()),
                },
            )
            return {
                "success": False,
                "message": f"session is not ready for dispatch while status={status}",
                "session_status": status,
            }

        tasks = self.cache.get_page_tasks(page_key)
        next_task = self._select_next_task(tasks)
        if not next_task:
            self.cache.append_session_artifact(
                session_id,
                {
                    "kind": "dispatch.idle",
                    "session_id": session_id,
                    "page_key": page_key,
                    "status": self.get_session_status(session_id),
                    "ts": int(time.time()),
                },
            )
            return {
                "success": True,
                "has_task": False,
                "message": "no pending task",
                "session_status": self.get_session_status(session_id),
            }

        if str(next_task.get("status") or "") != "running":
            ExplorationTaskService.update_task_status(tasks, next_task["task_id"], "running")
            self.cache.save_page_tasks(page_key, tasks)
            next_task = next((item for item in tasks if item.get("task_id") == next_task["task_id"]), next_task)

        page_meta = self.cache.get_page_meta(page_key)
        if page_meta:
            page_meta["status"] = "running"
            self.cache.save_page_meta(page_key, page_meta)
            self.cache.update_frontier_entry(session_id, page_key, {"status": "running"})

        self.cache.update_session(session_id, ExplorationSessionStateMachine.task_running(page_key))
        next_task = dict(next_task)
        if next_task.get("is_validation_task"):
            next_task["completion_hint"] = (
                "This is a validation task. Execute only this task, verify the expected effect, restore the previous "
                "session/context when required, then report_task_artifact() immediately with validation_passed, "
                "session_restored, resume_note, before_state, after_state, and evidence. Do not rescan the page or "
                "enqueue a new page for this task."
            )
        else:
            next_task["completion_hint"] = (
                "Execute only this task, validate effect_type, then report_task_artifact() with before_state, "
                "after_state, executed_target, validation_status, evidence, and navigation fields when applicable."
            )

        self.cache.append_session_artifact(
            session_id,
            {
                "kind": "task.assigned",
                "session_id": session_id,
                "page_key": page_key,
                "task_id": next_task.get("task_id", ""),
                "task_group": next_task.get("task_group", ""),
                "task_type": next_task.get("task_type", ""),
                "task_goal": next_task.get("task_goal", ""),
                "is_validation_task": bool(next_task.get("is_validation_task")),
                "attempt_count": next_task.get("attempt_count", 0),
                "ts": int(time.time()),
            },
        )
        logger.info(
            "[ExplorationDispatcher] task.assigned session_id=%s page_key=%s task_id=%s task_group=%s task_type=%s validation=%s",
            session_id,
            page_key,
            next_task.get("task_id", ""),
            next_task.get("task_group", ""),
            next_task.get("task_type", ""),
            bool(next_task.get("is_validation_task")),
        )
        return {
            "success": True,
            "has_task": True,
            "task": next_task,
            "session_status": self.get_session_status(session_id),
        }

    def get_session_status(self, session_id: str) -> str:
        return str(self.cache.get_session(session_id).get("status") or "")

    def can_record_page(self, session_id: str, page_key: str = "") -> bool:
        status = self.get_session_status(session_id)
        if status in {
            ExplorationSessionState.VALIDATION_RESTORING,
            ExplorationSessionState.SESSION_COMPLETED,
            ExplorationSessionState.FAILED,
            ExplorationSessionState.CANCELLED,
        }:
            logger.info(
                "[ExplorationDispatcher] record_page.blocked session_id=%s page_key=%s status=%s",
                session_id,
                page_key,
                status,
            )
            return False
        return True

    def can_dispatch_next_task(self, session_id: str, page_key: str = "") -> bool:
        status = self.get_session_status(session_id)
        if status in {
            ExplorationSessionState.VALIDATION_RESTORING,
            ExplorationSessionState.SESSION_COMPLETED,
            ExplorationSessionState.FAILED,
            ExplorationSessionState.CANCELLED,
        }:
            logger.info(
                "[ExplorationDispatcher] dispatch.blocked session_id=%s page_key=%s status=%s",
                session_id,
                page_key,
                status,
            )
            return False
        return True

    def accept_task_result(
        self,
        session_id: str,
        page_key: str,
        task_id: str,
        task_group: str,
        artifact: Dict[str, Any],
    ) -> Dict[str, Any]:
        tasks = self.cache.get_page_tasks(page_key)
        target_task = next((task for task in tasks if task.get("task_id") == task_id), None)
        if target_task is None:
            self.cache.append_session_artifact(
                session_id,
                {
                    "kind": "task.result_rejected",
                    "session_id": session_id,
                    "page_key": page_key,
                    "task_id": task_id,
                    "reason": "task_not_found",
                    "ts": int(time.time()),
                },
            )
            return {"success": False, "message": f"task not found: {task_id}"}

        effect_type = self._normalize_effect_type(artifact.get("effect_type"))
        artifact["effect_type"] = effect_type
        is_validation_task = bool(target_task.get("is_validation_task") or artifact.get("is_validation_task"))
        artifact["is_validation_task"] = is_validation_task
        artifact.setdefault("validation_goal", target_task.get("validation_goal", ""))
        artifact.setdefault("validation_success_signals", target_task.get("validation_success_signals", []))
        artifact["skip_rescan_after_execute"] = bool(
            artifact.get("skip_rescan_after_execute") or target_task.get("skip_rescan_after_execute")
        )
        validation_passed, session_restored = self._resolve_validation_task_outcome(page_key, target_task, artifact, effect_type)
        artifact["validation_passed"] = validation_passed
        artifact["session_restored"] = session_restored
        validation_status = self._normalize_validation_status(artifact, effect_type)
        if is_validation_task:
            validation_status = self._normalize_validation_task_status(
                target_task,
                artifact,
                effect_type,
                validation_status,
            )
        artifact["validation_status"] = validation_status
        resolved_status = self._resolve_task_status(target_task, validation_status, effect_type)
        artifact["status"] = resolved_status

        ExplorationTaskService.update_task_status(tasks, task_id, resolved_status, artifact)
        self.cache.save_page_tasks(page_key, tasks)
        self.cache.save_task_result(
            task_id,
            {
                "task_id": task_id,
                "page_key": page_key,
                "task_group": task_group,
                "artifact": artifact,
                "status": resolved_status,
                "effect_type": effect_type,
            },
        )

        self.cache.append_page_artifact(
            page_key,
            {
                "kind": "task_artifact",
                "task_id": task_id,
                "task_group": task_group,
                "page_key": page_key,
                "buttons": artifact.get("buttons", []),
                "links": artifact.get("links", []),
                "dynamic_elements": artifact.get("dynamic_elements", []),
                "page_sections": artifact.get("page_sections", []),
                "artifact": artifact,
            },
        )
        self.cache.append_session_artifact(
            session_id,
            {
                "kind": "action.validated",
                "session_id": session_id,
                "page_key": page_key,
                "task_id": task_id,
                "task_group": task_group,
                "validation_status": validation_status,
                "effect_type": effect_type,
                "is_validation_task": is_validation_task,
                "validation_passed": validation_passed,
                "session_restored": session_restored,
                "executed_target": artifact.get("executed_target", {}),
                "ts": int(time.time()),
            },
        )

        session_patch = {}
        if resolved_status == "accepted":
            session_patch["completed_task_count"] = int(self.cache.get_session(session_id).get("completed_task_count", 0)) + 1
        elif resolved_status == "failed":
            session_patch["failed_task_count"] = int(self.cache.get_session(session_id).get("failed_task_count", 0)) + 1
        if session_patch:
            self.cache.update_session(session_id, session_patch)

        if is_validation_task and resolved_status == "retry_pending" and not session_restored:
            self.cache.update_session(session_id, ExplorationSessionStateMachine.validation_restoring(page_key))
            self.cache.append_session_artifact(
                session_id,
                {
                    "kind": "validation.restoring",
                    "session_id": session_id,
                    "page_key": page_key,
                    "task_id": task_id,
                    "ts": int(time.time()),
                },
            )
        elif resolved_status in {"accepted", "retry_pending", "skipped"}:
            self.cache.update_session(session_id, ExplorationSessionStateMachine.ready_for_next_task(page_key))
            self.cache.append_session_artifact(
                session_id,
                {
                    "kind": "session.ready_for_next_task",
                    "session_id": session_id,
                    "page_key": page_key,
                    "task_id": task_id,
                    "task_status": resolved_status,
                    "ts": int(time.time()),
                },
            )

        if is_validation_task and resolved_status == "accepted":
            self.cache.append_session_artifact(
                session_id,
                {
                    "kind": "validation.committed",
                    "session_id": session_id,
                    "page_key": page_key,
                    "task_id": task_id,
                    "validation_passed": validation_passed,
                    "session_restored": session_restored,
                    "ts": int(time.time()),
                },
            )

        if resolved_status == "retry_pending":
            self.cache.append_session_artifact(
                session_id,
                {
                    "kind": "task.replanned",
                    "session_id": session_id,
                    "page_key": page_key,
                    "task_id": task_id,
                    "effect_type": effect_type,
                    "forbidden_targets": target_task.get("forbidden_targets", []),
                    "ts": int(time.time()),
                },
            )

        new_page_key = ""
        navigation_detected = (bool(artifact.get("navigated")) or effect_type == "navigation_detected") and not is_validation_task
        if navigation_detected:
            enqueue_result = self.enqueue_navigation_page(
                session_id=session_id,
                source_page_key=page_key,
                task_id=task_id,
                new_url=str(artifact.get("new_url") or ""),
                target_page_name=str(artifact.get("target_page_name") or ""),
                depth=int(self.cache.get_page_meta(page_key).get("depth", 0)) + 1,
            )
            new_page_key = enqueue_result.get("page_key", "")

        finalize = self.finalize_page_if_ready(session_id, page_key)
        logger.info(
            "[ExplorationDispatcher] action.validated session_id=%s page_key=%s task_id=%s effect=%s status=%s validation=%s restored=%s enqueue=%s complete=%s",
            session_id,
            page_key,
            task_id,
            effect_type,
            resolved_status,
            is_validation_task,
            session_restored,
            bool(new_page_key),
            bool(finalize.get("completed")),
        )
        return {
            "success": True,
            "task_status": resolved_status,
            "validation_status": validation_status,
            "effect_type": effect_type,
            "page_status": finalize.get("page_status", "running"),
            "navigation_detected": navigation_detected,
            "new_page_key": new_page_key,
            "page_completed": bool(finalize.get("completed")),
            "is_validation_task": is_validation_task,
            "validation_passed": validation_passed,
            "session_restored": session_restored,
            "session_status": self.get_session_status(session_id),
        }

    def enqueue_navigation_page(
        self,
        session_id: str,
        source_page_key: str,
        task_id: str,
        new_url: str = "",
        target_page_name: str = "",
        depth: int = 0,
    ) -> Dict[str, Any]:
        derived_page_key = self._frontier_page_key(session_id, entry_url=new_url, target_page_name=target_page_name)
        frontier = self.cache.list_frontier(session_id)
        for item in frontier:
            if str(item.get("page_key") or "") == derived_page_key:
                return {"enqueued": False, "page_key": derived_page_key, "reason": "duplicate_page_key"}
            if new_url and str(item.get("url") or "").strip() == new_url.strip():
                return {"enqueued": False, "page_key": derived_page_key, "reason": "duplicate_url"}

        payload = {
            "source_page_key": source_page_key,
            "target_page_name": target_page_name,
            "new_url": new_url,
            "task_id": task_id,
            "ts": int(time.time()),
        }
        self.cache.append_navigation(session_id, payload)
        self.cache.append_frontier(
            session_id,
            {
                "page_key": derived_page_key,
                "url": new_url,
                "depth": depth,
                "enqueue_reason": "navigation_task",
                "trigger_task_id": task_id,
                "source_page_key": source_page_key,
                "status": "queued",
            },
        )
        self.cache.append_session_artifact(
            session_id,
            {
                "kind": "navigation.enqueued",
                "session_id": session_id,
                "page_key": source_page_key,
                "task_id": task_id,
                "new_page_key": derived_page_key,
                "new_url": new_url,
                "depth": depth,
                "ts": int(time.time()),
            },
        )
        logger.info(
            "[ExplorationDispatcher] navigation.enqueued session_id=%s source_page_key=%s task_id=%s new_page_key=%s",
            session_id,
            source_page_key,
            task_id,
            derived_page_key,
        )
        return {"enqueued": True, "page_key": derived_page_key, "reason": "queued"}

    def finalize_page_if_ready(self, session_id: str, page_key: str) -> Dict[str, Any]:
        tasks = self.cache.get_page_tasks(page_key)
        task_summary = ExplorationTaskService.summarize_task_status(tasks)
        completed = ExplorationTaskService.is_page_completed(tasks)

        page_meta = self.cache.get_page_meta(page_key)
        if page_meta:
            page_meta["status"] = "completed" if completed else ("running" if tasks else "scanned")
            page_meta["task_status_summary"] = task_summary
            self.cache.save_page_meta(page_key, page_meta)
            self.cache.update_frontier_entry(session_id, page_key, {"status": page_meta["status"]})

        if completed:
            self.cache.update_session(session_id, ExplorationSessionStateMachine.page_completed(page_key))
            self.cache.append_session_artifact(
                session_id,
                {
                    "kind": "page.completed",
                    "session_id": session_id,
                    "page_key": page_key,
                    "task_status_summary": task_summary,
                    "ts": int(time.time()),
                },
            )
            logger.info(
                "[ExplorationDispatcher] page.completed session_id=%s page_key=%s pending=%s navigation=%s",
                session_id,
                page_key,
                task_summary.get("pending", 0) + task_summary.get("retry_pending", 0),
                sum(1 for task in tasks if task.get("task_group") == "navigation" and task.get("status") not in ExplorationTaskService.TERMINAL_TASK_STATUSES),
            )

        return {
            "completed": completed,
            "page_status": (page_meta or {}).get("status", "running"),
            "pending_tasks": task_summary.get("pending", 0) + task_summary.get("running", 0) + task_summary.get("retry_pending", 0),
            "pending_navigation": sum(
                1
                for task in tasks
                if task.get("task_group") == "navigation"
                and task.get("status") not in ExplorationTaskService.TERMINAL_TASK_STATUSES
            ),
        }

    def pop_next_page(self, session_id: str) -> Dict[str, Any]:
        frontier = self.cache.list_frontier(session_id)
        for item in frontier:
            if str(item.get("status") or "") != "queued":
                continue
            page_key = str(item.get("page_key") or "")
            item["status"] = "scanning"
            self.cache.save_frontier(session_id, frontier)
            page_meta = self.cache.get_page_meta(page_key)
            if page_meta:
                page_meta["status"] = "scanning"
                self.cache.save_page_meta(page_key, page_meta)
            self.cache.update_session(session_id, ExplorationSessionStateMachine.started(page_key))
            return {"success": True, "has_page": True, "page": item}
        return {"success": True, "has_page": False, "message": "no queued page"}

    def finalize_session_if_ready(self, session_id: str) -> Dict[str, Any]:
        snapshot = self.get_session_snapshot(session_id)
        frontier = list(snapshot.get("frontier_preview") or [])
        all_frontier = self.cache.list_frontier(session_id)
        pages = list(snapshot.get("pages") or [])

        pending_frontier = sum(
            1 for item in all_frontier
            if str(item.get("status") or "") in {"queued", "scanning", "running", "scanned"}
        )
        pending_page_tasks = sum(
            int(page.get("task_status_summary", {}).get("pending", 0))
            + int(page.get("task_status_summary", {}).get("running", 0))
            + int(page.get("task_status_summary", {}).get("retry_pending", 0))
            for page in pages
        )
        completed = pending_frontier == 0 and pending_page_tasks == 0 and bool(pages)
        if completed:
            self.cache.update_session(session_id, ExplorationSessionStateMachine.session_completed())
            self.cache.append_session_artifact(
                session_id,
                {
                    "kind": "session.completed",
                    "session_id": session_id,
                    "ts": int(time.time()),
                },
            )
            snapshot = self.get_session_snapshot(session_id)
        return {
            "completed": completed,
            "pending_frontier": pending_frontier,
            "pending_page_tasks": pending_page_tasks,
            "snapshot": snapshot,
            "frontier_preview": frontier,
        }

    def cleanup_session_cache(self, session_id: str):
        self.cache.cleanup_session(session_id)

    def get_session_snapshot(self, session_id: str) -> Dict[str, Any]:
        session_meta = self.cache.get_session(session_id)
        frontier = self.cache.list_frontier(session_id)
        navigation = self.cache.list_navigation(session_id)
        page_keys = self.cache.list_session_pages(session_id)
        session_artifacts = self.cache.list_session_artifacts(session_id)

        pages: List[Dict[str, Any]] = []
        for page_key in page_keys:
            meta = self.cache.get_page_meta(page_key)
            scan = self.cache.get_page_scan(page_key)
            tasks = self.cache.get_page_tasks(page_key)
            task_summary = ExplorationTaskService.summarize_task_status(tasks)
            pages.append(
                {
                    "page_key": page_key,
                    "meta": meta,
                    "scan_summary": scan.get("page_summary", {}),
                    "task_total": len(tasks),
                    "task_status_summary": task_summary,
                    "next_pending_tasks": [
                        {
                            "task_id": task.get("task_id", ""),
                            "task_group": task.get("task_group", ""),
                            "task_type": task.get("task_type", ""),
                            "task_goal": task.get("task_goal", ""),
                            "element_label": task.get("element_label", ""),
                            "is_validation_task": bool(task.get("is_validation_task")),
                        }
                        for task in tasks
                        if task.get("status") in {"pending", "retry_pending"}
                    ][:5],
                }
            )

        current_page_key = str(session_meta.get("current_page_key") or "")
        current_page = next((page for page in pages if page.get("page_key") == current_page_key), {})
        return {
            "session": session_meta,
            "frontier_size": len(frontier),
            "frontier_preview": frontier[:10],
            "navigation_count": len(navigation),
            "navigation_preview": navigation[:10],
            "page_count": len(pages),
            "pages": pages,
            "current_page": current_page,
            "artifact_count": len(session_artifacts),
            "artifact_preview": session_artifacts[-15:],
        }

    @staticmethod
    def _select_next_task(tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for task in tasks:
            if task.get("status") == "running":
                return dict(task)
        for group in ("in_page", "navigation"):
            for status in ("retry_pending", "pending"):
                for task in tasks:
                    if task.get("task_group") == group and task.get("status") == status:
                        return dict(task)
        return None

    @staticmethod
    def _normalize_effect_type(effect_type: Any) -> str:
        normalized = str(effect_type or "").strip().lower()
        if normalized in ExplorationTaskService.EFFECT_TYPES:
            return normalized
        return "state_changed" if normalized else "failed"

    @staticmethod
    def _normalize_validation_status(artifact: Dict[str, Any], effect_type: str) -> str:
        raw = str(artifact.get("validation_status") or artifact.get("status") or "").strip().lower()
        if raw in {"accepted", "retry_pending", "failed", "skipped"}:
            return raw
        if effect_type in {"wrong_target", "no_effect"}:
            return "retry_pending"
        if effect_type == "failed":
            return "failed"
        return "accepted"

    @staticmethod
    def _resolve_task_status(task: Dict[str, Any], validation_status: str, effect_type: str) -> str:
        if validation_status != "retry_pending":
            return validation_status
        attempt_count = int(task.get("attempt_count", 0))
        max_attempts = int(task.get("max_attempts", 2))
        if attempt_count >= max_attempts:
            return "failed"
        if effect_type in {"wrong_target", "no_effect", "partial_success"}:
            return "retry_pending"
        return validation_status

    def _resolve_validation_task_outcome(
        self,
        page_key: str,
        task: Dict[str, Any],
        artifact: Dict[str, Any],
        effect_type: str,
    ) -> tuple[bool, bool]:
        raw_validation_passed = bool(artifact.get("validation_passed"))
        raw_session_restored = bool(artifact.get("session_restored"))
        raw_status = str(artifact.get("validation_status") or artifact.get("status") or "").strip().lower()
        requires_restore = bool(task.get("resume_after_validation"))
        runtime_state_available = bool(artifact.get("runtime_state_available"))
        runtime_current_url = str(artifact.get("runtime_current_url") or "").strip()
        runtime_login_form_present = bool(artifact.get("runtime_login_form_present"))
        submitted_new_url = str(artifact.get("new_url") or "").strip()
        expected_page_url = str(self.cache.get_page_meta(page_key).get("url") or "").strip()

        validation_passed = raw_validation_passed or raw_status == "accepted"
        if not validation_passed and effect_type not in {"wrong_target", "no_effect", "failed"}:
            validation_passed = True

        if not requires_restore:
            session_restored = True
        elif runtime_state_available:
            session_restored = False
            if runtime_current_url and not runtime_login_form_present:
                if expected_page_url and runtime_current_url == expected_page_url:
                    session_restored = True
                elif submitted_new_url and runtime_current_url != submitted_new_url:
                    session_restored = True
            session_restored = raw_session_restored and session_restored
        else:
            session_restored = False
        return validation_passed, session_restored

    @staticmethod
    def _normalize_validation_task_status(
        task: Dict[str, Any],
        artifact: Dict[str, Any],
        effect_type: str,
        current_status: str,
    ) -> str:
        validation_passed = bool(artifact.get("validation_passed"))
        session_restored = bool(artifact.get("session_restored"))
        requires_restore = bool(task.get("resume_after_validation"))
        runtime_state_available = bool(artifact.get("runtime_state_available"))

        if effect_type == "failed":
            return "failed"
        if effect_type in {"wrong_target", "no_effect"}:
            return "retry_pending"
        if not validation_passed:
            return "retry_pending"
        if requires_restore and not runtime_state_available:
            return "retry_pending"
        if requires_restore and not session_restored:
            return "retry_pending"
        return "accepted" if current_status != "skipped" else current_status

    @staticmethod
    def _label_from_interactive(item: Dict[str, Any]) -> str:
        return ExplorationTaskService.label_for_element(item)

    @staticmethod
    def _is_link_like(item: Dict[str, Any]) -> bool:
        tag = str(item.get("tag") or "").lower()
        role = str(item.get("role") or "").lower()
        href = str(item.get("href") or "").strip()
        return bool(href or tag == "a" or role == "link")

    @staticmethod
    def _is_button_like(item: Dict[str, Any]) -> bool:
        tag = str(item.get("tag") or "").lower()
        role = str(item.get("role") or "").lower()
        element_type = str(item.get("element_type") or "").lower()
        return bool(tag == "button" or role == "button" or element_type in {"button", "submit", "reset"})

    @staticmethod
    def _frontier_page_key(session_id: str, entry_url: str = "", target_page_name: str = "") -> str:
        base = (entry_url or target_page_name or "page").strip()
        safe = "".join(ch if ch.isalnum() else "_" for ch in base).strip("_") or "page"
        return f"{session_id}:{safe[:120]}"
