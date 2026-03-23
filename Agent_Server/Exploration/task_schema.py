from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List


def _now_iso() -> str:
    return datetime.now().isoformat()


@dataclass
class InteractiveCandidate:
    candidate_id: str
    label: str
    selector: str = ""
    tag: str = ""
    role: str = ""
    element_type: str = ""
    section: str = ""
    href: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    priority: int = 0
    semantic_group: str = "general"
    dangerous: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PageSnapshot:
    snapshot_id: str
    url: str
    title: str = ""
    page_type: str = "mixed"
    page_signature: str = ""
    dom_richness: str = "vision"
    interactive_count: int = 0
    total_dom_nodes: int = 0
    buttons: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    page_sections: List[str] = field(default_factory=list)
    forms: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    dialogs: List[str] = field(default_factory=list)
    interactive_elements: List[Dict[str, Any]] = field(default_factory=list)
    candidates: List[InteractiveCandidate] = field(default_factory=list)
    screenshot_path: str = ""
    screenshot_base64: str = ""
    summary: str = ""
    description: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        return data


@dataclass
class Task:
    task_id: str
    action: str
    target_name: str
    page_snapshot_id: str
    priority: int = 0
    semantic_group: str = "general"
    issued_by: str = "manager_dom"
    allowed_engines: List[str] = field(default_factory=lambda: ["dom", "vision"])
    safety_level: str = "safe"
    selector_hint: str = ""
    region_hint: str = ""
    attempt: int = 0
    status: str = "queued"
    candidate_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskResult:
    task_id: str
    success: bool
    status: str
    engine: str
    locator: Dict[str, Any] = field(default_factory=dict)
    execution_result: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    need_fallback: bool = False
    fallback_engine: str = ""
    failure_code: str = ""
    worker_reason: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExplorationArtifact:
    task_run_id: str
    mode: str
    entry_url: str
    goal: str
    snapshots: List[Dict[str, Any]] = field(default_factory=list)
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    task_results: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    capabilities: Dict[str, Any] = field(default_factory=dict)
    critical_paths: List[Dict[str, Any]] = field(default_factory=list)
    coverage: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    current_engine: str = ""
    artifact_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
