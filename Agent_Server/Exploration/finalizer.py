from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from Page_Knowledge.service import PageKnowledgeService

from .cache_service import ExplorationCacheService

logger = logging.getLogger(__name__)


class ExplorationFinalizer:
    """Merge Redis-cached exploration artifacts into final page knowledge payloads."""

    def __init__(self, cache_service: Optional[ExplorationCacheService] = None):
        self.cache = cache_service or ExplorationCacheService()

    @staticmethod
    def _dedupe_strings(values: List[Any]) -> List[str]:
        result: List[str] = []
        seen = set()
        for value in values:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    @staticmethod
    def _merge_items(existing: List[Any], incoming: List[Any]) -> List[Any]:
        merged = list(existing or [])
        seen = {str(item) for item in merged}
        for item in incoming or []:
            marker = str(item)
            if marker in seen:
                continue
            seen.add(marker)
            merged.append(item)
        return merged

    def enrich_page_data(self, session_id: str, page_data: Dict[str, Any]) -> Dict[str, Any]:
        pages = list(page_data.get("pages") or [])
        buttons = list(page_data.get("buttons") or [])
        links = list(page_data.get("links") or [])
        dynamic_elements = list(page_data.get("dynamic_elements") or [])
        page_sections = list(page_data.get("page_sections") or [])

        frontier = self.cache.list_frontier(session_id)
        navigation = self.cache.list_navigation(session_id)
        session_artifacts = self.cache.list_session_artifacts(session_id)
        session_meta = self.cache.get_session(session_id)
        effect_counter: Counter[str] = Counter()
        artifact_events: Counter[str] = Counter()

        for page in pages:
            page_key = str(page.get("cache_page_key") or page.get("page_id") or "").strip()
            if not page_key:
                continue
            scan = self.cache.get_page_scan(page_key)
            artifacts = self.cache.list_page_artifacts(page_key)
            tasks = self.cache.get_page_tasks(page_key)

            scan_buttons = [item.get("label") for item in scan.get("interactive_elements", []) if item.get("label")]
            scan_links = [
                item.get("label")
                for item in scan.get("interactive_elements", [])
                if item.get("href") or str(item.get("tag") or "").lower() == "a"
            ]
            buttons = self._merge_items(buttons, scan_buttons)
            links = self._merge_items(links, scan_links)
            dynamic_elements = self._merge_items(dynamic_elements, scan.get("dialogs", []))
            page_sections = self._merge_items(page_sections, scan.get("page_sections", []))

            page["generated_tasks"] = len(tasks)
            page["cached_artifacts"] = len(artifacts)
            page["status"] = self.cache.get_page_meta(page_key).get("status", page.get("status", "recorded"))

            for artifact in artifacts:
                buttons = self._merge_items(buttons, artifact.get("buttons", []))
                links = self._merge_items(links, artifact.get("links", []))
                dynamic_elements = self._merge_items(dynamic_elements, artifact.get("dynamic_elements", []))
                page_sections = self._merge_items(page_sections, artifact.get("page_sections", []))
                artifact_payload = artifact.get("artifact") or {}
                effect_type = str(artifact_payload.get("effect_type") or artifact.get("effect_type") or "").strip()
                if effect_type:
                    effect_counter[effect_type] += 1

        for session_artifact in session_artifacts:
            event_type = str(session_artifact.get("event_type") or "").strip()
            if event_type:
                artifact_events[event_type] += 1
            effect_type = str(session_artifact.get("effect_type") or "").strip()
            if effect_type:
                effect_counter[effect_type] += 1

        page_data["buttons"] = self._dedupe_strings(buttons)
        page_data["links"] = self._dedupe_strings(links)
        page_data["dynamic_elements"] = self._dedupe_strings(dynamic_elements)
        page_data["page_sections"] = self._dedupe_strings(page_sections)
        page_data["pages"] = pages
        page_data["frontier_pages"] = frontier
        page_data["navigation_events"] = navigation
        page_data["session_artifacts"] = session_artifacts[-120:]

        summary = dict(page_data.get("artifact_summary") or {})
        summary["cached_navigation"] = len(navigation)
        summary["frontier_size"] = len(frontier)
        summary["cache_enabled"] = self.cache.enabled
        summary["session_artifact_count"] = len(session_artifacts)
        summary["effect_summary"] = dict(effect_counter)
        summary["event_summary"] = dict(artifact_events)
        if session_meta:
            summary["session_status"] = session_meta.get("status", "")
        page_data["artifact_summary"] = summary
        return page_data

    async def finalize_page_knowledge(
        self,
        session_id: str,
        url: str,
        page_data: Dict[str, Any],
        db,
        project_id: int | None = None,
        cleanup: bool = True,
    ) -> Dict[str, Any]:
        enriched = self.enrich_page_data(session_id, page_data)
        result = await PageKnowledgeService.check_and_update(
            url=url,
            new_capabilities=enriched,
            db=db,
            project_id=project_id,
        )
        if cleanup:
            self.cleanup_session_cache(session_id)
        return {
            "capabilities": enriched,
            "knowledge_result": result,
        }

    def cleanup_session_cache(self, session_id: str):
        self.cache.cleanup_session(session_id)
