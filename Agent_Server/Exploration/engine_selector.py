from __future__ import annotations

from typing import Optional

from .task_schema import PageSnapshot


def choose_engine(snapshot: PageSnapshot, preferred: Optional[str] = None) -> str:
    if preferred in {"dom", "vision"}:
        return preferred
    selector_candidates = sum(1 for candidate in snapshot.candidates if candidate.selector)
    if selector_candidates >= 3:
        return "dom"
    if snapshot.forms or snapshot.tables:
        return "dom"
    if snapshot.dom_richness == "dom":
        return "dom"
    return "vision"
