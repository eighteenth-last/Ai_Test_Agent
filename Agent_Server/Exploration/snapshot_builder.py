from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from .task_schema import InteractiveCandidate, PageSnapshot


def _normalize_text_list(values: List[str], limit: int = 20) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        value = (value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def _last_href_segment(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    token = href.split("#")[-1].split("?")[0].rstrip("/")
    if "/" in token:
        token = token.split("/")[-1]
    return token.strip()


def _build_candidate_label(item: Dict[str, Any]) -> str:
    for key in ("label", "placeholder", "aria_label", "title", "name"):
        value = (item.get(key) or "").strip()
        if value:
            return value

    href_tail = _last_href_segment(item.get("href", ""))
    if href_tail:
        return href_tail

    section = (item.get("section") or "").strip()
    tag = (item.get("tag") or "element").strip().lower()
    element_type = (item.get("element_type") or "").strip().lower()
    candidate_id = (item.get("candidate_id") or "").strip()

    if section:
        if element_type:
            return f"{section}-{tag}-{element_type}"
        return f"{section}-{tag}"
    if element_type:
        return f"{tag}-{element_type}"
    if candidate_id:
        return f"{tag}-{candidate_id}"
    return tag or "element"


def guess_page_type(dom_summary: Dict[str, Any]) -> str:
    forms = dom_summary.get("forms", [])
    tables = dom_summary.get("tables", [])
    dialogs = dom_summary.get("dialogs", [])
    interactives = dom_summary.get("interactive_elements", [])

    has_password = any(
        (field.get("type") or "").lower() == "password"
        for form in forms
        for field in form.get("fields", [])
    )
    if has_password:
        return "login"
    if dialogs:
        return "dialog"
    if tables:
        return "list"
    if forms:
        return "form"
    if len(interactives) >= 12:
        return "dashboard"
    return "mixed"


def build_snapshot(
    snapshot_id: str,
    dom_summary: Dict[str, Any],
    detect_result: Dict[str, Any],
    screenshot: Dict[str, str],
) -> PageSnapshot:
    buttons = _normalize_text_list([
        _build_candidate_label(item)
        for item in dom_summary.get("interactive_elements", [])
        if (item.get("tag") or "").lower() == "button"
    ])
    links = _normalize_text_list([
        _build_candidate_label(item)
        for item in dom_summary.get("interactive_elements", [])
        if (item.get("tag") or "").lower() == "a"
    ])
    sections = _normalize_text_list(dom_summary.get("page_sections", []), limit=15)
    page_type = guess_page_type(dom_summary)

    candidates: List[InteractiveCandidate] = []
    for item in dom_summary.get("interactive_elements", []):
        label = _build_candidate_label(item)
        candidates.append(InteractiveCandidate(
            candidate_id=item.get("candidate_id", ""),
            label=label,
            selector=item.get("selector", ""),
            tag=item.get("tag", ""),
            role=item.get("role", ""),
            element_type=item.get("element_type", ""),
            section=item.get("section", ""),
            href=item.get("href", ""),
            x=float(item.get("x", 0)),
            y=float(item.get("y", 0)),
            width=float(item.get("width", 0)),
            height=float(item.get("height", 0)),
        ))

    signature_source = "|".join([
        dom_summary.get("url", ""),
        dom_summary.get("title", ""),
        page_type,
        ",".join(buttons[:10]),
        ",".join(sections[:10]),
        str(len(dom_summary.get("forms", []))),
        str(len(dom_summary.get("tables", []))),
        str(len(dom_summary.get("dialogs", []))),
    ])
    page_signature = hashlib.sha256(signature_source.encode("utf-8")).hexdigest()[:16]

    summary = (
        f"{page_type} page with {len(candidates)} interactive elements, "
        f"{len(dom_summary.get('forms', []))} forms, {len(dom_summary.get('tables', []))} tables"
    )

    return PageSnapshot(
        snapshot_id=snapshot_id,
        url=dom_summary.get("url", ""),
        title=dom_summary.get("title", ""),
        page_type=page_type,
        page_signature=page_signature,
        dom_richness=detect_result.get("mode", "vision"),
        interactive_count=detect_result.get("interactive", len(candidates)),
        total_dom_nodes=detect_result.get("total", dom_summary.get("total_dom_nodes", 0)),
        buttons=buttons,
        links=links,
        page_sections=sections,
        forms=dom_summary.get("forms", []),
        tables=dom_summary.get("tables", []),
        dialogs=dom_summary.get("dialogs", []),
        interactive_elements=dom_summary.get("interactive_elements", []),
        candidates=candidates,
        screenshot_path=screenshot.get("path", ""),
        screenshot_base64=screenshot.get("base64", ""),
        summary=summary,
        description=summary,
    )
