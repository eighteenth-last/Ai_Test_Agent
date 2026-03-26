from __future__ import annotations

from typing import Any, Dict


class ExplorationSessionState:
    CREATED = "created"
    EXPLORING = "exploring"
    PAGE_SCANNED = "page_scanned"
    TASK_RUNNING = "task_running"
    VALIDATION_RESTORING = "validation_restoring"
    READY_FOR_NEXT_TASK = "ready_for_next_task"
    PAGE_COMPLETED = "page_completed"
    SESSION_COMPLETED = "session_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExplorationSessionStateMachine:
    """Small helper to standardize session status transitions in V3."""

    @staticmethod
    def started(current_page_key: str = "") -> Dict[str, Any]:
        return {"status": ExplorationSessionState.EXPLORING, "current_page_key": current_page_key}

    @staticmethod
    def page_scanned(page_key: str) -> Dict[str, Any]:
        return {"status": ExplorationSessionState.PAGE_SCANNED, "current_page_key": page_key}

    @staticmethod
    def task_running(page_key: str) -> Dict[str, Any]:
        return {"status": ExplorationSessionState.TASK_RUNNING, "current_page_key": page_key}

    @staticmethod
    def validation_restoring(page_key: str) -> Dict[str, Any]:
        return {"status": ExplorationSessionState.VALIDATION_RESTORING, "current_page_key": page_key}

    @staticmethod
    def ready_for_next_task(page_key: str) -> Dict[str, Any]:
        return {"status": ExplorationSessionState.READY_FOR_NEXT_TASK, "current_page_key": page_key}

    @staticmethod
    def page_completed(page_key: str) -> Dict[str, Any]:
        return {"status": ExplorationSessionState.PAGE_COMPLETED, "current_page_key": page_key}

    @staticmethod
    def session_completed() -> Dict[str, Any]:
        return {"status": ExplorationSessionState.SESSION_COMPLETED}
