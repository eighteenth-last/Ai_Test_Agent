from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Optional

from .browser_use_agent_explorer import BrowserUseAgentExplorer


class ExplorationOrchestrator:
    @staticmethod
    async def run(
        mode: str,
        goal: str,
        env_info: Dict[str, Any],
        session_ref: Optional[Dict[str, Any]] = None,
        cancel_event: Optional[asyncio.Event] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        return await BrowserUseAgentExplorer.run(
            mode=mode,
            goal=goal,
            env_info=env_info,
            session_ref=session_ref,
            cancel_event=cancel_event,
            status_callback=status_callback,
        )
