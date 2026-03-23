from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Callable, Dict, Optional

from Api_request.prompts import BROWSER_USE_CHINESE_SYSTEM
from OneClick_Test.exploration_controller import ExplorationController
from OneClick_Test.exploration_prompts import EXPLORATION_SYSTEM_PROMPT, build_exploration_prompt
from OneClick_Test.exploration_state import ExplorationState
from llm import get_active_browser_use_llm

from .browser_use_tools import (
    create_browser_session,
    ensure_browser_started,
    navigate_to,
    read_url,
    stop_browser,
)

logger = logging.getLogger(__name__)


class BrowserUseAgentExplorer:
    @staticmethod
    async def run(
        mode: str,
        goal: str,
        env_info: Dict[str, Any],
        session_ref: Optional[Dict[str, Any]] = None,
        cancel_event: Optional[asyncio.Event] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        try:
            from browser_use import Agent
        except ImportError as exc:
            logger.error("[BrowserUseExplorer] failed to import Agent: %s", exc)
            return {"success": False, "message": f"browser_use import failed: {exc}"}

        cancel_event = cancel_event or asyncio.Event()
        state_manager = ExplorationState()
        controller = ExplorationController(state_manager)
        browser_session = None

        def emit(event_type: str, **payload):
            if status_callback:
                try:
                    status_callback(event_type, payload)
                except Exception as callback_err:
                    logger.debug("[BrowserUseExplorer] status callback failed: %s", callback_err)

        try:
            browser_session = await create_browser_session(env_info)
            if session_ref is not None:
                session_ref["browser_session"] = browser_session
                session_ref["cancel_event"] = cancel_event

            await ensure_browser_started(browser_session)

            start_url = (
                env_info.get("login_url")
                or env_info.get("target_url")
                or env_info.get("base_url")
                or ""
            )
            if start_url:
                await navigate_to(browser_session, start_url)

            task = build_exploration_prompt(
                user_goal=goal,
                env_info=env_info,
            )

            extend_prompt = "\n\n".join(
                part.strip()
                for part in [BROWSER_USE_CHINESE_SYSTEM, EXPLORATION_SYSTEM_PROMPT]
                if part and part.strip()
            )

            llm = get_active_browser_use_llm()
            agent = Agent(
                task=task,
                llm=llm,
                browser_session=browser_session,
                controller=controller,
                use_vision=os.getenv("LLM_USE_VISION", "false").lower() == "true",
                max_actions_per_step=int(os.getenv("MAX_ACTIONS", "10")),
                extend_system_message=extend_prompt,
            )

            emit("run.started", url=env_info.get("target_url", ""), start_url=start_url)
            emit("engine.selected", engine="browser_use")
            emit("task.started", title="browser_use_exploration", engine="browser_use")

            max_steps = int(os.getenv("EXPLORE_MAX_STEPS", "200"))
            agent_task = asyncio.create_task(agent.run(max_steps=max_steps))
            cancel_task = asyncio.create_task(cancel_event.wait())

            try:
                done, _ = await asyncio.wait(
                    {agent_task, cancel_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if cancel_task in done and cancel_event.is_set():
                    emit("run.cancelled", reason="cancel_event")
                    if not agent_task.done():
                        agent_task.cancel()
                        try:
                            await agent_task
                        except asyncio.CancelledError:
                            pass
                    return {"success": False, "message": "cancelled"}

                history = await agent_task
            finally:
                cancel_task.cancel()

            final_result = ""
            try:
                if hasattr(history, "final_result"):
                    raw_result = history.final_result()
                    final_result = raw_result if isinstance(raw_result, str) else json.dumps(raw_result, ensure_ascii=False)
            except Exception as exc:
                logger.debug("[BrowserUseExplorer] failed to read final result: %s", exc)

            total_steps = 0
            try:
                history_items = getattr(history, "history", [])
                total_steps = len(history_items) if history_items is not None else 0
            except Exception:
                total_steps = 0

            current_url = await read_url(browser_session)
            page_data = state_manager.build_page_data(
                total_steps=total_steps,
                user_input=goal,
                current_url=current_url,
                final_result=final_result,
                current_engine="browser_use",
            )
            BrowserUseAgentExplorer._merge_extra_result(page_data, BrowserUseAgentExplorer._parse_result(final_result))

            artifact = {
                "mode": mode,
                "entry_url": env_info.get("target_url") or env_info.get("base_url", ""),
                "goal": goal,
                "artifact_summary": page_data.get("artifact_summary", {}),
                "capabilities": page_data,
                "pages": page_data.get("pages", []),
            }

            emit("artifact.ready", summary=page_data.get("artifact_summary", {}))
            emit("run.completed", artifact_summary=page_data.get("artifact_summary", {}))
            return {
                "success": True,
                "page_data": page_data,
                "artifact": artifact,
            }
        except asyncio.CancelledError:
            logger.info("[BrowserUseExplorer] cancelled")
            return {"success": False, "message": "cancelled"}
        except Exception as exc:
            logger.error("[BrowserUseExplorer] run failed: %s", exc, exc_info=True)
            emit("run.failed", error=str(exc))
            return {"success": False, "message": str(exc)}
        finally:
            if browser_session:
                try:
                    await stop_browser(browser_session)
                except Exception as stop_err:
                    logger.warning("[BrowserUseExplorer] stop browser failed: %s", stop_err)
            if session_ref is not None:
                session_ref["browser_session"] = None

    @staticmethod
    def _parse_result(final_result: str) -> Dict[str, Any]:
        if not final_result:
            return {}
        try:
            parsed = json.loads(final_result)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _merge_extra_result(page_data: Dict[str, Any], extra: Dict[str, Any]):
        if not extra:
            return

        for key in ("summary", "description", "page_type"):
            value = extra.get(key)
            if value:
                page_data[key] = value

        for key in ("explored_modules", "explored_functions", "security_surface", "roles"):
            existing = list(page_data.get(key, []))
            incoming = extra.get(key, [])
            if isinstance(incoming, list):
                for item in incoming:
                    text = str(item).strip()
                    if text and text not in existing:
                        existing.append(text)
                page_data[key] = existing
