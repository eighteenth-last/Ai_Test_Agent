from __future__ import annotations

from typing import Optional

from .task_schema import PageSnapshot


def choose_engine(snapshot: PageSnapshot, preferred: Optional[str] = None) -> str:
    if preferred in {"dom", "vision"}:
        return preferred
    if snapshot.candidates or snapshot.forms or snapshot.tables or snapshot.total_dom_nodes:
        return "dom"
    return "vision"
