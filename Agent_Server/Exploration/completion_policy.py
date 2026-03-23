from __future__ import annotations

from .runtime import ExplorationRuntime


def should_stop(runtime: ExplorationRuntime, depth: int) -> bool:
    if runtime.cancelled():
        return True
    if len(runtime.task_results) >= runtime.max_tasks:
        return True
    if len(runtime.snapshots) >= runtime.max_snapshots:
        return True
    if depth > runtime.max_depth:
        return True
    return False
