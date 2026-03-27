import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from Exploration.cache_service import ExplorationCacheService
from Exploration.dispatcher_service import ExplorationDispatcherService
from Exploration.task_service import ExplorationTaskService

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
    def __init__(
        self,
        session_id: str = "",
        entry_mode: str = "",
        goal: str = "",
        entry_url: str = "",
        cache_service: Optional[ExplorationCacheService] = None,
    ):
        self.pages: Dict[str, PageInfo] = {}
        self.current_page_id: Optional[str] = None
        self.navigation_history: List[str] = []
        self.total_links_explored: int = 0
        self.exploration_stack: List[str] = []
        self.max_depth: int = 0
        self.session_id = session_id or ""
        self.entry_mode = entry_mode or ""
        self.goal = goal or ""
        self.entry_url = entry_url or ""
        self.cache_service = cache_service
        self.dispatcher = (
            ExplorationDispatcherService(self.cache_service)
            if self.cache_service and self.session_id
            else None
        )
        self.page_tasks: Dict[str, List[Dict[str, Any]]] = {}

        if self.dispatcher:
            self.dispatcher.start_exploration_session(
                session_id=self.session_id,
                entry_mode=self.entry_mode,
                goal=self.goal,
                entry_url=self.entry_url,
            )
        elif self.cache_service and self.session_id:
            self.cache_service.start_session(
                self.session_id,
                {
                    "session_id": self.session_id,
                    "entry_mode": self.entry_mode,
                    "goal": self.goal,
                    "entry_url": self.entry_url,
                    "status": "running",
                    "current_page_key": "",
                },
            )
        logger.info("[ExplorationState] initialized")

    def _cache_page_key(self, page_id: str) -> str:
        page_id = str(page_id or "").strip()
        if self.session_id:
            prefix = f"{self.session_id}:"
            if page_id.startswith(prefix):
                return page_id
            return f"{self.session_id}:{page_id}"
        return page_id

    def _page_id_from_cache_page_key(self, page_key: str) -> str:
        page_key = str(page_key or "").strip()
        if self.session_id:
            prefix = f"{self.session_id}:"
            if page_key.startswith(prefix):
                return page_key[len(prefix):]
        return page_key

    def _resolve_cache_page_key(self, page_id: str = "", task_id: str = "") -> str:
        raw_page_id = str(page_id or "").strip()
        if raw_page_id:
            return self._cache_page_key(raw_page_id)

        if self.cache_service and task_id:
            task_result = self.cache_service.get_task_result(task_id)
            saved_page_key = str(task_result.get("page_key") or "").strip()
            if saved_page_key:
                return saved_page_key

        if self.cache_service and self.session_id:
            session_page_key = str(self.cache_service.get_session(self.session_id).get("current_page_key") or "").strip()
            if session_page_key:
                return session_page_key

        if self.current_page_id:
            return self._cache_page_key(self.current_page_id)
        return ""

    def record_page(
        self,
        page_id: str,
        elements: List[Dict[str, Any]],
        url: str,
        dom_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        cache_page_key = self._resolve_cache_page_key(page_id)
        resolved_page_id = self._page_id_from_cache_page_key(cache_page_key)
        if self.dispatcher and not self.dispatcher.can_record_page(self.session_id, cache_page_key):
            return {
                "success": False,
                "message": "session is restoring validation context; do not record_page yet",
            }

        if resolved_page_id not in self.pages:
            self.pages[resolved_page_id] = PageInfo(page_id=resolved_page_id, url=url)

        page = self.pages[resolved_page_id]
        summary = dom_summary or {}
        interactive = summary.get("interactive_elements") or elements or []
        page.url = url or page.url
        page.title = str(summary.get("title") or page.title or "")
        page.elements = interactive
        page.dom_summary = summary
        page.is_recorded = True
        self.current_page_id = resolved_page_id

        current_depth = len(self.exploration_stack)
        if current_depth > self.max_depth:
            self.max_depth = current_depth

        logger.info(
            "[ExplorationState] recorded page=%s elements=%s depth=%s",
            page_id,
            len(page.elements),
            current_depth,
        )

        if self.dispatcher:
            register_result = self.dispatcher.register_page_scan(
                session_id=self.session_id,
                page_key=cache_page_key,
                page_url=page.url,
                page_title=page.title,
                interactive_elements=interactive,
                dom_summary=summary,
                depth=current_depth,
            )
            self.page_tasks[cache_page_key] = register_result.get("tasks", [])
        elif self.cache_service and self.session_id:
            cache_page_key = self._cache_page_key(page_id)
            page_meta = {
                "page_key": cache_page_key,
                "session_id": self.session_id,
                "url": page.url,
                "title": page.title,
                "depth": current_depth,
                "status": "scanned",
            }
            self.cache_service.save_page_meta(cache_page_key, page_meta)
            self.cache_service.save_page_scan(
                cache_page_key,
                {
                    "page_id": page_id,
                    "resolved_page_id": resolved_page_id,
                    "page_key": cache_page_key,
                    "title": page.title,
                    "url": page.url,
                    "interactive_elements": interactive,
                    "forms": summary.get("forms") or [],
                    "tables": summary.get("tables") or [],
                    "dialogs": summary.get("dialogs") or [],
                    "page_sections": summary.get("page_sections") or [],
                },
            )
            tasks = ExplorationTaskService.build_page_tasks(
                self.session_id,
                cache_page_key,
                interactive,
                summary,
            )
            self.page_tasks[cache_page_key] = tasks
            self.cache_service.save_page_tasks(cache_page_key, tasks)
            self.cache_service.update_session(
                self.session_id,
                {
                    "current_page_key": cache_page_key,
                    "status": "running",
                },
            )
            self.cache_service.append_page_artifact(
                cache_page_key,
                {
                    "kind": "page_recorded",
                    "page_id": page_id,
                    "page_key": cache_page_key,
                    "url": page.url,
                    "title": page.title,
                    "buttons": [self._label_from_interactive(item) for item in interactive if self._is_button_like(item)],
                    "links": [self._label_from_interactive(item) for item in interactive if self._is_link_like(item)],
                    "dynamic_elements": summary.get("dialogs") or [],
                    "page_sections": summary.get("page_sections") or [],
                },
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
        source_page_id = self.current_page_id
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

        if self.dispatcher and self.session_id:
            self.dispatcher.enqueue_navigation_page(
                session_id=self.session_id,
                source_page_key=self._cache_page_key(source_page_id or "") if source_page_id else "",
                task_id=f"manual_nav_{element_index}",
                target_page_name=target_page_name,
                depth=depth,
            )
        elif self.cache_service and self.session_id:
            navigation_payload = {
                "source_page_key": self._cache_page_key(source_page_id or "") if source_page_id else "",
                "target_page_name": target_page_name,
                "element_index": element_index,
                "depth": depth,
            }
            self.cache_service.append_navigation(self.session_id, navigation_payload)
            if target_page_name:
                self.cache_service.append_frontier(
                    self.session_id,
                    {
                        "page_key": self._cache_page_key(target_page_name),
                        "url": "",
                        "depth": depth,
                        "enqueue_reason": "navigation_task",
                        "status": "pending",
                    },
                )

    def mark_page_completed(self) -> Dict[str, Any]:
        page_id = self.current_page_id
        if self.dispatcher and self.session_id and page_id:
            completion = self.dispatcher.finalize_page_if_ready(self.session_id, self._cache_page_key(page_id))
            if not completion.get("completed"):
                return {
                    "success": False,
                    "message": (
                        f"page still has pending work: {completion.get('pending_tasks', 0)} task(s), "
                        f"{completion.get('pending_navigation', 0)} navigation task(s)"
                    ),
                }
        if self.exploration_stack:
            completed_page = self.exploration_stack.pop()
            logger.info(
                "[ExplorationState] completed page=%s remaining_depth=%s",
                completed_page,
                len(self.exploration_stack),
            )
        if self.cache_service and self.session_id and page_id and not self.dispatcher:
            cache_page_key = self._cache_page_key(page_id)
            page_meta = self.cache_service.get_page_meta(cache_page_key)
            page_meta.update({"status": "completed"})
            self.cache_service.save_page_meta(cache_page_key, page_meta)
        return {"success": True, "message": "current page marked completed"}

    def validate_completion(self) -> Dict[str, Any]:
        if self.dispatcher and self.session_id:
            finalize = self.dispatcher.finalize_session_if_ready(self.session_id)
            if finalize.get("completed"):
                return {"success": True}

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

        if self.cache_service and self.session_id:
            self.cache_service.update_session(self.session_id, {"status": "completed"})
        return {"success": True}

    def report_page_observation(
        self,
        page_id: str,
        observation: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not page_id:
            page_id = self.current_page_id or ""
        if not page_id:
            return {"success": False, "message": "page_id is required"}

        if self.cache_service and self.session_id:
            cache_page_key = self._cache_page_key(page_id)
            self.cache_service.append_page_artifact(
                cache_page_key,
                {
                    "kind": "page_observation",
                    "page_id": page_id,
                    "page_key": cache_page_key,
                    "buttons": observation.get("buttons", []),
                    "links": observation.get("links", []),
                    "dynamic_elements": observation.get("dynamic_elements", []),
                    "page_sections": observation.get("page_sections", []),
                    "observation": observation,
                },
            )
        return {"success": True, "message": "page observation recorded"}

    def report_task_artifact(
        self,
        task_id: str,
        task_group: str,
        page_id: str,
        artifact: Dict[str, Any],
    ) -> Dict[str, Any]:
        cache_page_key = self._resolve_cache_page_key(page_id, task_id)
        resolved_page_id = self._page_id_from_cache_page_key(cache_page_key)
        if not task_id or not cache_page_key or not resolved_page_id:
            return {"success": False, "message": "task_id and page_id are required"}

        if self.cache_service and self.session_id:
            if self.dispatcher:
                dispatch_result = self.dispatcher.accept_task_result(
                    session_id=self.session_id,
                    page_key=cache_page_key,
                    task_id=task_id,
                    task_group=task_group,
                    artifact=artifact,
                )
                if not dispatch_result.get("success"):
                    logger.warning(
                        "[ExplorationState] report_task_artifact rejected session_id=%s page_key=%s task_id=%s reason=%s",
                        self.session_id,
                        cache_page_key,
                        task_id,
                        dispatch_result.get("message", ""),
                    )
                    return {
                        "success": False,
                        "message": str(dispatch_result.get("message") or "failed to accept task result"),
                        "dispatch_result": dispatch_result,
                    }

                self.page_tasks[cache_page_key] = self.cache_service.get_page_tasks(cache_page_key)
                dispatch_result.setdefault("resolved_page_key", cache_page_key)
                dispatch_result.setdefault("resolved_page_id", resolved_page_id)
                logger.info(
                    "[ExplorationState] report_task_artifact accepted session_id=%s page_key=%s task_id=%s status=%s effect=%s session_status=%s",
                    self.session_id,
                    cache_page_key,
                    task_id,
                    dispatch_result.get("task_status", ""),
                    dispatch_result.get("effect_type", ""),
                    dispatch_result.get("session_status", ""),
                )
                return {
                    "success": True,
                    "message": "task artifact recorded",
                    "dispatch_result": dispatch_result,
                }
            tasks = self.page_tasks.get(cache_page_key)
            if tasks is None:
                tasks = self.cache_service.get_page_tasks(cache_page_key)
                self.page_tasks[cache_page_key] = tasks
            status = str(artifact.get("status") or "accepted")
            ExplorationTaskService.update_task_status(tasks, task_id, "accepted" if status == "accepted" else status, artifact)
            self.cache_service.save_page_tasks(cache_page_key, tasks)
            self.cache_service.save_task_result(
                task_id,
                {
                    "task_id": task_id,
                    "page_key": cache_page_key,
                    "task_group": task_group,
                    "artifact": artifact,
                },
            )
            self.cache_service.append_page_artifact(
                cache_page_key,
                {
                    "kind": "task_artifact",
                    "task_id": task_id,
                    "task_group": task_group,
                    "page_id": resolved_page_id,
                    "page_key": cache_page_key,
                    "buttons": artifact.get("buttons", []),
                    "links": artifact.get("links", []),
                    "dynamic_elements": artifact.get("dynamic_elements", []),
                    "page_sections": artifact.get("page_sections", []),
                    "artifact": artifact,
                },
            )
            if artifact.get("navigated") and self.session_id:
                self.cache_service.append_navigation(
                    self.session_id,
                    {
                        "source_page_key": cache_page_key,
                        "target_page_name": artifact.get("target_page_name", ""),
                        "new_url": artifact.get("new_url", ""),
                        "task_id": task_id,
                        "task_group": task_group,
                    },
                )
        return {"success": True, "message": "task artifact recorded"}

    def dispatch_next_task(self, page_id: str = "") -> Dict[str, Any]:
        cache_page_key = self._resolve_cache_page_key(page_id)
        resolved_page_id = self._page_id_from_cache_page_key(cache_page_key)
        if not self.dispatcher or not self.session_id or not cache_page_key or not resolved_page_id:
            return {"success": False, "message": "dispatcher or page context unavailable"}

        if not self.dispatcher.can_dispatch_next_task(self.session_id, cache_page_key):
            return {
                "success": False,
                "message": "session is restoring validation context; do not dispatch next task yet",
            }
        result = self.dispatcher.dispatch_next_task(self.session_id, cache_page_key)
        if result.get("success"):
            self.page_tasks[cache_page_key] = self.cache_service.get_page_tasks(cache_page_key)
            result.setdefault("resolved_page_key", cache_page_key)
            result.setdefault("resolved_page_id", resolved_page_id)
            logger.info(
                "[ExplorationState] dispatch_next_task session_id=%s page_key=%s has_task=%s session_status=%s",
                self.session_id,
                cache_page_key,
                bool(result.get("has_task")),
                result.get("session_status", ""),
            )
        else:
            logger.warning(
                "[ExplorationState] dispatch_next_task blocked session_id=%s page_key=%s message=%s",
                self.session_id,
                cache_page_key,
                result.get("message", ""),
            )
        return result

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
                    "cache_page_key": self._cache_page_key(page.page_id),
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
