from __future__ import annotations

import logging
from typing import Any, Dict, List, Set
from uuid import uuid4

logger = logging.getLogger(__name__)


class ExplorationTaskService:
    """Lightweight deterministic task generation for page exploration."""

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
    )

    @staticmethod
    def classify_task_group(element: Dict[str, Any]) -> str:
        href = str(element.get("href") or "").strip()
        tag = str(element.get("tag") or "").lower()
        role = str(element.get("role") or "").lower()
        label = str(
            element.get("label")
            or element.get("title")
            or element.get("aria_label")
            or element.get("name")
            or ""
        ).lower()
        section = str(element.get("section") or "").lower()

        if href or tag == "a" or role == "link":
            return "navigation"

        combined = f"{label} {section}".strip()
        if any(keyword in combined for keyword in ExplorationTaskService.IN_PAGE_KEYWORDS):
            return "in_page"
        if any(keyword in combined for keyword in ExplorationTaskService.NAVIGATION_KEYWORDS):
            return "navigation"
        return "in_page"

    @staticmethod
    def infer_task_type(element: Dict[str, Any], task_group: str) -> str:
        tag = str(element.get("tag") or "").lower()
        role = str(element.get("role") or "").lower()
        element_type = str(element.get("element_type") or "").lower()
        label = str(element.get("label") or "").lower()

        if tag in {"input", "textarea", "select"} or element_type in {"text", "password", "email", "search"}:
            return "form_input"
        if "pagination" in label or "page" in label or "下一页" in label or "上一页" in label:
            return "pagination"
        if "dialog" in label or "modal" in label or "弹窗" in label:
            return "dialog"
        if task_group == "navigation":
            return "navigate"
        if tag == "button" or role == "button" or element_type in {"button", "submit", "reset"}:
            return "button"
        return "interaction"

    @staticmethod
    def build_page_tasks(
        session_id: str,
        page_key: str,
        interactive_elements: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        tasks: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()

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

            element_label = str(
                element.get("label")
                or element.get("title")
                or element.get("aria_label")
                or element.get("name")
                or element.get("placeholder")
                or element_key
            ).strip()

            task_group = ExplorationTaskService.classify_task_group(element)
            task_type = ExplorationTaskService.infer_task_type(element, task_group)
            session_marker = session_id.replace(":", "_") if session_id else "global"
            task_id = f"task_{session_marker}_{uuid4().hex[:12]}"

            tasks.append(
                {
                    "task_id": task_id,
                    "session_id": session_id,
                    "page_key": page_key,
                    "task_group": task_group,
                    "task_type": task_type,
                    "element_key": element_key,
                    "element_label": element_label,
                    "action_payload": {
                        "selector": element.get("selector") or "",
                        "href": element.get("href") or "",
                        "x": element.get("x"),
                        "y": element.get("y"),
                        "candidate_id": element.get("candidate_id") or "",
                        "index": index,
                    },
                    "has_navigation": task_group == "navigation",
                    "status": "pending",
                    "attempt_count": 0,
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
    def update_task_status(tasks: List[Dict[str, Any]], task_id: str, status: str, result: Dict[str, Any] | None = None):
        for task in tasks:
            if task.get("task_id") != task_id:
                continue
            task["status"] = status
            if status == "running":
                task["attempt_count"] = int(task.get("attempt_count", 0)) + 1
            if result is not None:
                task["result_payload"] = result
            break

    @staticmethod
    def is_page_completed(tasks: List[Dict[str, Any]]) -> bool:
        if not tasks:
            return True
        return all(str(task.get("status") or "") in {"accepted", "completed", "skipped"} for task in tasks)
