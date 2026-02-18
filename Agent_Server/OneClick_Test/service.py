"""
一键测试 - 核心服务

LLM 编排：分析意图 → 查询数据库 → 获取环境 → 页面分析 → 生成用例 → 执行测试

特性：
- 停止功能：通过 asyncio.Event 取消正在运行的任务 + 关闭浏览器
- 浏览器复用：所有用例共享一个 BrowserSession
- 429 限流检测：遇到配额耗尽立即停止后续用例
- 循环检测：集成 LoopDetector 防止 Agent 陷入无限循环
- 自动切换：集成 ModelAutoSwitcher 在模型失败时自动切换
- Token 统计：按会话追踪 Token 使用量
"""
import json
import os
import time
import asyncio
import logging
import traceback
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session

from database.connection import (
    ExecutionCase, OneclickSession, Skill,
    ExecutionBatch, TestRecord, TestReport, BugReport
)
from llm.client import get_llm_client
from llm.auto_switch import get_auto_switcher, classify_failure_reason
from Api_request.prompts import (
    ONECLICK_INTENT_ANALYSIS_SYSTEM,
    ONECLICK_INTENT_ANALYSIS_USER_TEMPLATE,
    ONECLICK_GENERATE_CASES_SYSTEM,
    ONECLICK_GENERATE_CASES_USER_TEMPLATE,
)
from OneClick_Test.session import SessionManager
from OneClick_Test.skill_manager import SkillManager
from OneClick_Test.loop_detection import LoopDetector, LoopDetectionConfig

logger = logging.getLogger(__name__)


# ========== 全局运行状态管理 ==========
# session_id → { "cancel_event": asyncio.Event, "browser_session": BrowserSession|None, "loop_detector": LoopDetector|None }
_running_sessions: Dict[int, Dict[str, Any]] = {}


class OneClickService:
    """一键测试核心服务"""

    # ========== Phase 1: 启动会话 & 分析意图 ==========

    @staticmethod
    async def start_session(db: Session, user_input: str, skill_ids: List[int] = None) -> Dict:
        """
        启动一键测试会话
        1. 创建会话
        2. LLM 分析用户意图
        3. 从数据库查询相关用例
        4. 获取测试环境信息
        """
        # 创建会话
        session = SessionManager.create_session(db, user_input)
        session_id = session.id

        try:
            # 更新状态
            SessionManager.update_status(db, session, 'analyzing')
            SessionManager.add_message(db, session, 'assistant', '正在分析您的需求...')

            # 1. LLM 分析意图
            intent = await OneClickService._analyze_intent(user_input, db)
            logger.info(f"[OneClick] 意图分析: {intent}")

            # 2. 从数据库查询相关用例
            existing_cases = OneClickService._query_related_cases(db, intent)
            case_info = f"从数据库找到 {len(existing_cases)} 条相关用例" if existing_cases else "数据库中暂无相关用例"
            SessionManager.add_message(db, session, 'assistant', f'✅ {case_info}')

            # 3. 获取测试环境
            env_info = OneClickService._get_env_info()
            target_url = env_info.get('base_url', '')
            session.target_url = target_url
            session.login_info = json.dumps(env_info, ensure_ascii=False)

            env_msg = f"✅ 测试环境: {target_url}"
            SessionManager.add_message(db, session, 'assistant', env_msg)

            # 4. 保存 skill_ids
            if skill_ids:
                session.skill_ids = json.dumps(skill_ids)

            db.commit()

            # 5. 生成测试用例
            cases_result = await OneClickService._generate_test_cases(
                db, session, user_input, intent, existing_cases, env_info, skill_ids
            )

            return {
                "success": True,
                "session_id": session_id,
                "status": session.status,
                "data": {
                    "intent": intent,
                    "existing_cases_count": len(existing_cases),
                    "target_url": target_url,
                    "generated_cases": cases_result.get("cases", []),
                    "messages": SessionManager.get_messages(session),
                }
            }

        except Exception as e:
            logger.error(f"[OneClick] 启动失败: {e}\n{traceback.format_exc()}")
            session.status = 'failed'
            SessionManager.add_message(db, session, 'assistant', f'❌ 分析失败: {str(e)}')
            db.commit()
            return {"success": False, "session_id": session_id, "message": str(e)}

    # ========== Phase 2: 用户确认 & 执行测试 ==========

    @staticmethod
    async def confirm_and_execute(
        db: Session, session_id: int, confirmed_cases: List[Dict] = None
    ) -> Dict:
        """用户确认测试用例后执行"""
        session = SessionManager.get_session(db, session_id)
        if not session:
            return {"success": False, "message": "会话不存在"}

        if session.status not in ('cases_generated', 'confirmed'):
            return {"success": False, "message": f"当前状态 '{session.status}' 不允许执行"}

        try:
            # 使用用户确认的用例，或使用已生成的
            cases = confirmed_cases
            if not cases:
                cases = json.loads(session.generated_cases) if session.generated_cases else []

            if not cases:
                return {"success": False, "message": "没有可执行的测试用例"}

            session.confirmed_cases = json.dumps(cases, ensure_ascii=False)
            session.status = 'confirmed'
            db.commit()

            SessionManager.add_message(db, session, 'user', f'确认执行 {len(cases)} 条测试用例')
            SessionManager.update_status(db, session, 'executing')
            SessionManager.add_message(db, session, 'assistant', '🚀 开始执行测试...')

            # 执行测试
            result = await OneClickService._execute_tests(db, session, cases)

            # 更新会话
            session.execution_result = json.dumps(result, ensure_ascii=False)
            if result.get("success"):
                session.status = 'completed'
                summary = result.get("summary", {})
                msg = f"✅ 测试完成！通过 {summary.get('passed', 0)}/{summary.get('total', 0)} 条"
                if result.get("stopped"):
                    msg += "（已手动停止）"
                if result.get("rate_limited"):
                    msg += "（因 API 配额耗尽提前终止）"

                # 自动生成测试报告和 Bug 报告
                try:
                    report_info = await OneClickService._save_reports(
                        db, session, cases, result
                    )
                    if report_info.get("report_id"):
                        msg += f"\n📄 测试报告已生成 (ID: {report_info['report_id']})"
                    if report_info.get("bug_count", 0) > 0:
                        msg += f"\n🐛 已生成 {report_info['bug_count']} 条 Bug 报告"
                    # 邮件发送结果
                    email_info = report_info.get("email", {})
                    if email_info.get("success"):
                        msg += f"\n📧 {email_info.get('message', '邮件已发送')}"
                    elif email_info.get("message") and email_info["message"] not in ("未发送", "没有自动接收联系人", "未配置邮件服务"):
                        msg += f"\n📧 邮件发送失败: {email_info['message']}"
                except Exception as report_err:
                    logger.warning(f"[OneClick] 生成报告失败: {report_err}")
            else:
                session.status = 'failed'
                msg = f"❌ 执行失败: {result.get('message', '未知错误')}"

            SessionManager.add_message(db, session, 'assistant', msg)
            db.commit()

            return {
                "success": True,
                "session_id": session_id,
                "status": session.status,
                "data": {
                    "result": result,
                    "messages": SessionManager.get_messages(session),
                }
            }

        except Exception as e:
            logger.error(f"[OneClick] 执行失败: {e}\n{traceback.format_exc()}")
            session.status = 'failed'
            SessionManager.add_message(db, session, 'assistant', f'❌ 执行异常: {str(e)}')
            db.commit()
            return {"success": False, "session_id": session_id, "message": str(e)}
        finally:
            # 清理运行状态
            _running_sessions.pop(session_id, None)

    # ========== 内部方法 ==========

    @staticmethod
    async def _analyze_intent(user_input: str, db: Session) -> Dict:
        """LLM 分析用户意图"""
        llm = get_llm_client()

        # 获取数据库中已有的模块列表
        modules = db.query(ExecutionCase.module).distinct().all()
        module_list = [m[0] for m in modules if m[0]]

        system_prompt = ONECLICK_INTENT_ANALYSIS_SYSTEM

        user_prompt = ONECLICK_INTENT_ANALYSIS_USER_TEMPLATE.format(
            user_input=user_input,
            module_list=', '.join(module_list) if module_list else '暂无',
        )

        try:
            response = llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return llm.parse_json_response(response)
        except Exception as e:
            logger.warning(f"[OneClick] 意图分析失败: {e}")
            return {
                "target_module": user_input,
                "test_scope": user_input,
                "keywords": user_input.split(),
                "need_login": True,
                "test_type": "功能测试"
            }

    @staticmethod
    def _query_related_cases(db: Session, intent: Dict) -> List[Dict]:
        """从数据库查询相关用例"""
        keywords = intent.get("keywords", [])
        module = intent.get("target_module", "")

        query = db.query(ExecutionCase)

        # 按模块匹配
        if module:
            query = query.filter(
                ExecutionCase.module.like(f"%{module}%") |
                ExecutionCase.title.like(f"%{module}%") |
                ExecutionCase.keywords.like(f"%{module}%")
            )

        cases = query.limit(50).all()

        # 如果模块匹配没结果，用关键词
        if not cases and keywords:
            for kw in keywords:
                kw_cases = db.query(ExecutionCase).filter(
                    ExecutionCase.title.like(f"%{kw}%") |
                    ExecutionCase.keywords.like(f"%{kw}%") |
                    ExecutionCase.module.like(f"%{kw}%")
                ).limit(20).all()
                cases.extend(kw_cases)
            # 去重
            seen = set()
            unique = []
            for c in cases:
                if c.id not in seen:
                    seen.add(c.id)
                    unique.append(c)
            cases = unique[:50]

        return [
            {
                "id": c.id,
                "title": c.title,
                "module": c.module,
                "steps": c.steps,
                "expected": c.expected,
                "priority": c.priority,
                "test_data": c.test_data,
            }
            for c in cases
        ]

    @staticmethod
    def _get_env_info() -> Dict:
        """获取测试环境信息"""
        return {
            "base_url": os.getenv("API_BASE_URL", ""),
            "token": os.getenv("API_TOKEN", ""),
            "headless": os.getenv("HEADLESS", "false").lower() == "true",
        }

    @staticmethod
    async def _generate_test_cases(
        db: Session,
        session: OneclickSession,
        user_input: str,
        intent: Dict,
        existing_cases: List[Dict],
        env_info: Dict,
        skill_ids: List[int] = None,
    ) -> Dict:
        """LLM 生成测试用例"""
        llm = get_llm_client()

        # 构建上下文
        context_parts = []

        # 已有用例
        if existing_cases:
            context_parts.append("## 数据库中已有的相关用例：")
            for c in existing_cases[:20]:
                context_parts.append(f"- [{c['id']}] {c['title']} (模块: {c.get('module', 'N/A')})")
                if c.get('steps'):
                    context_parts.append(f"  步骤: {c['steps'][:200]}")

        # 环境信息
        context_parts.append(f"\n## 测试环境：")
        context_parts.append(f"- 目标地址: {env_info.get('base_url', 'N/A')}")

        # Skills 知识（从 MinIO 以便签形式加载）
        skills_notes = SkillManager.load_skills_as_notes(
            db, skill_ids=skill_ids, task=user_input
        )
        if skills_notes:
            context_parts.append(f"\n{skills_notes}")

        context = "\n".join(context_parts)

        system_prompt = ONECLICK_GENERATE_CASES_SYSTEM

        user_prompt = ONECLICK_GENERATE_CASES_USER_TEMPLATE.format(
            user_input=user_input,
            intent_json=json.dumps(intent, ensure_ascii=False),
            context=context,
        )

        try:
            SessionManager.add_message(db, session, 'assistant', '正在生成测试用例...')

            response = llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,
                max_tokens=8000,
                response_format={"type": "json_object"}
            )

            # 使用 Provider 感知的 JSON 解析
            result = llm.parse_json_response(response)

            cases = result.get("cases", [])
            summary = result.get("summary", "")

            # 保存到会话
            session.generated_cases = json.dumps(cases, ensure_ascii=False)
            SessionManager.update_status(db, session, 'cases_generated')
            SessionManager.add_message(
                db, session, 'assistant',
                f'✅ 已生成 {len(cases)} 条测试用例\n{summary}',
                extra={"type": "cases_generated", "count": len(cases)}
            )

            return {"cases": cases, "summary": summary}

        except Exception as e:
            logger.error(f"[OneClick] 生成用例失败: {e}")
            SessionManager.add_message(db, session, 'assistant', f'⚠️ 用例生成失败: {str(e)}')
            return {"cases": [], "summary": ""}

    @staticmethod
    async def _execute_tests(
        db: Session, session: OneclickSession, cases: List[Dict]
    ) -> Dict:
        """
        执行测试用例（使用 browser-use）

        关键改进：
        1. 所有用例共享一个 BrowserSession，不再每条用例都新建浏览器
        2. 通过 asyncio.Event 支持取消，stop_session() 可以真正停止执行
        3. 检测 429 限流错误，立即停止后续用例
        """
        results = []
        passed = 0
        failed = 0
        total = len(cases)
        start_time = time.time()
        stopped = False
        rate_limited = False

        env_info = json.loads(session.login_info) if session.login_info else {}
        target_url = session.target_url or env_info.get("base_url", "")

        # 注册取消事件
        cancel_event = asyncio.Event()
        session_id = session.id
        loop_detector = LoopDetector(LoopDetectionConfig(
            enabled=True,
            warning_threshold=3,
            critical_threshold=5,
            global_circuit_breaker=8,
        ))
        _running_sessions[session_id] = {
            "cancel_event": cancel_event,
            "browser_session": None,
            "loop_detector": loop_detector,
        }

        # 确保 auto_switcher 已加载
        switcher = get_auto_switcher()
        try:
            switcher.load_profiles_from_db()
        except Exception as e:
            logger.warning(f"[OneClick] 加载 auto_switcher 配置失败: {e}")

        # 创建共享的 BrowserSession
        shared_browser = None
        try:
            shared_browser = await OneClickService._create_shared_browser(env_info)
            _running_sessions[session_id]["browser_session"] = shared_browser
            logger.info(f"[OneClick] ✅ 共享浏览器已创建，开始执行 {total} 条用例")
        except Exception as e:
            logger.error(f"[OneClick] ❌ 创建共享浏览器失败: {e}")
            return {"success": False, "message": f"浏览器启动失败: {str(e)}"}

        try:
            for idx, case in enumerate(cases):
                # ===== 检查是否被取消 =====
                if cancel_event.is_set():
                    stopped = True
                    remaining = total - idx
                    SessionManager.add_message(
                        db, session, 'assistant',
                        f'⏹️ 已停止，跳过剩余 {remaining} 条用例'
                    )
                    logger.info(f"[OneClick] ⏹️ 会话 {session_id} 已被取消，跳过剩余 {remaining} 条")
                    break

                case_title = case.get("title", f"用例{idx+1}")
                SessionManager.add_message(
                    db, session, 'assistant',
                    f'⏳ [{idx+1}/{total}] 正在执行: {case_title}',
                    extra={"type": "executing", "index": idx}
                )

                try:
                    need_browser = case.get("need_browser", True)

                    if need_browser:
                        # 重置循环检测器（每条用例独立检测）
                        loop_detector.reset()

                        # ===== 用例间状态隔离：确保从目标页面开始 =====
                        if shared_browser and idx > 0:
                            try:
                                await OneClickService._reset_browser_state(
                                    shared_browser, target_url
                                )
                            except Exception as reset_err:
                                logger.warning(f"[OneClick] ⚠️ 重置浏览器状态失败: {reset_err}")

                        # 使用共享浏览器执行
                        result = await OneClickService._execute_browser_test(
                            case, target_url, env_info, db,
                            browser_session=shared_browser,
                            cancel_event=cancel_event,
                            loop_detector=loop_detector,
                            session_id=session_id,
                        )
                    else:
                        result = {"status": "skip", "message": "非浏览器测试，跳过"}

                    status = result.get("status", "error")

                    # ===== 检测 429 限流 =====
                    if status == "rate_limited":
                        rate_limited = True
                        failed += 1
                        results.append({
                            "index": idx + 1,
                            "title": case_title,
                            "status": "rate_limited",
                            "message": result.get("message", "API 配额耗尽"),
                            "duration": result.get("duration", 0),
                            "steps": result.get("steps", 0),
                        })
                        remaining = total - idx - 1
                        SessionManager.add_message(
                            db, session, 'assistant',
                            f'🚫 [{idx+1}/{total}] {case_title}: API 配额耗尽 (429)，停止执行剩余 {remaining} 条用例',
                            extra={"type": "rate_limited"}
                        )
                        logger.warning(f"[OneClick] 🚫 429 限流，停止后续用例")
                        break

                    if status == "pass":
                        passed += 1
                        emoji = "✅"
                    elif status == "fail":
                        failed += 1
                        emoji = "❌"
                    else:
                        failed += 1
                        emoji = "⚠️"

                    results.append({
                        "index": idx + 1,
                        "title": case_title,
                        "status": status,
                        "message": result.get("message", ""),
                        "duration": result.get("duration", 0),
                        "steps": result.get("steps", 0),
                    })

                    SessionManager.add_message(
                        db, session, 'assistant',
                        f'{emoji} [{idx+1}/{total}] {case_title}: {status}',
                        extra={"type": "case_result", "index": idx, "status": status}
                    )

                except Exception as e:
                    failed += 1
                    error_msg = str(e)

                    # 检查异常中是否包含 429
                    if _is_rate_limit_error(error_msg):
                        rate_limited = True
                        results.append({
                            "index": idx + 1,
                            "title": case_title,
                            "status": "rate_limited",
                            "message": error_msg,
                        })
                        SessionManager.add_message(
                            db, session, 'assistant',
                            f'🚫 [{idx+1}/{total}] {case_title}: API 配额耗尽，停止执行'
                        )
                        break

                    results.append({
                        "index": idx + 1,
                        "title": case_title,
                        "status": "error",
                        "message": error_msg,
                    })
                    SessionManager.add_message(
                        db, session, 'assistant',
                        f'❌ [{idx+1}/{total}] {case_title}: 执行异常 - {error_msg}'
                    )

            total_duration = int(time.time() - start_time)

            return {
                "success": True,
                "stopped": stopped,
                "rate_limited": rate_limited,
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "executed": len(results),
                    "duration": total_duration,
                },
                "results": results,
                "loop_stats": loop_detector.get_stats(),
            }

        finally:
            # ===== 关闭共享浏览器 =====
            if shared_browser:
                try:
                    logger.info(f"[OneClick] 正在关闭共享浏览器...")
                    # 使用 kill() 强制关闭，因为 keep_alive=True 时 stop() 不会真正关闭
                    await shared_browser.kill()
                    logger.info(f"[OneClick] ✅ 共享浏览器已关闭")
                except Exception as e:
                    logger.warning(f"[OneClick] ⚠️ 关闭浏览器异常: {e}")
            # 清理运行状态
            _running_sessions.pop(session_id, None)

    @staticmethod
    async def _create_shared_browser(env_info: Dict):
        """创建共享的 BrowserSession（所有用例复用）"""
        from browser_use import BrowserSession
        from Execute_test.service import find_chrome_path

        headless = env_info.get("headless", False)
        chrome_path = os.getenv('BROWSER_PATH', '').strip() or find_chrome_path()
        disable_security = os.getenv('DISABLE_SECURITY', 'false').lower() == 'true'

        browser_session = BrowserSession(
            headless=headless,
            disable_security=disable_security,
            executable_path=chrome_path if chrome_path else None,
            minimum_wait_page_load_time=0.5,
            wait_between_actions=0.3,
            keep_alive=True,
        )

        logger.info(f"[OneClick] 🚀 创建共享浏览器: headless={headless}, chrome={chrome_path or '自动'}")
        return browser_session

    @staticmethod
    async def _reset_browser_state(browser_session, target_url: str):
        """
        用例间状态隔离：清除 cookies + 导航到目标页面

        解决问题：用例1登录成功后，用例2（如错误密码测试）会在已登录状态下开始，
        导致测试结果不准确。

        策略：
        1. 获取当前 browser context，清除所有 cookies
        2. 导航到目标 URL，确保从干净状态开始
        """
        import asyncio

        try:
            context = await browser_session.get_browser_context()

            # 清除所有 cookies（确保登录态被清除）
            await context.clear_cookies()
            logger.debug("[OneClick] 🧹 已清除浏览器 cookies")

            # 获取当前页面并导航到目标 URL
            pages = context.pages
            if pages:
                page = pages[0]
                await page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(0.5)
                logger.debug(f"[OneClick] 🔄 已导航到目标页面: {target_url}")
            else:
                logger.warning("[OneClick] ⚠️ 没有可用的页面，跳过导航")

        except Exception as e:
            logger.warning(f"[OneClick] ⚠️ 重置浏览器状态异常: {e}")
            # 不抛出异常，允许测试继续

    @staticmethod
    async def _execute_browser_test(
        case: Dict, target_url: str, env_info: Dict, db: Session,
        browser_session=None,
        cancel_event: asyncio.Event = None,
        loop_detector: LoopDetector = None,
        session_id: int = None,
    ) -> Dict:
        """
        使用 browser-use 执行单条浏览器测试

        特性：
        - 接受外部传入的 browser_session（共享浏览器）
        - 接受 cancel_event 用于中途取消
        - 检测 429 限流错误并返回特殊状态
        - 集成循环检测，防止 Agent 陷入无限循环
        - 集成自动切换，模型失败时自动切换
        """
        start = time.time()

        try:
            from llm import get_active_browser_use_llm, FailoverChatModel, get_auto_switcher
            from browser_use import Agent
            from Api_request.prompts import BROWSER_USE_CHINESE_SYSTEM

            raw_llm = get_active_browser_use_llm()
            # 用 FailoverChatModel 包装，实现 429 时自动切换模型
            switcher = get_auto_switcher()
            if switcher.enabled and len(switcher._profiles) > 1:
                llm = FailoverChatModel(raw_llm, switcher)
                logger.info("[OneClick] ✅ 已启用 FailoverChatModel，支持 429 自动切换")
            else:
                llm = raw_llm
                logger.info("[OneClick] ⚠️ 自动切换未启用或仅有1个模型，使用原始 LLM")
            max_steps = int(os.getenv("MAX_STEPS", "100"))
            max_actions = int(os.getenv("MAX_ACTIONS", "10"))
            use_vision = os.getenv("LLM_USE_VISION", "false").lower() == "true"

            # 构建任务描述
            steps_text = ""
            steps = case.get("steps", [])
            if isinstance(steps, list):
                steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
            elif isinstance(steps, str):
                steps_text = steps

            test_data = case.get("test_data", {})
            data_text = ""
            if test_data:
                data_text = f"\n测试数据: {json.dumps(test_data, ensure_ascii=False)}"

            task = f"""【一键测试任务】
目标地址: {target_url}
测试用例: {case.get('title', '')}
测试步骤:
{steps_text}
预期结果: {case.get('expected', '')}
{data_text}

请按照步骤执行测试，并验证预期结果。"""

            # Skills 便签注入（从 MinIO 加载）
            skills_notes = SkillManager.load_skills_as_notes(db, task=task)
            extend_prompt = BROWSER_USE_CHINESE_SYSTEM
            if skills_notes:
                extend_prompt += f"\n\n{skills_notes}"

            # 如果有循环检测器，在 system prompt 中注入提示
            if loop_detector:
                extend_prompt += (
                    "\n\n⚠️ 循环检测已启用：如果你发现自己在重复执行相同的操作且没有进展，"
                    "请立即改变策略或标记任务为失败。不要反复尝试同一个操作。"
                )

            # 创建 Agent（复用共享浏览器）
            agent = Agent(
                task=task,
                llm=llm,
                browser_session=browser_session,
                use_vision=use_vision,
                max_actions_per_step=max_actions,
                extend_system_message=extend_prompt,
            )

            # 执行测试（带取消检测）
            history = await agent.run(max_steps=max_steps)

            # 检查执行后是否被取消
            if cancel_event and cancel_event.is_set():
                return {
                    "status": "cancelled",
                    "message": "测试已被手动停止",
                    "duration": int(time.time() - start),
                    "steps": 0,
                }

            duration = int(time.time() - start)

            # 分析结果
            final_result = history.final_result() if hasattr(history, 'final_result') else ""

            # 判断成功/失败
            status = "pass"
            if hasattr(history, 'has_errors') and history.has_errors():
                status = "fail"
            elif final_result and isinstance(final_result, str):
                if any(kw in final_result.lower() for kw in ['fail', '失败', 'error', '错误']):
                    status = "fail"

            total_steps = len(history.history) if hasattr(history, 'history') else 0

            # 收集循环检测统计
            loop_stats = loop_detector.get_stats() if loop_detector else {}

            return {
                "status": status,
                "message": final_result if final_result else ("测试通过" if status == "pass" else "测试失败"),
                "duration": duration,
                "steps": total_steps,
                "loop_stats": loop_stats,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[OneClick] 浏览器测试失败: {error_msg}")

            # 检测 429 限流
            if _is_rate_limit_error(error_msg):
                # 尝试自动切换模型
                try:
                    switcher = get_auto_switcher()
                    if switcher.enabled:
                        reason = classify_failure_reason(e)
                        new_id = switcher.mark_failure(
                            switcher._current_model_id or 0, reason
                        )
                        if new_id:
                            logger.info(f"[OneClick] 🔄 模型已自动切换到 ID={new_id}")
                except Exception as switch_err:
                    logger.warning(f"[OneClick] 自动切换失败: {switch_err}")

                return {
                    "status": "rate_limited",
                    "message": f"API 配额耗尽: {error_msg}",
                    "duration": int(time.time() - start),
                    "steps": 0,
                }

            # 其他错误也尝试标记到 auto_switcher
            try:
                switcher = get_auto_switcher()
                if switcher.enabled:
                    reason = classify_failure_reason(e)
                    switcher.mark_failure(
                        switcher._current_model_id or 0, reason
                    )
            except Exception:
                pass

            return {
                "status": "error",
                "message": error_msg,
                "duration": int(time.time() - start),
                "steps": 0,
            }

    # ========== 自动生成报告 ==========

    @staticmethod
    async def _save_reports(
        db: Session, session: OneclickSession,
        cases: List[Dict], result: Dict
    ) -> Dict:
        """
        执行完成后自动生成测试报告 + Bug 报告

        - 测试报告：保存到 test_reports 表，在 /report/run 页面可查看
        - Bug 报告：对失败/错误用例，保存到 bug_reports 表，在 /report/bug 页面可查看
        """
        from database.connection import TestReport, BugReport

        summary = result.get("summary", {})
        results_list = result.get("results", [])
        report_id = None
        bug_count = 0

        # ---- 1. 生成测试报告 ----
        try:
            pass_rate = round(
                summary.get("passed", 0) / max(summary.get("total", 1), 1) * 100, 2
            )

            # 构建报告详情（Markdown）
            details_lines = [
                f"# 一键测试报告",
                f"",
                f"## 测试概览",
                f"- 会话 ID: {session.id}",
                f"- 用户需求: {session.user_input}",
                f"- 目标地址: {session.target_url or '-'}",
                f"- 总用例数: {summary.get('total', 0)}",
                f"- 通过: {summary.get('passed', 0)}",
                f"- 失败: {summary.get('failed', 0)}",
                f"- 通过率: {pass_rate}%",
                f"- 总耗时: {summary.get('duration', 0)} 秒",
                f"",
                f"## 用例执行详情",
                f"",
            ]

            for r in results_list:
                status = r.get("status", "unknown")
                icon = "✅" if status == "pass" else "❌" if status in ("fail", "error") else "⚠️"
                details_lines.append(f"### {icon} {r.get('index', '')}. {r.get('title', '')}")
                details_lines.append(f"- 状态: {status}")
                details_lines.append(f"- 耗时: {r.get('duration', 0)} 秒")
                details_lines.append(f"- 步数: {r.get('steps', 0)}")
                if r.get("message"):
                    # 截断过长的消息
                    msg_text = r["message"][:500]
                    details_lines.append(f"- 结果: {msg_text}")
                details_lines.append("")

            report_details = "\n".join(details_lines)

            report = TestReport(
                title=f"一键测试_{session.user_input[:30]}_{datetime.now().strftime('%m%d_%H%M')}",
                summary={
                    "total": summary.get("total", 0),
                    "pass": summary.get("passed", 0),
                    "fail": summary.get("failed", 0),
                    "pass_rate": pass_rate,
                    "duration": summary.get("duration", 0),
                    "total_steps": sum(r.get("steps", 0) for r in results_list),
                    "execution_mode": "一键测试",
                    "session_id": session.id,
                },
                details=report_details,
                format_type="markdown",
                total_steps=sum(r.get("steps", 0) for r in results_list),
            )
            db.add(report)
            db.flush()
            report_id = report.id
            logger.info(f"[OneClick] 📄 测试报告已保存: ID={report_id}")
        except Exception as e:
            logger.warning(f"[OneClick] 保存测试报告失败: {e}")

        # ---- 2. 为失败用例生成 Bug 报告 ----
        for r in results_list:
            status = r.get("status", "")
            if status not in ("fail", "error"):
                continue

            try:
                idx = r.get("index", 0) - 1
                case = cases[idx] if 0 <= idx < len(cases) else {}

                # 根据状态判断严重程度
                if status == "error":
                    severity = "一级"
                    error_type = "系统错误"
                elif "rate_limited" in r.get("message", ""):
                    severity = "三级"
                    error_type = "环境问题"
                else:
                    severity = "二级"
                    error_type = "功能错误"

                steps = case.get("steps", [])
                if isinstance(steps, list):
                    reproduce_text = json.dumps(steps, ensure_ascii=False)
                else:
                    reproduce_text = str(steps)

                bug = BugReport(
                    test_record_id=None,
                    bug_name=f"[一键测试] {r.get('title', '未知用例')}",
                    test_case_id=None,
                    location_url=session.target_url or "",
                    error_type=error_type,
                    severity_level=severity,
                    reproduce_steps=reproduce_text,
                    result_feedback=r.get("message", "")[:2000],
                    expected_result=case.get("expected", ""),
                    actual_result=r.get("message", "")[:1000],
                    status="待处理",
                    description=f"一键测试会话 #{session.id} 中用例 [{r.get('title', '')}] 执行{status}",
                    case_type="功能测试",
                    execution_mode="一键测试",
                )
                db.add(bug)
                bug_count += 1
            except Exception as e:
                logger.warning(f"[OneClick] 保存 Bug 报告失败: {e}")

        if bug_count > 0:
            logger.info(f"[OneClick] 🐛 已生成 {bug_count} 条 Bug 报告")

        try:
            db.commit()
        except Exception as e:
            logger.error(f"[OneClick] 提交报告到数据库失败: {e}")
            db.rollback()

        # ---- 3. 自动发送邮件给 auto_receive_bug 联系人 ----
        email_result = {"success": False, "message": "未发送"}
        try:
            email_result = OneClickService._send_oneclick_report_email(
                db, session, summary, results_list, cases,
                report_id, bug_count
            )
        except Exception as e:
            logger.warning(f"[OneClick] 自动发送邮件失败: {e}")
            email_result = {"success": False, "message": str(e)}

        return {
            "report_id": report_id,
            "bug_count": bug_count,
            "email": email_result,
        }

    @staticmethod
    def _send_oneclick_report_email(
        db: Session,
        session: OneclickSession,
        summary: Dict,
        results_list: List[Dict],
        cases: List[Dict],
        report_id: Optional[int],
        bug_count: int,
    ) -> Dict:
        """
        将测试报告 + Bug 报告整合为一封邮件，发送给 auto_receive_bug=1 的联系人

        仅在一键测试功能中触发，整合两种报告类型。
        """
        from database.connection import Contact, EmailConfig, EmailRecord

        # 查询自动接收 Bug 的联系人
        contacts = db.query(Contact).filter(Contact.auto_receive_bug == 1).all()
        if not contacts:
            logger.info("[OneClick] 📧 没有自动接收 Bug 的联系人，跳过邮件发送")
            return {"success": False, "message": "没有自动接收联系人"}

        # 获取激活的邮件配置
        email_config = db.query(EmailConfig).filter(EmailConfig.is_active == 1).first()
        if not email_config:
            logger.info("[OneClick] 📧 未配置邮件服务，跳过邮件发送")
            return {"success": False, "message": "未配置邮件服务"}

        # 构建邮件
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        duration = summary.get("duration", 0)
        pass_rate = round(passed / max(total, 1) * 100, 1)

        subject = f"[一键测试] {session.user_input[:40]} - 通过 {passed}/{total} - {now_str}"

        # 构建用例结果表格行
        case_rows = ""
        bug_rows = ""
        for r in results_list:
            status = r.get("status", "unknown")
            status_text = "✅ 通过" if status == "pass" else "❌ 失败" if status == "fail" else "⚠️ 错误" if status == "error" else "🚫 限流"
            status_color = "#16a34a" if status == "pass" else "#dc2626" if status in ("fail", "error") else "#d97706"
            msg = (r.get("message", "") or "")[:150]

            case_rows += f"""<tr>
                <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;">{r.get('index', '')}</td>
                <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;">{r.get('title', '')}</td>
                <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;color:{status_color};font-weight:600;">{status_text}</td>
                <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;">{r.get('duration', 0)}s</td>
                <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:12px;color:#64748b;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{msg}</td>
            </tr>"""

            # Bug 详情行（仅失败/错误用例）
            if status in ("fail", "error"):
                idx = r.get("index", 0) - 1
                case = cases[idx] if 0 <= idx < len(cases) else {}
                expected = (case.get("expected", "") or "")[:100]
                severity = "一级(系统错误)" if status == "error" else "二级(功能错误)"
                sev_color = "#dc2626" if status == "error" else "#ea580c"

                bug_rows += f"""<tr>
                    <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;">{r.get('title', '')}</td>
                    <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:13px;color:{sev_color};font-weight:600;">{severity}</td>
                    <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:12px;">{expected}</td>
                    <td style="padding:10px 12px;border-bottom:1px solid #f1f5f9;font-size:12px;color:#dc2626;">{msg}</td>
                </tr>"""

        # Bug 报告区块（仅在有 Bug 时显示）
        bug_section = ""
        if bug_count > 0 and bug_rows:
            bug_section = f"""
            <div style="margin-top:8px;">
                <h2 style="font-size:16px;font-weight:600;color:#1e293b;margin:0 0 12px;">
                    🐛 Bug 报告（{bug_count} 条）
                </h2>
                <table width="100%" style="border-collapse:collapse;">
                    <tr style="background:#fef2f2;">
                        <th style="padding:10px 12px;text-align:left;font-size:12px;color:#991b1b;font-weight:600;">用例名称</th>
                        <th style="padding:10px 12px;text-align:left;font-size:12px;color:#991b1b;font-weight:600;">严重程度</th>
                        <th style="padding:10px 12px;text-align:left;font-size:12px;color:#991b1b;font-weight:600;">预期结果</th>
                        <th style="padding:10px 12px;text-align:left;font-size:12px;color:#991b1b;font-weight:600;">实际结果</th>
                    </tr>
                    {bug_rows}
                </table>
            </div>"""

        # 完整 HTML 邮件
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:'Helvetica Neue',Arial,'PingFang SC','Microsoft YaHei',sans-serif;">
<div style="max-width:720px;margin:20px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
  <div style="background:linear-gradient(135deg,#007857,#00a67e);padding:28px 36px;color:#fff;">
    <h1 style="margin:0;font-size:20px;font-weight:600;">一键测试报告</h1>
    <p style="margin:6px 0 0;font-size:13px;opacity:0.85;">{now_str} · 会话 #{session.id} · {session.user_input[:50]}</p>
  </div>

  <div style="padding:24px 36px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
      <tr>
        <td style="width:25%;text-align:center;padding:16px 8px;background:#f0fdf4;border-radius:8px;">
          <div style="font-size:28px;font-weight:700;color:#16a34a;">{pass_rate}%</div>
          <div style="font-size:12px;color:#666;margin-top:4px;">通过率</div>
        </td>
        <td style="width:8px;"></td>
        <td style="width:25%;text-align:center;padding:16px 8px;background:#f0fdf4;border-radius:8px;">
          <div style="font-size:28px;font-weight:700;color:#007857;">{passed}/{total}</div>
          <div style="font-size:12px;color:#666;margin-top:4px;">通过/总计</div>
        </td>
        <td style="width:8px;"></td>
        <td style="width:25%;text-align:center;padding:16px 8px;background:{'#fef2f2' if failed > 0 else '#f0fdf4'};border-radius:8px;">
          <div style="font-size:28px;font-weight:700;color:{'#dc2626' if failed > 0 else '#16a34a'};">{failed}</div>
          <div style="font-size:12px;color:#666;margin-top:4px;">失败</div>
        </td>
        <td style="width:8px;"></td>
        <td style="width:25%;text-align:center;padding:16px 8px;background:#eff6ff;border-radius:8px;">
          <div style="font-size:28px;font-weight:700;color:#2563eb;">{duration}s</div>
          <div style="font-size:12px;color:#666;margin-top:4px;">耗时</div>
        </td>
      </tr>
    </table>

    <div style="border-top:1px solid #e5e7eb;padding-top:20px;">
      <h2 style="font-size:16px;font-weight:600;color:#1e293b;margin:0 0 12px;">📋 用例执行详情</h2>
      <table width="100%" style="border-collapse:collapse;">
        <tr style="background:#f8fafc;">
          <th style="padding:10px 12px;text-align:left;font-size:12px;color:#64748b;font-weight:600;">#</th>
          <th style="padding:10px 12px;text-align:left;font-size:12px;color:#64748b;font-weight:600;">用例名称</th>
          <th style="padding:10px 12px;text-align:left;font-size:12px;color:#64748b;font-weight:600;">状态</th>
          <th style="padding:10px 12px;text-align:left;font-size:12px;color:#64748b;font-weight:600;">耗时</th>
          <th style="padding:10px 12px;text-align:left;font-size:12px;color:#64748b;font-weight:600;">结果说明</th>
        </tr>
        {case_rows}
      </table>
    </div>

    {bug_section}

    <div style="margin-top:20px;padding:12px 16px;background:#f8fafc;border-radius:8px;font-size:12px;color:#94a3b8;">
      测试报告 ID: {report_id or '-'} · Bug 报告: {bug_count} 条 · 目标地址: {session.target_url or '-'}
    </div>
  </div>

  <div style="background:#f8fafc;padding:14px 36px;text-align:center;font-size:12px;color:#94a3b8;">
    此邮件由 AI 测试平台（一键测试）自动生成发送
  </div>
</div>
</body></html>"""

        # 发送邮件
        sender = email_config.sender_email
        provider = email_config.provider or 'resend'
        recipients_result = []
        success_count = 0
        failed_count_email = 0

        for contact in contacts:
            to_email = (
                email_config.test_email
                if email_config.test_mode == 1 and email_config.test_email
                else contact.email
            )
            try:
                if provider == 'aliyun':
                    from Build_Report.router import _send_via_aliyun
                    _send_via_aliyun(
                        access_key_id=email_config.api_key,
                        access_key_secret=email_config.secret_key,
                        sender=sender,
                        to_email=to_email,
                        subject=subject,
                        html_body=html,
                    )
                else:
                    import resend
                    resend.api_key = email_config.api_key
                    resend.Emails.send({
                        "from": sender,
                        "to": [to_email],
                        "subject": subject,
                        "html": html,
                    })
                success_count += 1
                recipients_result.append({
                    "name": contact.name, "email": contact.email, "status": "success"
                })
                logger.info(f"[OneClick] 📧 邮件已发送: {contact.name} <{to_email}>")
            except Exception as e:
                failed_count_email += 1
                recipients_result.append({
                    "name": contact.name, "email": contact.email,
                    "status": "failed", "error": str(e)
                })
                logger.warning(f"[OneClick] 📧 邮件发送失败: {contact.name} - {e}")

        # 记录发送历史
        status = (
            'success' if failed_count_email == 0
            else ('partial' if success_count > 0 else 'failed')
        )
        try:
            record = EmailRecord(
                subject=subject,
                recipients=recipients_result,
                status=status,
                success_count=success_count,
                failed_count=failed_count_email,
                total_count=len(contacts),
                email_type='oneclick_report',
                content_summary=f"一键测试报告: 通过 {passed}/{total}, Bug {bug_count} 条",
            )
            db.add(record)
            db.commit()
        except Exception as e:
            logger.warning(f"[OneClick] 保存邮件记录失败: {e}")
            db.rollback()

        logger.info(
            f"[OneClick] 📧 邮件发送完成: 成功 {success_count}, 失败 {failed_count_email}"
        )
        return {
            "success": success_count > 0,
            "message": f"已发送 {success_count}/{len(contacts)} 位联系人",
            "success_count": success_count,
            "failed_count": failed_count_email,
        }

    # ========== 会话查询 ==========

    @staticmethod
    def get_session_detail(db: Session, session_id: int) -> Optional[Dict]:
        """获取会话详情"""
        session = SessionManager.get_session(db, session_id)
        if not session:
            return None

        return {
            "id": session.id,
            "user_input": session.user_input,
            "status": session.status,
            "target_url": session.target_url,
            "login_info": json.loads(session.login_info) if session.login_info else None,
            "page_analysis": json.loads(session.page_analysis) if session.page_analysis else None,
            "generated_cases": json.loads(session.generated_cases) if session.generated_cases else [],
            "confirmed_cases": json.loads(session.confirmed_cases) if session.confirmed_cases else [],
            "execution_result": json.loads(session.execution_result) if session.execution_result else None,
            "messages": SessionManager.get_messages(session),
            "runtime_stats": SessionManager.get_runtime_stats(session_id),
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        }

    @staticmethod
    async def stop_session(db: Session, session_id: int) -> Dict:
        """
        停止会话 — 真正取消正在运行的任务

        改进：
        1. 设置 cancel_event 通知执行循环停止
        2. 关闭正在运行的浏览器实例
        3. 更新数据库状态
        """
        session = SessionManager.get_session(db, session_id)
        if not session:
            return {"success": False, "message": "会话不存在"}

        if session.status in ('completed', 'failed'):
            return {"success": False, "message": "会话已结束"}

        # 1. 设置取消信号
        running = _running_sessions.get(session_id)
        if running:
            cancel_event = running.get("cancel_event")
            if cancel_event:
                cancel_event.set()
                logger.info(f"[OneClick] ⏹️ 已发送取消信号: session_id={session_id}")

            # 2. 关闭浏览器
            browser = running.get("browser_session")
            if browser:
                try:
                    await browser.kill()
                    logger.info(f"[OneClick] ✅ 浏览器已强制关闭: session_id={session_id}")
                except Exception as e:
                    logger.warning(f"[OneClick] ⚠️ 关闭浏览器异常: {e}")
        else:
            logger.info(f"[OneClick] ℹ️ 会话 {session_id} 没有正在运行的任务")

        # 3. 更新数据库状态
        session.status = 'failed'
        SessionManager.add_message(db, session, 'assistant', '⏹️ 测试已手动停止')
        db.commit()
        return {"success": True, "message": "已停止"}


# ========== 工具函数 ==========

def _is_rate_limit_error(error_msg: str) -> bool:
    """检测是否为 429 限流错误"""
    lower = error_msg.lower()
    return any(kw in lower for kw in [
        '429', 'rate limit', 'rate_limit', 'quota',
        'exceeded', 'too many requests',
        'modelratelimiterror',
    ])
