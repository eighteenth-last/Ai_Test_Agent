import asyncio
import json
import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from Exploration.browser_use_runtime import ensure_browser_use_runtime_env
from Exploration.dom_manager_prompts import build_dom_manager_prompt
from llm import get_llm_client

ensure_browser_use_runtime_env()

try:
    from browser_use.agent.views import ActionResult
    from browser_use.tools.service import Tools
    from browser_use.tools.views import ClickElementAction
    try:
        from browser_use import BrowserSession
    except ImportError:
        from browser_use.browser import BrowserSession
except ImportError as exc:
    logging.error("failed to import browser-use: %s", exc)
    raise

logger = logging.getLogger(__name__)


class ExplorationController(Tools):
    def __init__(self, exploration_state):
        super().__init__(exclude_actions=["search", "extract", "upload_file", "screenshot"])
        self.exploration_state = exploration_state
        self._register_exploration_actions()
        logger.info("[ExplorationController] initialized")

    @staticmethod
    def _format_task_text(task: Dict[str, Any]) -> str:
        candidate_pool = task.get("candidate_pool") or []
        top_candidate = candidate_pool[0] if candidate_pool else {}
        return (
            f"task_id={task.get('task_id', '')}; "
            f"group={task.get('task_group', '')}; "
            f"type={task.get('task_type', '')}; "
            f"goal={task.get('task_goal', '')}; "
            f"validation={bool(task.get('is_validation_task'))}; "
            f"target={task.get('element_label', '')}; "
            f"selector={task.get('action_payload', {}).get('selector', '')}; "
            f"candidate_id={task.get('action_payload', {}).get('candidate_id', '')}; "
            f"top_candidate={top_candidate.get('label', '')}; "
            f"success_criteria={len(task.get('success_criteria', []) or [])}"
        )

    @staticmethod
    def _parse_llm_json(text: str) -> Dict[str, Any]:
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            try:
                from json_repair import repair_json

                repaired = repair_json(text, return_objects=True)
                return repaired if isinstance(repaired, dict) else {}
            except Exception:
                return {}

    async def _resolve_interactive_elements(
        self,
        page_id: str,
        dom_summary: Dict[str, Any],
        fallback_elements: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        candidates = list(dom_summary.get("dom_candidates") or dom_summary.get("interactive_elements") or [])
        if not candidates:
            return list(fallback_elements or [])

        llm = get_llm_client()
        snapshot = {
            "page_id": page_id,
            "title": dom_summary.get("title", ""),
            "url": dom_summary.get("url", ""),
            "dialogs": dom_summary.get("dialogs") or [],
            "page_sections": dom_summary.get("page_sections") or [],
            "forms": dom_summary.get("forms") or [],
            "tables": dom_summary.get("tables") or [],
            "candidate_count": len(candidates),
        }
        prompt = build_dom_manager_prompt(
            goal=self.exploration_state.goal or "整理当前页面可交互元素",
            snapshot=snapshot,
            candidates=candidates,
        )

        try:
            content = await llm.achat(
                messages=[
                    {"role": "system", "content": "你只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=4000,
                response_format={"type": "json_object"},
                source="dom_interactive_filter",
            )
            payload = self._parse_llm_json(content)
        except Exception as exc:
            logger.warning("[ExplorationController] failed to resolve interactive elements with llm: %s", exc)
            payload = {}

        selected = payload.get("interactive_elements") if isinstance(payload, dict) else []
        candidate_map = {
            str(item.get("candidate_id") or "").strip(): dict(item)
            for item in candidates
            if str(item.get("candidate_id") or "").strip()
        }
        resolved: List[Dict[str, Any]] = []
        seen_ids = set()
        for item in selected or []:
            candidate_id = str((item or {}).get("candidate_id") or "").strip()
            base = candidate_map.get(candidate_id)
            if not base or candidate_id in seen_ids:
                continue
            merged = dict(base)
            label_override = str((item or {}).get("label_override") or "").strip()
            if label_override:
                merged["label"] = label_override
            interaction_type = str((item or {}).get("interaction_type") or "").strip()
            if interaction_type:
                merged["interaction_type"] = interaction_type
            merged["llm_confidence"] = float((item or {}).get("confidence") or 0.0)
            merged["llm_reason"] = str((item or {}).get("reason") or "").strip()
            resolved.append(merged)
            seen_ids.add(candidate_id)

        if resolved:
            return resolved
        if fallback_elements:
            return list(fallback_elements)
        return candidates

    def _register_exploration_actions(self):
        class RecordPageParams(BaseModel):
            page_id: str = Field(description="Stable page identifier")
            elements: List[Dict[str, Any]] = Field(description="Interactive elements detected on the page")

        @self.registry.action(
            description="Record the current page before navigating away from it.",
            param_model=RecordPageParams,
        )
        async def record_page(params: RecordPageParams, browser_session: BrowserSession) -> ActionResult:
            logger.info(
                "[ExplorationController] record_page page_id=%s elements=%s",
                params.page_id,
                len(params.elements),
            )

            current_url = ""
            try:
                current_url = await browser_session.get_current_page_url()
            except Exception as exc:
                logger.warning("[ExplorationController] failed to read current url: %s", exc)

            dom_mode_hint = ""
            dom_summary: Dict[str, Any] = {}
            interactive_elements = list(params.elements or [])

            try:
                from Exploration.browser_use_tools import extract_dom_summary

                dom_summary = await extract_dom_summary(browser_session)
                interactive_elements = await self._resolve_interactive_elements(
                    page_id=params.page_id,
                    dom_summary=dom_summary,
                    fallback_elements=interactive_elements,
                )
                dom_summary["interactive_elements"] = interactive_elements
                interactive = len(interactive_elements)
                total = int(dom_summary.get("total_dom_nodes") or 0)
                candidates = len(dom_summary.get("dom_candidates") or [])
                dom_mode_hint = (
                    f" DOM primary: candidates={candidates}, interactive={interactive}, total={total}, mode=dom+llm"
                )
            except Exception as exc:
                logger.warning("[ExplorationController] failed to extract DOM summary: %s", exc)

            result = self.exploration_state.record_page(
                page_id=params.page_id,
                elements=interactive_elements,
                url=current_url,
                dom_summary=dom_summary,
            )
            if not result["success"]:
                return ActionResult(
                    error=result["message"],
                    extracted_content=(
                        "Do not rescan the page right now. If the current task is a validation task, "
                        "finish restoring the original session/context and then report the same task again."
                    ),
                    include_in_memory=True,
                )

            title = str(dom_summary.get("title") or params.page_id)
            msg = (
                f"Recorded page '{params.page_id}' ({title}) with "
                f"{len(interactive_elements)} interactive elements."
                f"{dom_mode_hint}"
            )
            next_task_result = self.exploration_state.dispatch_next_task(params.page_id)
            if next_task_result.get("success") and next_task_result.get("has_task"):
                task_text = self._format_task_text(next_task_result.get("task") or {})
                msg += f"\nServer assigned next task: {task_text}"
            else:
                msg += "\nServer has no pending task for this page yet."
            return ActionResult(extracted_content=msg, include_in_memory=True)

        class ExploreLinkParams(BaseModel):
            element_index: int = Field(description="Interactive element index to click")
            target_page_name: str = Field(description="Expected target page name")

        @self.registry.action(
            description="Click a link or button to explore a child page, then continue exploration there.",
            param_model=ExploreLinkParams,
        )
        async def explore_link(params: ExploreLinkParams, browser_session: BrowserSession) -> ActionResult:
            logger.info(
                "[ExplorationController] explore_link index=%s target=%s",
                params.element_index,
                params.target_page_name,
            )

            validation = self.exploration_state.validate_navigate()
            if not validation["success"]:
                return ActionResult(error=validation["message"], include_in_memory=True)

            if self.exploration_state.is_link_explored(params.element_index):
                return ActionResult(
                    error=f"element {params.element_index} has already been explored",
                    include_in_memory=True,
                )

            try:
                click_action = self.registry.registry.actions.get("click")
                if not click_action:
                    return ActionResult(error="click action is unavailable", include_in_memory=True)

                click_params = ClickElementAction(index=params.element_index)
                click_result = await click_action.function(
                    params=click_params,
                    browser_session=browser_session,
                )
                if isinstance(click_result, ActionResult) and click_result.error:
                    return click_result
            except Exception as exc:
                return ActionResult(error=f"click failed: {exc}", include_in_memory=True)

            await asyncio.sleep(3)
            self.exploration_state.mark_link_explored(
                element_index=params.element_index,
                target_page_name=params.target_page_name,
            )
            msg = (
                f"Entered '{params.target_page_name}'. Record the new page, explore it deeply, "
                "then use go_back() after it is complete."
            )
            return ActionResult(extracted_content=msg, include_in_memory=True)

        @self.registry.action(
            description="Mark the current page as fully explored before going back.",
        )
        async def mark_page_completed() -> ActionResult:
            result = self.exploration_state.mark_page_completed()
            if not result["success"]:
                return ActionResult(error=result["message"], include_in_memory=True)
            return ActionResult(
                extracted_content="Current page is complete. Use go_back() to return to the parent page.",
                include_in_memory=True,
            )

        class DispatchNextTaskParams(BaseModel):
            page_id: str = Field(default="", description="Current page id; empty means use the recorded current page")

        @self.registry.action(
            description="Ask the server for the next exploration task of the current page. The server will prioritize in-page tasks before navigation tasks.",
            param_model=DispatchNextTaskParams,
        )
        async def dispatch_next_task(params: DispatchNextTaskParams) -> ActionResult:
            result = self.exploration_state.dispatch_next_task(params.page_id)
            if not result["success"]:
                return ActionResult(
                    error=result["message"],
                    extracted_content=(
                        "Do not request the next task yet. Finish restoring the validation context first, "
                        "then call `report_task_artifact()` again for the same task. "
                        f"session_status={result.get('session_status', '')}"
                    ),
                    include_in_memory=True,
                )
            if not result.get("has_task"):
                return ActionResult(
                    extracted_content=(
                        "No pending task remains on the current page. "
                        f"session_status={result.get('session_status', '')}"
                    ),
                    include_in_memory=True,
                )

            task = result.get("task") or {}
            task_text = (
                f"Next task: {self._format_task_text(task)}\n"
                f"hint={task.get('completion_hint', '')}"
            )
            return ActionResult(extracted_content=task_text, include_in_memory=True)

        class ReportPageObservationParams(BaseModel):
            page_id: str = Field(description="Current page id")
            buttons: List[str] = Field(default_factory=list, description="New buttons or button labels observed")
            links: List[str] = Field(default_factory=list, description="New links observed")
            dynamic_elements: List[str] = Field(default_factory=list, description="Dialogs, drawers, modals, toasts observed")
            page_sections: List[str] = Field(default_factory=list, description="Page sections or modules observed")
            note: str = Field(default="", description="Short note about the current observation")

        @self.registry.action(
            description="Report the latest page observation so the server can cache page artifacts outside the model context.",
            param_model=ReportPageObservationParams,
        )
        async def report_page_observation(params: ReportPageObservationParams) -> ActionResult:
            payload = params.model_dump()
            result = self.exploration_state.report_page_observation(params.page_id, payload)
            if not result["success"]:
                return ActionResult(error=result["message"], include_in_memory=True)
            return ActionResult(
                extracted_content=f"Reported page observation for '{params.page_id}'.",
                include_in_memory=True,
            )

        class ReportTaskArtifactParams(BaseModel):
            task_id: str = Field(description="Current task identifier")
            task_group: str = Field(default="in_page", description="Task group: in_page or navigation")
            page_id: str = Field(default="", description="Current page id")
            status: str = Field(default="accepted", description="Task result status")
            validation_status: str = Field(default="", description="Structured validation result: accepted/retry_pending/failed/skipped")
            effect_type: str = Field(default="", description="Structured effect type after the action")
            observed_result: str = Field(default="", description="Short summary of the observed result")
            replan_reason: str = Field(default="", description="Why the task should be replanned when the action had no effect or hit a wrong target")
            navigated: bool = Field(default=False, description="Whether the task navigated to a new page")
            new_url: str = Field(default="", description="New URL when navigation happened")
            target_page_name: str = Field(default="", description="Target page name if known")
            executed_target: Dict[str, Any] = Field(default_factory=dict, description="The actual clicked or operated target")
            before_state: Dict[str, Any] = Field(default_factory=dict, description="State summary before executing the action")
            after_state: Dict[str, Any] = Field(default_factory=dict, description="State summary after executing the action")
            buttons: List[str] = Field(default_factory=list, description="New buttons observed after this task")
            links: List[str] = Field(default_factory=list, description="New links observed after this task")
            dynamic_elements: List[str] = Field(default_factory=list, description="Dialogs or transient UI observed")
            page_sections: List[str] = Field(default_factory=list, description="Sections observed after task execution")
            evidence: List[str] = Field(default_factory=list, description="Evidence strings proving the result")
            is_validation_task: bool = Field(default=False, description="Whether this task is validation-only")
            validation_passed: bool = Field(default=False, description="Whether the validation goal passed")
            session_restored: bool = Field(default=False, description="Whether the pre-validation session was restored")
            resume_note: str = Field(default="", description="Short note about the restore step")

        @self.registry.action(
            description="Report the artifact produced by a single exploration task so the server can cache task results.",
            param_model=ReportTaskArtifactParams,
        )
        async def report_task_artifact(params: ReportTaskArtifactParams, browser_session: BrowserSession) -> ActionResult:
            payload = params.model_dump()
            payload["runtime_state_available"] = False
            try:
                from Exploration.browser_use_tools import extract_dom_summary

                current_url = await browser_session.get_current_page_url()
                dom_summary = await extract_dom_summary(browser_session)
                fields = [
                    field
                    for form in dom_summary.get("forms", [])
                    for field in form.get("fields", [])
                ]
                login_form_present = any((field.get("type") or "").lower() == "password" for field in fields)
                payload["runtime_state_available"] = True
                payload["runtime_current_url"] = current_url
                payload["runtime_page_title"] = str(dom_summary.get("title") or "")
                payload["runtime_login_form_present"] = login_form_present
            except Exception as exc:
                logger.warning("[ExplorationController] failed to inspect runtime state for task artifact: %s", exc)

            result = self.exploration_state.report_task_artifact(
                task_id=params.task_id,
                task_group=params.task_group,
                page_id=params.page_id,
                artifact=payload,
            )
            if not result["success"]:
                dispatch_result = result.get("dispatch_result") or {}
                return ActionResult(
                    error=result["message"],
                    extracted_content=(
                        f"Task artifact for '{params.task_id}' was rejected by the server. "
                        f"reason={result.get('message', '')}; "
                        f"session_status={dispatch_result.get('session_status', '')}"
                    ),
                    include_in_memory=True,
                )
            dispatch_result = result.get("dispatch_result") or {}
            page_id = (
                dispatch_result.get("resolved_page_id")
                or params.page_id
                or self.exploration_state.current_page_id
                or ""
            )
            if dispatch_result.get("page_completed"):
                return ActionResult(
                    extracted_content=(
                        f"Reported task artifact for '{params.task_id}'. "
                        "Current page has no pending server task. "
                        "Call mark_page_completed() and then go_back() if this is a child page."
                    ),
                    include_in_memory=True,
                )
            if dispatch_result.get("is_validation_task") and not dispatch_result.get("session_restored"):
                return ActionResult(
                    extracted_content=(
                        f"Validation task '{params.task_id}' is not committed yet because the session/context "
                        "has not been restored. Restore the previous session first, then call "
                        f"`report_task_artifact()` again for the same task_id and page_id='{page_id}'. "
                        "Do not call `record_page()` or `dispatch_next_task()` yet. "
                        f"session_status={dispatch_result.get('session_status', '')}"
                    ),
                    include_in_memory=True,
                )
            next_task_result = self.exploration_state.dispatch_next_task(page_id)
            if next_task_result.get("success") and next_task_result.get("has_task"):
                task = next_task_result.get("task") or {}
                task_text = self._format_task_text(task)
                return ActionResult(
                    extracted_content=(
                        f"Reported task artifact for '{params.task_id}'. "
                        f"Server assigned next task: {task_text}. "
                        f"session_status={next_task_result.get('session_status', '')}"
                    ),
                    include_in_memory=True,
                )
            if not next_task_result.get("success"):
                return ActionResult(
                    extracted_content=(
                        f"Reported task artifact for '{params.task_id}', but the next task is not available yet. "
                        f"reason={next_task_result.get('message', '')}; "
                        f"session_status={next_task_result.get('session_status', '')}"
                    ),
                    include_in_memory=True,
                )
            return ActionResult(
                extracted_content=(
                    f"Reported task artifact for '{params.task_id}'. "
                    f"session_status={dispatch_result.get('session_status', '')}; "
                    f"next_dispatch_status={next_task_result.get('session_status', '')}"
                ),
                include_in_memory=True,
            )

        @self.registry.action(
            description="Refresh the current page when the UI is stuck or did not finish loading.",
        )
        async def refresh_page(browser_session: BrowserSession) -> ActionResult:
            try:
                page = browser_session.context.pages[0] if browser_session.context and browser_session.context.pages else None
                if not page:
                    return ActionResult(error="current page is unavailable", include_in_memory=True)
                await page.reload()
                await asyncio.sleep(3)
                current_url = await browser_session.get_current_page_url()
                return ActionResult(
                    extracted_content=f"Refreshed page: {current_url}",
                    include_in_memory=True,
                )
            except Exception as exc:
                return ActionResult(error=f"refresh failed: {exc}", include_in_memory=True)

        @self.registry.action(
            description="Complete exploration after all reachable pages and branches have been explored.",
        )
        async def complete_exploration() -> ActionResult:
            validation = self.exploration_state.validate_completion()
            if not validation["success"]:
                return ActionResult(
                    error=f"exploration is not complete: {validation['message']}",
                    include_in_memory=True,
                )

            report = self.exploration_state.generate_report()
            return ActionResult(extracted_content=report, include_in_memory=True)

        logger.info("[ExplorationController] actions registered")
