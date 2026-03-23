import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class PageInfo:
    page_id: str
    url: str
    title: str = ""
    elements: List[Dict[str, Any]] = field(default_factory=list)
    dom_summary: Dict[str, Any] = field(default_factory=dict)
    is_recorded: bool = False
    explored_links: Set[int] = field(default_factory=set)


class ExplorationState:
    def __init__(self):
        self.pages: Dict[str, PageInfo] = {}
        self.current_page_id: Optional[str] = None
        self.navigation_history: List[str] = []
        self.total_links_explored: int = 0
        self.exploration_stack: List[str] = []
        self.max_depth: int = 0
        logger.info("[ExplorationState] initialized")

    def record_page(
        self,
        page_id: str,
        elements: List[Dict[str, Any]],
        url: str,
        dom_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if page_id not in self.pages:
            self.pages[page_id] = PageInfo(page_id=page_id, url=url)

        page = self.pages[page_id]
        summary = dom_summary or {}
        interactive = elements or summary.get("interactive_elements") or []
        page.url = url or page.url
        page.title = str(summary.get("title") or page.title or "")
        page.elements = interactive
        page.dom_summary = summary
        page.is_recorded = True
        self.current_page_id = page_id

        current_depth = len(self.exploration_stack)
        if current_depth > self.max_depth:
            self.max_depth = current_depth

        logger.info(
            "[ExplorationState] recorded page=%s elements=%s depth=%s",
            page_id,
            len(page.elements),
            current_depth,
        )
        return {"success": True, "message": f"recorded {len(page.elements)} elements"}

    def validate_navigate(self) -> Dict[str, Any]:
        if not self.current_page_id:
            return {"success": False, "message": "current page is not set"}

        current_page = self.pages.get(self.current_page_id)
        if not current_page or not current_page.is_recorded:
            return {"success": False, "message": "call record_page before navigation"}

        return {"success": True}

    def is_link_explored(self, element_index: int) -> bool:
        if not self.current_page_id:
            return False
        current_page = self.pages.get(self.current_page_id)
        if not current_page:
            return False
        return element_index in current_page.explored_links

    def mark_link_explored(self, element_index: int, target_page_name: str):
        if self.current_page_id:
            current_page = self.pages.get(self.current_page_id)
            if current_page:
                current_page.explored_links.add(element_index)

        self.exploration_stack.append(target_page_name)
        self.navigation_history.append(target_page_name)
        self.total_links_explored += 1

        depth = len(self.exploration_stack)
        logger.info(
            "[ExplorationState] explored link target=%s total_links=%s depth=%s",
            target_page_name,
            self.total_links_explored,
            depth,
        )

    def mark_page_completed(self):
        if self.exploration_stack:
            completed_page = self.exploration_stack.pop()
            logger.info(
                "[ExplorationState] completed page=%s remaining_depth=%s",
                completed_page,
                len(self.exploration_stack),
            )

    def validate_completion(self) -> Dict[str, Any]:
        if self.exploration_stack:
            return {
                "success": False,
                "message": f"{len(self.exploration_stack)} pages still need to return",
            }

        if self.max_depth < 2:
            return {
                "success": False,
                "message": f"exploration depth too shallow: {self.max_depth}",
            }

        if len(self.pages) < 3:
            return {
                "success": False,
                "message": f"not enough pages explored: {len(self.pages)}",
            }

        if self.total_links_explored < 5:
            return {
                "success": False,
                "message": f"not enough links explored: {self.total_links_explored}",
            }

        return {"success": True}

    def generate_report(self) -> str:
        report_lines = [
            "## Exploration Report",
            f"- Total pages: {len(self.pages)}",
            f"- Explored links: {self.total_links_explored}",
            f"- Max depth: {self.max_depth}",
            "",
            "### Pages",
        ]

        for page_id, page in self.pages.items():
            report_lines.append(
                f"- {page_id}: {len(page.elements)} elements, {len(page.explored_links)} explored links"
            )

        return "\n".join(report_lines)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_pages": len(self.pages),
            "total_links_explored": self.total_links_explored,
            "current_page": self.current_page_id,
            "recorded_pages": sum(1 for page in self.pages.values() if page.is_recorded),
            "max_depth": self.max_depth,
            "current_depth": len(self.exploration_stack),
        }

    def build_artifact_summary(self, total_steps: int = 0, engine: str = "browser_use") -> Dict[str, Any]:
        interactive_candidates = sum(
            len(page.dom_summary.get("interactive_elements") or page.elements or [])
            for page in self.pages.values()
        )
        return {
            "snapshots": len(self.pages),
            "tasks": max(total_steps, self.total_links_explored),
            "executed_tasks": total_steps,
            "frontier_exhausted": not self.exploration_stack,
            "last_engine": engine,
            "interactive_candidates": interactive_candidates,
        }

    def build_page_data(
        self,
        total_steps: int = 0,
        user_input: str = "",
        current_url: str = "",
        final_result: str = "",
        current_engine: str = "browser_use",
    ) -> Dict[str, Any]:
        forms: List[Dict[str, Any]] = []
        tables: List[Dict[str, Any]] = []
        buttons: List[str] = []
        links: List[str] = []
        dynamic_elements: List[str] = []
        page_sections: List[str] = []
        roles: List[str] = []
        available_actions: List[str] = []
        explored_modules: List[str] = []
        explored_functions: List[str] = []
        pages_payload: List[Dict[str, Any]] = []

        has_file_upload = False
        auth_required = False

        for page in self.pages.values():
            summary = page.dom_summary or {}
            interactive = summary.get("interactive_elements") or page.elements or []
            page_forms = summary.get("forms") or []
            page_tables = summary.get("tables") or []
            page_dialogs = summary.get("dialogs") or []
            sections = summary.get("page_sections") or []

            forms.extend(page_forms)
            tables.extend(page_tables)
            dynamic_elements.extend([str(item) for item in page_dialogs if item])
            page_sections.extend([str(item) for item in sections if item])
            explored_modules.extend([str(item) for item in sections if item])

            for form in page_forms:
                submit_button = str(form.get("submit_button") or "").strip()
                if submit_button:
                    available_actions.append(submit_button)
                    buttons.append(submit_button)

                for field in form.get("fields", []):
                    field_type = str(field.get("type") or "").lower()
                    if field_type == "password":
                        auth_required = True
                    if field_type == "file":
                        has_file_upload = True

            page_buttons: List[str] = []
            page_links: List[str] = []
            for item in interactive:
                label = self._label_from_interactive(item)
                if not label:
                    continue

                role = str(item.get("role") or "").strip()
                if role:
                    roles.append(role)

                tag = str(item.get("tag") or "").lower()
                href = str(item.get("href") or "").strip()
                element_type = str(item.get("element_type") or "").lower()

                if href or tag == "a" or role == "link":
                    links.append(label)
                    page_links.append(label)
                elif tag == "button" or role == "button" or element_type in {"button", "submit", "reset"}:
                    buttons.append(label)
                    page_buttons.append(label)

                available_actions.append(label)
                explored_functions.append(label)

            pages_payload.append(
                {
                    "page_id": page.page_id,
                    "title": page.title or str(summary.get("title") or ""),
                    "url": page.url,
                    "interactive_count": len(interactive),
                    "explored_links": len(page.explored_links),
                    "forms": len(page_forms),
                    "tables": len(page_tables),
                    "dialogs": list(dict.fromkeys([str(item) for item in page_dialogs if item])),
                    "page_sections": list(dict.fromkeys([str(item) for item in sections if item])),
                    "buttons": list(dict.fromkeys(page_buttons)),
                    "links": list(dict.fromkeys(page_links)),
                }
            )

        buttons = self._dedupe(buttons)
        links = self._dedupe(links)
        dynamic_elements = self._dedupe(dynamic_elements)
        page_sections = self._dedupe(page_sections)
        roles = self._dedupe(roles)
        available_actions = self._dedupe(available_actions)
        explored_modules = self._dedupe(explored_modules)
        explored_functions = self._dedupe(explored_functions)

        has_export = any(self._contains_keyword(item, ["export", "download", "导出", "下载"]) for item in available_actions)
        has_import = any(self._contains_keyword(item, ["import", "upload", "导入", "上传"]) for item in available_actions)
        has_search = any(self._contains_keyword(item, ["search", "query", "lookup", "搜索", "查询"]) for item in available_actions)
        has_pagination = any(self._contains_keyword(item, ["next", "prev", "page", "分页", "上一页", "下一页"]) for item in available_actions)

        stats = self.get_stats()
        artifact_summary = self.build_artifact_summary(total_steps=total_steps, engine=current_engine)
        current_page = self.pages.get(self.current_page_id or "")
        resolved_url = current_url or (current_page.url if current_page else "")
        resolved_title = ""
        if current_page:
            resolved_title = current_page.title or str(current_page.dom_summary.get("title") or "")
        if not resolved_title and pages_payload:
            resolved_title = str(pages_payload[-1].get("title") or "")

        summary = (
            f"Explored {stats['total_pages']} pages and {stats['total_links_explored']} links "
            f"for goal: {user_input or 'page exploration'}"
        )

        return {
            "page_title": resolved_title,
            "current_url": resolved_url,
            "page_type": "web_app",
            "summary": summary,
            "description": summary,
            "forms": forms,
            "tables": tables,
            "buttons": buttons,
            "links": links,
            "dynamic_elements": dynamic_elements,
            "page_sections": page_sections,
            "auth_required": auth_required,
            "has_file_upload": has_file_upload,
            "has_export": has_export,
            "has_import": has_import,
            "has_search": has_search,
            "has_pagination": has_pagination,
            "roles": roles,
            "security_surface": [],
            "explored_modules": explored_modules,
            "explored_functions": explored_functions,
            "available_actions": available_actions,
            "pages": pages_payload,
            "raw_output": final_result,
            "user_input": user_input,
            "exploration_stats": stats,
            "completed_pages_count": stats["total_pages"],
            "total_steps": total_steps,
            "total_links_explored": stats["total_links_explored"],
            "current_engine": current_engine,
            "artifact_summary": artifact_summary,
        }

    @staticmethod
    def _label_from_interactive(item: Dict[str, Any]) -> str:
        for key in ("label", "title", "aria_label", "name", "placeholder", "selector", "tag"):
            value = str(item.get(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _dedupe(values: List[str]) -> List[str]:
        seen = set()
        result: List[str] = []
        for value in values:
            clean_value = str(value).strip()
            if not clean_value or clean_value in seen:
                continue
            seen.add(clean_value)
            result.append(clean_value)
        return result

    @staticmethod
    def _contains_keyword(value: str, keywords: List[str]) -> bool:
        lower_value = str(value or "").lower()
        return any(keyword in lower_value for keyword in keywords)
