from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

from .task_schema import Task


class QueueManager:
    """Simple priority queue with dedupe semantics for exploration tasks."""

    def __init__(self):
        self._items: List[Task] = []
        self._seen_keys: Set[str] = set()

    @staticmethod
    def _task_key(task: Task) -> str:
        return "|".join([
            task.page_snapshot_id,
            task.action,
            task.target_name.strip().lower(),
            task.selector_hint.strip(),
            task.semantic_group,
        ])

    def push(self, task: Task) -> bool:
        key = self._task_key(task)
        if key in self._seen_keys:
            return False
        self._seen_keys.add(key)
        self._items.append(task)
        self._items.sort(key=lambda item: (-item.priority, item.target_name))
        return True

    def push_many(self, tasks: Iterable[Task]) -> int:
        count = 0
        for task in tasks:
            if self.push(task):
                count += 1
        return count

    def pop(self) -> Optional[Task]:
        if not self._items:
            return None
        task = self._items.pop(0)
        task.status = "dispatched"
        return task

    def clear(self):
        self._items.clear()

    def is_empty(self) -> bool:
        return not self._items

    def __len__(self) -> int:
        return len(self._items)

    def snapshot(self) -> List[Dict]:
        return [task.to_dict() for task in self._items]
