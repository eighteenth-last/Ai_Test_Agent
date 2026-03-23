from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from .queue_manager import QueueManager
from .task_schema import PageSnapshot, Task, TaskResult


@dataclass
class ExplorationRuntime:
    run_id: str
    mode: str
    goal: str
    entry_url: str
    cancel_event: asyncio.Event
    queue: QueueManager = field(default_factory=QueueManager)
    browser_session: Any = None
    current_engine: str = ""
    current_task: str = ""
    snapshots: List[PageSnapshot] = field(default_factory=list)
    tasks: List[Task] = field(default_factory=list)
    task_results: List[TaskResult] = field(default_factory=list)
    critical_paths: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    visited_signatures: Set[str] = field(default_factory=set)
    blocked_tasks: Set[str] = field(default_factory=set)
    engine_history: List[str] = field(default_factory=list)
    root_session_ref: Optional[Dict[str, Any]] = None
    max_depth: int = 2
    max_tasks: int = 12
    max_snapshots: int = 10

    def emit(self, event_type: str, **data):
        self.events.append({
            "type": event_type,
            "time": datetime.now().isoformat(),
            "data": data,
        })

    def register_snapshot(self, snapshot: PageSnapshot):
        self.snapshots.append(snapshot)
        self.visited_signatures.add(snapshot.page_signature)
        self.emit(
            "snapshot.collected",
            snapshot_id=snapshot.snapshot_id,
            url=snapshot.url,
            page_type=snapshot.page_type,
            engine=snapshot.dom_richness,
        )

    def register_task(self, task: Task):
        self.tasks.append(task)
        self.emit(
            "task.queued",
            task_id=task.task_id,
            target=task.target_name,
            priority=task.priority,
            page_snapshot_id=task.page_snapshot_id,
        )

    def register_result(self, result: TaskResult):
        self.task_results.append(result)
        self.emit(
            "task.executed",
            task_id=result.task_id,
            status=result.status,
            engine=result.engine,
            success=result.success,
            failure_code=result.failure_code,
        )

    def cancelled(self) -> bool:
        return self.cancel_event.is_set()
