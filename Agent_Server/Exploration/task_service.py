from __future__ import annotations

import logging
from typing import Any, Dict, List, Set
from uuid import uuid4

logger = logging.getLogger(__name__)


class ExplorationTaskService:
    """Builds richer page tasks while keeping the current controller contract stable."""

    NAVIGATION_KEYWORDS = (
        "详情",
        "查看",
        "进入",
        "打开",
        "more",
        "detail",
        "view",
        "open",
        "next",
        "详情页",
        "click enter",
    )
    IN_PAGE_KEYWORDS = (
        "筛选",
        "展开",
        "更多",
        "tab",
        "标签",
        "折叠",
        "弹窗",
        "modal",
        "dialog",
        "drawer",
        "search",
        "query",
        "分页",
        "下一页",
        "上一页",
        "切换",
        "关闭",
        "提交",
        "保存",
    )
    TERMINAL_TASK_STATUSES = {"accepted", "completed", "skipped", "failed"}
    EFFECT_TYPES = {
        "no_effect",
        "state_changed",
        "dialog_opened",
        "dialog_closed",
        "content_expanded",
        "content_collapsed",
        "form_submitted",
        "form_validation_failed",
        "navigation_detected",
        "wrong_target",
        "partial_success",
        "failed",
    }

    @staticmethod
    def classify_task_group(element: Dict[str, Any]) -> str:
        href = str(element.get("href") or "").strip()
        tag = str(element.get("tag") or "").lower()
        role = str(element.get("role") or "").lower()
        label = ExplorationTaskService.label_for_element(element).lower()
        section = str(element.get("section") or "").lower()

        if href or tag == "a" or role == "link":
            return "navigation"

        combined = f"{label} {section}".strip()
        if any(keyword in combined for keyword in ExplorationTaskService.NAVIGATION_KEYWORDS):
            return "navigation"
        return "in_page"

    @staticmethod
    def infer_task_type(element: Dict[str, Any], task_group: str) -> str:
        tag = str(element.get("tag") or "").lower()
        role = str(element.get("role") or "").lower()
        element_type = str(element.get("element_type") or "").lower()
        label = ExplorationTaskService.label_for_element(element).lower()

        if tag in {"input", "textarea", "select"} or element_type in {"text", "password", "email", "search"}:
            return "form_input"
        if any(token in label for token in ("分页", "page", "下一页", "上一页", "next", "prev")):
            return "pagination"
        if any(token in label for token in ("dialog", "modal", "弹窗", "drawer")):
            return "dialog"
        if any(token in label for token in ("展开", "更多", "折叠", "expand", "collapse")):
            return "expand_section"
        if any(token in label for token in ("关闭", "取消", "close", "cancel")):
            return "close_panel"
        if any(token in label for token in ("提交", "保存", "确认", "登录", "submit", "save", "confirm", "login")):
            return "submit_action"
        if task_group == "navigation":
            return "navigate"
        if tag == "button" or role == "button" or element_type in {"button", "submit", "reset"}:
            return "button"
        return "interaction"

    @staticmethod
    def label_for_element(element: Dict[str, Any]) -> str:
        for key in ("label", "title", "aria_label", "name", "placeholder", "text", "selector", "tag"):
            value = str(element.get(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def build_page_summary(
        page_key: str,
        interactive_elements: List[Dict[str, Any]],
        dom_summary: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        summary = dom_summary or {}
        sections = [str(item).strip() for item in summary.get("page_sections") or [] if str(item).strip()]
        dialogs = [str(item).strip() for item in summary.get("dialogs") or [] if str(item).strip()]
        state_signals: List[str] = []

        if dialogs:
            state_signals.append("dialog_visible")
        if any(str(field.get("type") or "").lower() == "password" for form in summary.get("forms") or [] for field in form.get("fields") or []):
            state_signals.append("login_form_present")
        if any(ExplorationTaskService.label_for_element(item) for item in interactive_elements):
            state_signals.append("interactive_ready")
        if sections:
            state_signals.append("sections_detected")

        return {
            "page_key": page_key,
            "page_type": str(summary.get("page_type") or "web_app"),
            "interactive_count": len(interactive_elements),
            "state_signals": state_signals,
            "key_sections": sections[:12],
            "dialogs": dialogs[:8],
        }

    @staticmethod
    def build_page_tasks(
        session_id: str,
        page_key: str,
        interactive_elements: List[Dict[str, Any]],
        dom_summary: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        tasks: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()
        page_summary = ExplorationTaskService.build_page_summary(page_key, interactive_elements, dom_summary)

        for index, element in enumerate(interactive_elements):
            element_key = str(
                element.get("candidate_id")
                or element.get("selector")
                or element.get("href")
                or f"{page_key}:{index}"
            ).strip()
            if not element_key or element_key in seen_keys:
                continue
            seen_keys.add(element_key)

            element_label = ExplorationTaskService.label_for_element(element) or element_key
            task_group = ExplorationTaskService.classify_task_group(element)
            task_type = ExplorationTaskService.infer_task_type(element, task_group)
            session_marker = session_id.replace(":", "_") if session_id else "global"
            task_id = f"task_{session_marker}_{uuid4().hex[:12]}"
            candidate_pool = ExplorationTaskService._build_candidate_pool(
                interactive_elements=interactive_elements,
                base_index=index,
                task_group=task_group,
                task_type=task_type,
            )
            validation_config = ExplorationTaskService._build_validation_config(task_group, task_type, element_label)
            task_fingerprint = ExplorationTaskService._build_task_fingerprint(
                task_group=task_group,
                task_type=task_type,
                element_key=element_key,
                element_label=element_label,
            )

            tasks.append(
                {
                    "task_id": task_id,
                    "session_id": session_id,
                    "page_key": page_key,
                    "task_group": task_group,
                    "task_type": task_type,
                    "task_fingerprint": task_fingerprint,
                    "task_goal": ExplorationTaskService._build_task_goal(task_type, element_label),
                    "task_description": ExplorationTaskService._build_task_description(task_group, task_type, element_label),
                    "element_key": element_key,
                    "element_label": element_label,
                    "page_summary": page_summary,
                    "action_payload": {
                        "selector": element.get("selector") or "",
                        "href": element.get("href") or "",
                        "x": element.get("x"),
                        "y": element.get("y"),
                        "candidate_id": element.get("candidate_id") or "",
                        "index": index,
                    },
                    "candidate_pool": candidate_pool,
                    "success_criteria": ExplorationTaskService._build_success_criteria(task_group, task_type, element_label),
                    "failure_signals": ExplorationTaskService._build_failure_signals(task_group, task_type, element_label),
                    "task_memory": [],
                    "forbidden_targets": [],
                    "expected_effects": ExplorationTaskService._expected_effects(task_group, task_type),
                    "has_navigation": task_group == "navigation",
                    "max_attempts": 2 if task_group == "navigation" else 3,
                    "attempt_count": 0,
                    "status": "pending",
                    "last_effect_type": "",
                    "is_validation_task": bool(validation_config),
                    "validation_goal": validation_config.get("validation_goal", ""),
                    "validation_success_signals": validation_config.get("validation_success_signals", []),
                    "resume_after_validation": validation_config.get("resume_after_validation", False),
                    "skip_rescan_after_execute": validation_config.get("skip_rescan_after_execute", False),
                }
            )

        logger.info(
            "[ExplorationTaskService] built tasks page=%s total=%s in_page=%s nav=%s",
            page_key,
            len(tasks),
            sum(1 for item in tasks if item["task_group"] == "in_page"),
            sum(1 for item in tasks if item["task_group"] == "navigation"),
        )
        return tasks

    @staticmethod
    def merge_page_tasks(
        existing_tasks: List[Dict[str, Any]],
        new_tasks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        existing_by_fingerprint: Dict[str, Dict[str, Any]] = {}
        for task in existing_tasks or []:
            fingerprint = str(task.get("task_fingerprint") or "").strip()
            if fingerprint:
                existing_by_fingerprint[fingerprint] = dict(task)

        merged: List[Dict[str, Any]] = []
        seen_fingerprints: Set[str] = set()

        for task in new_tasks or []:
            fingerprint = str(task.get("task_fingerprint") or "").strip()
            previous = existing_by_fingerprint.get(fingerprint)
            if previous:
                merged_task = dict(task)
                merged_task["task_id"] = previous.get("task_id", merged_task.get("task_id", ""))
                merged_task["status"] = previous.get("status", merged_task.get("status", "pending"))
                merged_task["attempt_count"] = previous.get("attempt_count", merged_task.get("attempt_count", 0))
                merged_task["last_effect_type"] = previous.get("last_effect_type", merged_task.get("last_effect_type", ""))
                merged_task["task_memory"] = list(previous.get("task_memory") or merged_task.get("task_memory") or [])
                merged_task["forbidden_targets"] = list(previous.get("forbidden_targets") or merged_task.get("forbidden_targets") or [])
                if "result_payload" in previous:
                    merged_task["result_payload"] = previous.get("result_payload")
                merged_task["is_validation_task"] = bool(
                    previous.get("is_validation_task") or merged_task.get("is_validation_task")
                )
                if not merged_task.get("validation_goal"):
                    merged_task["validation_goal"] = previous.get("validation_goal", "")
                if not merged_task.get("validation_success_signals"):
                    merged_task["validation_success_signals"] = list(previous.get("validation_success_signals") or [])
                merged_task["resume_after_validation"] = bool(
                    previous.get("resume_after_validation") or merged_task.get("resume_after_validation")
                )
                merged_task["skip_rescan_after_execute"] = bool(
                    previous.get("skip_rescan_after_execute") or merged_task.get("skip_rescan_after_execute")
                )
                merged.append(merged_task)
            else:
                merged.append(task)
            if fingerprint:
                seen_fingerprints.add(fingerprint)

        for task in existing_tasks or []:
            fingerprint = str(task.get("task_fingerprint") or "").strip()
            if not fingerprint or fingerprint in seen_fingerprints:
                continue
            if str(task.get("status") or "") in ExplorationTaskService.TERMINAL_TASK_STATUSES:
                merged.append(dict(task))

        return merged

    @staticmethod
    def update_task_status(
        tasks: List[Dict[str, Any]],
        task_id: str,
        status: str,
        result: Dict[str, Any] | None = None,
    ):
        for task in tasks:
            if task.get("task_id") != task_id:
                continue
            task["status"] = status
            if status == "running":
                task["attempt_count"] = int(task.get("attempt_count", 0)) + 1
            if result is not None:
                task["result_payload"] = result
                effect_type = str(result.get("effect_type") or "").strip()
                if effect_type:
                    task["last_effect_type"] = effect_type
                executed_target = result.get("executed_target") or {}
                target_marker = str(
                    executed_target.get("candidate_id")
                    or executed_target.get("selector")
                    or executed_target.get("label")
                    or ""
                ).strip()
                if effect_type in {"wrong_target", "no_effect"} and target_marker:
                    forbidden = list(task.get("forbidden_targets") or [])
                    if target_marker not in forbidden:
                        forbidden.append(target_marker)
                    task["forbidden_targets"] = forbidden
                memory = list(task.get("task_memory") or [])
                summary = str(result.get("observed_result") or result.get("replan_reason") or effect_type or status).strip()
                if summary:
                    memory.append(
                        {
                            "attempt": int(task.get("attempt_count", 0)),
                            "status": status,
                            "effect_type": effect_type,
                            "summary": summary,
                        }
                    )
                task["task_memory"] = memory[-8:]
            break

    @staticmethod
    def is_page_completed(tasks: List[Dict[str, Any]]) -> bool:
        if not tasks:
            return True
        return all(str(task.get("status") or "") in ExplorationTaskService.TERMINAL_TASK_STATUSES for task in tasks)

    @staticmethod
    def summarize_task_status(tasks: List[Dict[str, Any]]) -> Dict[str, int]:
        return {
            "pending": sum(1 for task in tasks if task.get("status") == "pending"),
            "running": sum(1 for task in tasks if task.get("status") == "running"),
            "retry_pending": sum(1 for task in tasks if task.get("status") == "retry_pending"),
            "accepted": sum(1 for task in tasks if task.get("status") == "accepted"),
            "failed": sum(1 for task in tasks if task.get("status") == "failed"),
            "skipped": sum(1 for task in tasks if task.get("status") == "skipped"),
        }

    @staticmethod
    def _build_candidate_pool(
        interactive_elements: List[Dict[str, Any]],
        base_index: int,
        task_group: str,
        task_type: str,
    ) -> List[Dict[str, Any]]:
        base_element = interactive_elements[base_index]
        base_label = ExplorationTaskService.label_for_element(base_element).lower()
        candidates: List[Dict[str, Any]] = []

        for index, element in enumerate(interactive_elements):
            if ExplorationTaskService.classify_task_group(element) != task_group:
                continue
            label = ExplorationTaskService.label_for_element(element)
            if not label and not (element.get("selector") or element.get("href")):
                continue

            score = 0.4
            normalized = label.lower()
            if index == base_index:
                score = 1.0
            elif base_label and normalized and (normalized in base_label or base_label in normalized):
                score = 0.86
            elif ExplorationTaskService.infer_task_type(element, task_group) == task_type:
                score = 0.72

            candidates.append(
                {
                    "candidate_id": element.get("candidate_id") or "",
                    "selector": element.get("selector") or "",
                    "label": label,
                    "role": str(element.get("role") or ""),
                    "tag": str(element.get("tag") or ""),
                    "href": element.get("href") or "",
                    "index": index,
                    "confidence": round(score, 2),
                    "reason": "base target" if index == base_index else "same task family",
                }
            )

        candidates.sort(key=lambda item: (-float(item.get("confidence") or 0), int(item.get("index") or 0)))
        deduped: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        for item in candidates:
            marker = str(item.get("candidate_id") or item.get("selector") or item.get("href") or item.get("label") or "").strip()
            if not marker or marker in seen:
                continue
            seen.add(marker)
            deduped.append(item)
            if len(deduped) >= 5:
                break
        return deduped

    @staticmethod
    def _build_task_goal(task_type: str, element_label: str) -> str:
        if task_type == "navigate":
            return f"Navigate to the target page triggered by '{element_label}'."
        if task_type == "form_input":
            return f"Fill or focus the form field related to '{element_label}'."
        if task_type == "submit_action":
            return f"Submit or confirm the action for '{element_label}'."
        if task_type == "dialog":
            return f"Inspect the dialog or modal related to '{element_label}'."
        if task_type == "expand_section":
            return f"Expand or reveal the content behind '{element_label}'."
        if task_type == "close_panel":
            return f"Close or dismiss the panel triggered by '{element_label}'."
        return f"Interact with '{element_label}' and observe the resulting UI change."

    @staticmethod
    def _build_task_description(task_group: str, task_type: str, element_label: str) -> str:
        if task_group == "navigation":
            return (
                f"This is a navigation task for '{element_label}'. Confirm whether it opens a new route, "
                "detail page, tab, or other page-level context."
            )
        return (
            f"This is an in-page task for '{element_label}'. Explore the local UI change only and keep the "
            "current page context unless a real navigation is observed."
        )

    @staticmethod
    def _build_success_criteria(task_group: str, task_type: str, element_label: str) -> List[str]:
        criteria = ["A visible UI change is observed after the action."]
        if task_group == "navigation":
            criteria.extend(
                [
                    "URL changed, route changed, or a new page context is clearly entered.",
                    "A new page title, module, detail region, or content context becomes active.",
                ]
            )
        else:
            criteria.extend(
                [
                    "Current page remains active while local state changes are visible.",
                    "The resulting state can be described as a dialog, expansion, filter, form, or content change.",
                ]
            )
        if task_type == "submit_action":
            criteria.append("Submission feedback, validation feedback, or content refresh is observed.")
        if task_type == "close_panel":
            criteria.append("The related dialog, drawer, or panel is no longer visible.")
        if element_label:
            criteria.append(f"The effect can still be traced back to '{element_label}'.")
        return criteria

    @staticmethod
    def _build_failure_signals(task_group: str, task_type: str, element_label: str) -> List[str]:
        failures = ["No observable DOM, URL, or state change after the action."]
        if task_group == "navigation":
            failures.append("The page stays on the same context and no new content area appears.")
        else:
            failures.append("An unrelated page, dialog, or detail view opened instead of a local change.")
        if task_type == "close_panel":
            failures.append("The target panel remains visible after the action.")
        if task_type == "submit_action":
            failures.append("The action opens unrelated UI instead of submitting the intended form or confirmation.")
        if element_label:
            failures.append(f"The action clearly does not match the intent of '{element_label}'.")
        return failures

    @staticmethod
    def _expected_effects(task_group: str, task_type: str) -> List[str]:
        if task_group == "navigation":
            return ["navigation_detected", "state_changed", "partial_success", "wrong_target", "no_effect", "failed"]
        if task_type == "dialog":
            return ["dialog_opened", "dialog_closed", "state_changed", "wrong_target", "no_effect", "failed"]
        if task_type == "expand_section":
            return ["content_expanded", "content_collapsed", "state_changed", "wrong_target", "no_effect", "failed"]
        if task_type == "submit_action":
            return ["form_submitted", "form_validation_failed", "state_changed", "wrong_target", "no_effect", "failed"]
        return ["state_changed", "partial_success", "wrong_target", "no_effect", "failed"]

    @staticmethod
    def _build_task_fingerprint(task_group: str, task_type: str, element_key: str, element_label: str) -> str:
        normalized_label = str(element_label or "").strip().lower()
        normalized_key = str(element_key or "").strip().lower()
        return f"{task_group}::{task_type}::{normalized_key or normalized_label}"

    @staticmethod
    def _build_validation_config(task_group: str, task_type: str, element_label: str) -> Dict[str, Any]:
        label = str(element_label or "").strip().lower()
        if not label:
            return {}

        logout_keywords = ("退出登录", "退出", "注销", "logout", "sign out", "log out")
        close_keywords = ("关闭", "收起", "取消", "返回", "close", "cancel", "collapse")

        if any(keyword in label for keyword in logout_keywords):
            return {
                "validation_goal": f"Verify that '{element_label}' logs the user out, then restore the previous session before reporting completion.",
                "validation_success_signals": [
                    "Login form or anonymous state becomes visible after the action.",
                    "The previous authenticated menu or user area disappears.",
                    "After verification, the session is restored and the original exploration context is available again.",
                ],
                "resume_after_validation": True,
                "skip_rescan_after_execute": True,
            }

        if task_group == "in_page" and task_type in {"close_panel", "dialog", "expand_section"} and any(
            keyword in label for keyword in close_keywords
        ):
            return {
                "validation_goal": f"Verify the local UI effect triggered by '{element_label}' without rescanning the page.",
                "validation_success_signals": [
                    "The related dialog, panel, or expanded content changes to the expected local state.",
                    "No new page queue is created for this verification action.",
                ],
                "resume_after_validation": False,
                "skip_rescan_after_execute": True,
            }

        return {}
