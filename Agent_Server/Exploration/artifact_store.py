from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from .runtime import ExplorationRuntime
from .task_schema import ExplorationArtifact


def build_capabilities(runtime: ExplorationRuntime) -> Dict[str, Any]:
    buttons: List[str] = []
    links: List[str] = []
    page_sections: List[str] = []
    forms: List[Dict[str, Any]] = []
    tables: List[Dict[str, Any]] = []
    dialogs: List[str] = []
    page_types: List[str] = []

    for snapshot in runtime.snapshots:
        page_types.append(snapshot.page_type)
        buttons.extend(snapshot.buttons)
        links.extend(snapshot.links)
        page_sections.extend(snapshot.page_sections)
        dialogs.extend(snapshot.dialogs)
        for form in snapshot.forms:
            if form not in forms:
                forms.append(form)
        for table in snapshot.tables:
            if table not in tables:
                tables.append(table)

    buttons = list(dict.fromkeys([b for b in buttons if b]))[:30]
    links = list(dict.fromkeys([l for l in links if l]))[:20]
    page_sections = list(dict.fromkeys([s for s in page_sections if s]))[:20]
    dialogs = list(dict.fromkeys([d for d in dialogs if d]))[:10]
    page_type = Counter(page_types).most_common(1)[0][0] if page_types else "mixed"

    has_search = any(
        "search" in (field.get("name", "") + field.get("label", "") + field.get("placeholder", "")).lower() or
        "搜索" in (field.get("name", "") + field.get("label", "") + field.get("placeholder", ""))
        for form in forms for field in form.get("fields", [])
    ) or any(any(key in btn.lower() for key in ["search", "query"]) or "搜索" in btn or "查询" in btn for btn in buttons)
    has_pagination = any(table.get("has_pagination", False) for table in tables)
    has_export = any(any(key in btn.lower() for key in ["export", "download"]) or "导出" in btn or "下载" in btn for btn in buttons)
    has_import = any(any(key in btn.lower() for key in ["import", "upload"]) or "导入" in btn for btn in buttons)
    has_file_upload = any(
        (field.get("type") or "").lower() == "file"
        for form in forms for field in form.get("fields", [])
    ) or any("上传" in btn for btn in buttons)

    summary = (
        f"Explored {len(runtime.snapshots)} page snapshots, discovered "
        f"{len(forms)} forms, {len(tables)} tables and {len(buttons)} primary actions."
    )
    description = (
        f"Current exploration mode={runtime.mode}, current_engine={runtime.current_engine}, "
        f"page_sections={', '.join(page_sections[:8])}"
    )

    return {
        "page_type": page_type,
        "summary": summary,
        "description": description,
        "forms": forms,
        "tables": tables,
        "buttons": buttons,
        "links": links,
        "dynamic_elements": dialogs,
        "page_sections": page_sections,
        "auth_required": True,
        "has_file_upload": has_file_upload,
        "has_export": has_export,
        "has_import": has_import,
        "has_search": has_search,
        "has_pagination": has_pagination,
        "roles": [],
        "security_surface": [],
    }


def build_artifact(runtime: ExplorationRuntime) -> ExplorationArtifact:
    capabilities = build_capabilities(runtime)
    artifact_summary = {
        "snapshots": len(runtime.snapshots),
        "tasks": len(runtime.tasks),
        "executed_tasks": len(runtime.task_results),
        "frontier_exhausted": runtime.queue.is_empty(),
        "last_engine": runtime.current_engine,
        "interactive_candidates": sum(len(snapshot.candidates) for snapshot in runtime.snapshots),
    }
    coverage = {
        "frontier_exhausted": runtime.queue.is_empty(),
        "page_types": list(dict.fromkeys([snapshot.page_type for snapshot in runtime.snapshots])),
        "module_count": len(capabilities.get("page_sections", [])),
    }
    return ExplorationArtifact(
        task_run_id=runtime.run_id,
        mode=runtime.mode,
        entry_url=runtime.entry_url,
        goal=runtime.goal,
        snapshots=[snapshot.to_dict() for snapshot in runtime.snapshots],
        tasks=[task.to_dict() for task in runtime.tasks],
        task_results=[result.to_dict() for result in runtime.task_results],
        edges=runtime.edges,
        capabilities=capabilities,
        critical_paths=runtime.critical_paths,
        coverage=coverage,
        events=runtime.events,
        current_engine=runtime.current_engine,
        artifact_summary=artifact_summary,
    )
