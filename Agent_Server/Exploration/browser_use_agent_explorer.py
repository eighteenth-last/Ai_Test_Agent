from __future__ import annotations

import asyncio
import json
import logging
import os
from uuid import uuid4
from typing import Any, Callable, Dict, Optional

from Api_request.prompts import BROWSER_USE_CHINESE_SYSTEM
from Exploration.cache_service import ExplorationCacheService
from Exploration.dispatcher_service import ExplorationDispatcherService
from Exploration.finalizer import ExplorationFinalizer
from Exploration.browser_use_runtime import ensure_browser_use_runtime_env
from OneClick_Test.exploration_prompts import (
    EXPLORATION_SYSTEM_PROMPT,
    TASK_DRIVEN_EXPLORATION_SYSTEM_PROMPT,
    build_exploration_prompt,
    build_single_task_round_prompt,
    build_task_driven_exploration_prompt,
)
from OneClick_Test.exploration_state import ExplorationState
from llm import get_active_browser_use_llm

from .browser_use_tools import (
    create_browser_session,
    ensure_browser_started,
    navigate_to,
    read_url,
    stop_browser,
    try_basic_login,
)

logger = logging.getLogger(__name__)

ensure_browser_use_runtime_env()


def _env_flag(name: str, default: str) -> bool:
    return os.getenv(name, default).lower() == "true"


def _use_exploration_engine_v2(mode: str) -> bool:
    if mode == "knowledge":
        return _env_flag(
            "EXPLORATION_ENGINE_V2",
            os.getenv("KNOWLEDGE_EXPLORATION_V2", "true"),
        )
    if mode == "oneclick":
        queue_enabled_default = "true" if _env_flag("ONECLICK_EXPLORATION_V2", "true") else "false"
        return _env_flag("ONECLICK_EXPLORATION_ENGINE_V2", queue_enabled_default)
    return False


def _format_browser_use_import_error(exc: Exception) -> str:
    runtime_dir = ensure_browser_use_runtime_env()
    raw_message = str(exc)
    if "browser-use-downloads" in raw_message or "\\tmp\\" in raw_message or "/tmp/" in raw_message:
        return (
            f"browser_use 初始化失败: {raw_message}。"
            f"项目已将 BROWSER_USE_CONFIG_DIR 重定向到 {runtime_dir}，"
            "但当前 browser_use 版本仍在初始化默认下载目录 /tmp/browser-use-downloads-*。"
            "建议升级/修补该依赖，或在可写环境中运行。"
        )
    return f"browser_use import failed: {raw_message}"


def _format_runtime_error(exc: Exception) -> str:
    raw_message = str(exc)
    if "Can't connect to MySQL server" in raw_message or "数据库查询失败" in raw_message:
        return (
            f"页面探索启动失败: {raw_message}。"
            "当前不是 browser_use 兼容问题，而是项目依赖的 MySQL 未连接。"
            "请先启动项目数据库，或修正 Agent_Server/.env 中的数据库配置。"
        )
    return raw_message


async def _attempt_env_login(browser_session, env_info: Dict[str, Any], emit) -> Dict[str, Any]:
    username = str(env_info.get("username") or "")
    password = str(env_info.get("password") or "")
    if not username or not password:
        return {"success": False, "attempted": False, "detected_login": False, "reason": "missing_credentials"}

    login_result = await try_basic_login(browser_session, username, password)
    if not isinstance(login_result, dict):
        login_result = {"success": bool(login_result), "attempted": True, "detected_login": bool(login_result)}

    emit("login.attempted", result=login_result)

    if login_result.get("success"):
        target_url = str(env_info.get("target_url") or "")
        login_url = str(env_info.get("login_url") or "")
        current_url = await read_url(browser_session)
        if target_url and login_url and target_url != login_url and current_url != target_url:
            try:
                await navigate_to(browser_session, target_url)
                emit("login.redirected", from_url=current_url, to_url=target_url)
            except Exception as redirect_err:
                logger.warning("[BrowserUseExplorer] post-login navigate to target failed: %s", redirect_err)
                emit(
                    "login.redirect_failed",
                    from_url=current_url,
                    to_url=target_url,
                    error=str(redirect_err),
                )
    return login_result


class BrowserUseAgentExplorer:
    @staticmethod
    def _emit_session_snapshot(emit, dispatcher, exploration_session_id: str, session_completion: Dict[str, Any], **extra):
        if not exploration_session_id:
            return
        emit(
            "session.snapshot",
            snapshot=dispatcher.get_session_snapshot(exploration_session_id),
            session_completion=session_completion,
            **extra,
        )

    @staticmethod
    async def run(
        mode: str,
        goal: str,
        env_info: Dict[str, Any],
        session_ref: Optional[Dict[str, Any]] = None,
        cancel_event: Optional[asyncio.Event] = None,
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        ensure_browser_use_runtime_env()
        try:
            from browser_use import Agent
            from OneClick_Test.exploration_controller import ExplorationController
        except Exception as exc:
            logger.error("[BrowserUseExplorer] failed to import Agent: %s", exc)
            return {
                "success": False,
                "message": _format_browser_use_import_error(exc),
            }

        cancel_event = cancel_event or asyncio.Event()
        cache_service = ExplorationCacheService()
        dispatcher = ExplorationDispatcherService(cache_service)
        finalizer = ExplorationFinalizer(cache_service)
        exploration_session_id = ""
        state_manager: Optional[ExplorationState] = None
        controller: Optional[ExplorationController] = None
        browser_session = None

        def emit(event_type: str, **payload):
            if status_callback:
                try:
                    status_callback(event_type, payload)
                except Exception as callback_err:
                    logger.debug("[BrowserUseExplorer] status callback failed: %s", callback_err)

        try:
            if _use_exploration_engine_v2(mode):
                exploration_session_id = (
                    str(session_ref.get("exploration_session_id") or "")
                    if session_ref
                    else ""
                ) or f"exp_{uuid4().hex[:16]}"
                cache_service.start_session(
                    exploration_session_id,
                    {
                        "session_id": exploration_session_id,
                        "entry_mode": mode,
                        "goal": goal,
                        "entry_url": env_info.get("target_url") or env_info.get("base_url") or "",
                        "status": "running",
                        "current_page_key": "",
                    },
                )
                if session_ref is not None:
                    session_ref["exploration_session_id"] = exploration_session_id

            state_manager = ExplorationState(
                session_id=exploration_session_id,
                entry_mode=mode,
                goal=goal,
                entry_url=env_info.get("target_url") or env_info.get("base_url") or "",
                cache_service=cache_service if exploration_session_id else None,
            )
            controller = ExplorationController(state_manager)
            llm = get_active_browser_use_llm()

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

            login_result = await _attempt_env_login(browser_session, env_info, emit)
            if login_result.get("success"):
                logger.info(
                    "[BrowserUseExplorer] environment login submitted successfully: env=%s",
                    env_info.get("env_name") or env_info.get("_source") or "manual",
                )
            elif login_result.get("attempted"):
                logger.info(
                    "[BrowserUseExplorer] environment login attempted but not completed: %s",
                    login_result.get("reason"),
                )

            if exploration_session_id:
                session_snapshot = dispatcher.get_session_snapshot(exploration_session_id)
                task = build_task_driven_exploration_prompt(
                    user_goal=goal,
                    env_info=env_info,
                    session_snapshot=session_snapshot,
                )
            else:
                task = build_exploration_prompt(
                    user_goal=goal,
                    env_info=env_info,
                )

            system_prompt = TASK_DRIVEN_EXPLORATION_SYSTEM_PROMPT if exploration_session_id else EXPLORATION_SYSTEM_PROMPT
            extend_prompt = "\n\n".join(
                part.strip()
                for part in [BROWSER_USE_CHINESE_SYSTEM, system_prompt]
                if part and part.strip()
            )

            emit("run.started", url=env_info.get("target_url", ""), start_url=start_url)
            emit("engine.selected", engine="browser_use")
            emit("task.started", title="browser_use_exploration", engine="browser_use")
            if exploration_session_id:
                loop_result = await BrowserUseAgentExplorer._run_task_driven_loop(
                    agent_cls=Agent,
                    llm=llm,
                    browser_session=browser_session,
                    controller=controller,
                    goal=goal,
                    env_info=env_info,
                    dispatcher=dispatcher,
                    exploration_session_id=exploration_session_id,
                    cancel_event=cancel_event,
                    emit=emit,
                    extend_prompt=extend_prompt,
                )
                if not loop_result.get("success"):
                    return loop_result
                final_result = loop_result.get("final_result", "")
                total_steps = int(loop_result.get("total_steps", 0))
                session_completion = loop_result.get("session_completion", {})
            else:
                history = await BrowserUseAgentExplorer._run_agent_round(
                    agent_cls=Agent,
                    task=task,
                    llm=llm,
                    browser_session=browser_session,
                    controller=controller,
                    cancel_event=cancel_event,
                    extend_prompt=extend_prompt,
                    max_steps=int(os.getenv("EXPLORE_MAX_STEPS", "200")),
                )
                final_result, total_steps = BrowserUseAgentExplorer._extract_history(history)
                session_completion = {}

            current_url = await read_url(browser_session)
            assert state_manager is not None
            page_data = state_manager.build_page_data(
                total_steps=total_steps,
                user_input=goal,
                current_url=current_url,
                final_result=final_result,
                current_engine="browser_use",
            )
            BrowserUseAgentExplorer._merge_extra_result(page_data, BrowserUseAgentExplorer._parse_result(final_result))
            if exploration_session_id:
                if session_completion.get("completed"):
                    cache_service.update_session(exploration_session_id, {"status": "completed"})
                page_data = finalizer.enrich_page_data(exploration_session_id, page_data)
                page_data.setdefault("artifact_summary", {})["session_completion"] = session_completion

            artifact = {
                "mode": mode,
                "entry_url": env_info.get("target_url") or env_info.get("base_url", ""),
                "goal": goal,
                "artifact_summary": page_data.get("artifact_summary", {}),
                "capabilities": page_data,
                "pages": page_data.get("pages", []),
            }

            emit("artifact.ready", summary=page_data.get("artifact_summary", {}))
            if exploration_session_id:
                BrowserUseAgentExplorer._emit_session_snapshot(
                    emit,
                    dispatcher,
                    exploration_session_id,
                    session_completion,
                )
            emit("run.completed", artifact_summary=page_data.get("artifact_summary", {}))
            return {
                "success": True,
                "page_data": page_data,
                "artifact": artifact,
                "exploration_session_id": exploration_session_id,
            }
        except asyncio.CancelledError:
            logger.info("[BrowserUseExplorer] cancelled")
            if exploration_session_id:
                cache_service.update_session(exploration_session_id, {"status": "cancelled"})
            return {"success": False, "message": "cancelled"}
        except Exception as exc:
            logger.error("[BrowserUseExplorer] run failed: %s", exc, exc_info=True)
            emit("run.failed", error=str(exc))
            if exploration_session_id:
                cache_service.update_session(
                    exploration_session_id,
                    {"status": "failed", "error": str(exc)},
                )
            return {"success": False, "message": _format_runtime_error(exc)}
        finally:
            if browser_session:
                try:
                    await stop_browser(browser_session)
                except Exception as stop_err:
                    logger.warning("[BrowserUseExplorer] stop browser failed: %s", stop_err)
            if session_ref is not None:
                session_ref["browser_session"] = None

    @staticmethod
    async def _run_agent_round(
        agent_cls,
        task: str,
        llm,
        browser_session,
        controller,
        cancel_event: asyncio.Event,
        extend_prompt: str,
        max_steps: int,
    ):
        agent = agent_cls(
            task=task,
            llm=llm,
            browser_session=browser_session,
            controller=controller,
            use_vision=os.getenv("LLM_USE_VISION", "false").lower() == "true",
            max_actions_per_step=int(os.getenv("MAX_ACTIONS", "10")),
            extend_system_message=extend_prompt,
        )
        agent_task = asyncio.create_task(agent.run(max_steps=max_steps))
        cancel_task = asyncio.create_task(cancel_event.wait())
        try:
            done, _ = await asyncio.wait(
                {agent_task, cancel_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if cancel_task in done and cancel_event.is_set():
                if not agent_task.done():
                    agent_task.cancel()
                    try:
                        await agent_task
                    except asyncio.CancelledError:
                        pass
                raise asyncio.CancelledError
            return await agent_task
        finally:
            cancel_task.cancel()

    @staticmethod
    async def _run_task_driven_loop(
        agent_cls,
        llm,
        browser_session,
        controller,
        goal: str,
        env_info: Dict[str, Any],
        dispatcher: ExplorationDispatcherService,
        exploration_session_id: str,
        cancel_event: asyncio.Event,
        emit,
        extend_prompt: str,
    ) -> Dict[str, Any]:
        round_limit = int(os.getenv("EXPLORE_TASK_ROUNDS", "6"))
        round_steps = int(os.getenv("EXPLORE_TASK_ROUND_STEPS", "40"))
        total_steps = 0
        final_results = []
        last_signature = ""
        stalled_rounds = 0
        session_completion: Dict[str, Any] = {}

        for round_index in range(1, round_limit + 1):
            if cancel_event.is_set():
                emit("run.cancelled", reason="cancel_event")
                raise asyncio.CancelledError

            session_completion = dispatcher.finalize_session_if_ready(exploration_session_id)
            BrowserUseAgentExplorer._emit_session_snapshot(
                emit,
                dispatcher,
                exploration_session_id,
                session_completion,
                round=round_index,
            )
            snapshot = session_completion.get("snapshot", {})
            if session_completion.get("completed"):
                break

            current_page_key = str((snapshot.get("session") or {}).get("current_page_key") or "")
            assigned_task_result = (
                dispatcher.dispatch_next_task(exploration_session_id, current_page_key)
                if current_page_key
                else {"success": False, "has_task": False}
            )
            assigned_task = assigned_task_result.get("task") if assigned_task_result.get("has_task") else None
            if assigned_task:
                logger.info(
                    "[BrowserUseExplorer] task round assigned session=%s round=%s page=%s task_id=%s group=%s type=%s goal=%s attempts=%s/%s",
                    exploration_session_id,
                    round_index,
                    current_page_key,
                    assigned_task.get("task_id", ""),
                    assigned_task.get("task_group", ""),
                    assigned_task.get("task_type", ""),
                    assigned_task.get("task_goal", ""),
                    assigned_task.get("attempt_count", 0),
                    assigned_task.get("max_attempts", 0),
                )
                emit("task.assigned", task=assigned_task, round=round_index)
                task = build_single_task_round_prompt(
                    user_goal=goal,
                    env_info=env_info,
                    session_snapshot=snapshot,
                    assigned_task=assigned_task,
                )
                emit(
                    "task.started",
                    title=assigned_task.get("task_id", f"browser_use_task_round_{round_index}"),
                    engine="browser_use",
                )
            else:
                task = build_task_driven_exploration_prompt(
                    user_goal=goal,
                    env_info=env_info,
                    session_snapshot=snapshot,
                )
                emit("task.started", title=f"browser_use_exploration_round_{round_index}", engine="browser_use")
            history = await BrowserUseAgentExplorer._run_agent_round(
                agent_cls=agent_cls,
                task=task,
                llm=llm,
                browser_session=browser_session,
                controller=controller,
                cancel_event=cancel_event,
                extend_prompt=extend_prompt,
                max_steps=round_steps,
            )
            final_result, round_steps_used = BrowserUseAgentExplorer._extract_history(history)
            total_steps += round_steps_used
            if final_result:
                final_results.append(final_result)
            logger.info(
                "[BrowserUseExplorer] round completed session=%s round=%s page=%s assigned_task=%s steps=%s final_result_present=%s",
                exploration_session_id,
                round_index,
                current_page_key,
                bool(assigned_task),
                round_steps_used,
                bool(final_result),
            )

            session_completion = dispatcher.finalize_session_if_ready(exploration_session_id)
            BrowserUseAgentExplorer._emit_session_snapshot(
                emit,
                dispatcher,
                exploration_session_id,
                session_completion,
                round=round_index,
            )
            snapshot = session_completion.get("snapshot", {})
            if session_completion.get("completed"):
                break

            signature = json.dumps(
                {
                    "current_page_key": (snapshot.get("session") or {}).get("current_page_key", ""),
                    "page_count": snapshot.get("page_count", 0),
                    "frontier_size": snapshot.get("frontier_size", 0),
                    "navigation_count": snapshot.get("navigation_count", 0),
                    "current_page_status": (snapshot.get("current_page") or {}).get("meta", {}).get("status", ""),
                    "current_page_task_summary": (snapshot.get("current_page") or {}).get("task_status_summary", {}),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            if signature == last_signature:
                stalled_rounds += 1
            else:
                stalled_rounds = 0
                last_signature = signature
            if stalled_rounds >= 2:
                logger.warning(
                    "[BrowserUseExplorer] round stalled session=%s round=%s page=%s signature=%s",
                    exploration_session_id,
                    round_index,
                    (snapshot.get("session") or {}).get("current_page_key", ""),
                    signature,
                )
                emit("run.stalled", round=round_index, snapshot=snapshot)
                break

        return {
            "success": True,
            "final_result": "\n\n".join(item for item in final_results if item),
            "total_steps": total_steps,
            "session_completion": session_completion,
        }

    @staticmethod
    def _extract_history(history) -> tuple[str, int]:
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
        return final_result, total_steps

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
