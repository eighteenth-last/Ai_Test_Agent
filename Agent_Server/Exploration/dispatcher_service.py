from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .cache_service import ExplorationCacheService
from .task_service import ExplorationTaskService

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
            "status": "running",
            "current_page_key": "",
            "engine_version": "v2",
        }
        self.cache.start_session(session_id, payload)
        if entry_url:
            self.cache.append_frontier(
                session_id,
                {
                    "page_key": self._frontier_page_key(session_id, entry_url=entry_url),
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
            "status": "running",
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
        tasks = ExplorationTaskService.build_page_tasks(session_id, page_key, interactive_elements)
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
            },
        )
        self.cache.save_page_tasks(page_key, tasks)
        self.cache.update_session(
            session_id,
            {
                "status": "running",
                "current_page_key": page_key,
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
                "kind": "page_recorded",
                "page_key": page_key,
                "url": page_url,
                "title": page_title,
                "buttons": [self._label_from_interactive(item) for item in interactive_elements if self._is_button_like(item)],
                "links": [self._label_from_interactive(item) for item in interactive_elements if self._is_link_like(item)],
                "dynamic_elements": summary.get("dialogs") or [],
                "page_sections": summary.get("page_sections") or [],
            },
        )
        return {
            "page_status": "scanned",
            "task_count": len(tasks),
            "in_page_count": sum(1 for task in tasks if task.get("task_group") == "in_page"),
            "navigation_count": sum(1 for task in tasks if task.get("task_group") == "navigation"),
            "tasks": tasks,
        }

    def dispatch_next_task(self, session_id: str, page_key: str) -> Dict[str, Any]:
        tasks = self.cache.get_page_tasks(page_key)
        next_task = self._select_next_task(tasks)
        if not next_task:
            return {"success": True, "has_task": False, "message": "no pending task"}

        if str(next_task.get("status") or "") != "running":
            ExplorationTaskService.update_task_status(tasks, next_task["task_id"], "running")
            self.cache.save_page_tasks(page_key, tasks)
        page_meta = self.cache.get_page_meta(page_key)
        if page_meta:
            page_meta["status"] = "running"
            self.cache.save_page_meta(page_key, page_meta)
            self.cache.update_frontier_entry(session_id, page_key, {"status": "running"})
        self.cache.update_session(session_id, {"current_page_key": page_key, "status": "running"})
        next_task["status"] = "running"
        next_task["completion_hint"] = "执行完成后调用 report_task_artifact 上报结果，并在需要时补充新的页面观察。"
        return {
            "success": True,
            "has_task": True,
            "task": next_task,
        }

    def accept_task_result(
        self,
        session_id: str,
        page_key: str,
        task_id: str,
        task_group: str,
        artifact: Dict[str, Any],
    ) -> Dict[str, Any]:
        tasks = self.cache.get_page_tasks(page_key)
        resolved_status = str(artifact.get("status") or "accepted").lower()
        if resolved_status not in {"accepted", "failed", "skipped"}:
            resolved_status = "accepted"
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

        new_page_key = ""
        navigation_detected = bool(artifact.get("navigated"))
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
        return {
            "task_status": resolved_status,
            "page_status": finalize.get("page_status", "running"),
            "navigation_detected": navigation_detected,
            "new_page_key": new_page_key,
            "page_completed": bool(finalize.get("completed")),
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

        self.cache.append_navigation(
            session_id,
            {
                "source_page_key": source_page_key,
                "target_page_name": target_page_name,
                "new_url": new_url,
                "task_id": task_id,
            },
        )
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
        return {"enqueued": True, "page_key": derived_page_key, "reason": "queued"}

    def finalize_page_if_ready(self, session_id: str, page_key: str) -> Dict[str, Any]:
        tasks = self.cache.get_page_tasks(page_key)
        pending_in_page = sum(1 for task in tasks if task.get("task_group") == "in_page" and task.get("status") == "pending")
        pending_navigation = sum(1 for task in tasks if task.get("task_group") == "navigation" and task.get("status") == "pending")
        running_tasks = sum(1 for task in tasks if task.get("status") == "running")
        completed = ExplorationTaskService.is_page_completed(tasks)

        page_meta = self.cache.get_page_meta(page_key)
        page_meta["status"] = "completed" if completed else ("running" if (running_tasks or tasks) else "scanned")
        self.cache.save_page_meta(page_key, page_meta)
        self.cache.update_frontier_entry(session_id, page_key, {"status": page_meta["status"]})
        if completed:
            self.cache.update_session(session_id, {"status": "running"})
        return {
            "completed": completed,
            "page_status": page_meta["status"],
            "pending_tasks": pending_in_page + pending_navigation + running_tasks,
            "pending_navigation": pending_navigation,
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
            self.cache.update_session(session_id, {"current_page_key": page_key, "status": "running"})
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
            for page in pages
        )
        completed = pending_frontier == 0 and pending_page_tasks == 0 and bool(pages)
        if completed:
            self.cache.update_session(session_id, {"status": "completed"})
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

        pages: List[Dict[str, Any]] = []
        for page_key in page_keys:
            meta = self.cache.get_page_meta(page_key)
            tasks = self.cache.get_page_tasks(page_key)
            pages.append(
                {
                    "page_key": page_key,
                    "meta": meta,
                    "task_total": len(tasks),
                    "task_status_summary": {
                        "pending": sum(1 for task in tasks if task.get("status") == "pending"),
                        "running": sum(1 for task in tasks if task.get("status") == "running"),
                        "accepted": sum(1 for task in tasks if task.get("status") == "accepted"),
                        "failed": sum(1 for task in tasks if task.get("status") == "failed"),
                        "skipped": sum(1 for task in tasks if task.get("status") == "skipped"),
                    },
                    "next_pending_tasks": [
                        {
                            "task_id": task.get("task_id", ""),
                            "task_group": task.get("task_group", ""),
                            "task_type": task.get("task_type", ""),
                            "element_label": task.get("element_label", ""),
                        }
                        for task in tasks
                        if task.get("status") == "pending"
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
        }

    @staticmethod
    def _select_next_task(tasks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for task in tasks:
            if task.get("status") == "running":
                return dict(task)
        for group in ("in_page", "navigation"):
            for task in tasks:
                if task.get("task_group") == group and task.get("status") == "pending":
                    return dict(task)
        return None

    @staticmethod
    def _label_from_interactive(item: Dict[str, Any]) -> str:
        for key in ("label", "title", "aria_label", "name", "placeholder", "selector", "tag"):
            value = str(item.get(key) or "").strip()
            if value:
                return value
        return ""

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
