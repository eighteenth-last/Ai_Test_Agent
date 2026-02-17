"""
一键测试 - 核心服务

LLM 编排：分析意图 → 查询数据库 → 获取环境 → 页面分析 → 生成用例 → 执行测试

修复：
- 停止功能：通过 asyncio.Event 取消正在运行的任务 + 关闭浏览器
- 浏览器复用：所有用例共享一个 BrowserSession
- 429 限流检测：遇到配额耗尽立即停止后续用例
"""
import json
import os
import re
import time
import asyncio
import logging
import traceback
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session

from database.connection import (
    ExecutionCase, OneclickSession, Skill,
    ExecutionBatch, TestRecord
)
from llm.client import get_llm_client
from OneClick_Test.session import SessionManager
from OneClick_Test.skill_manager import SkillManager

logger = logging.getLogger(__name__)


# ========== 全局运行状态管理 ==========
# session_id → { "cancel_event": asyncio.Event, "browser_session": BrowserSession|None }
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

        system_prompt = """你是一个智能测试助手。分析用户的测试需求，提取关键信息。
返回 JSON 格式：
{
    "target_module": "目标测试模块名称（如：课程作业、登录、用户管理）",
    "test_scope": "测试范围描述",
    "keywords": ["关键词1", "关键词2"],
    "need_login": true/false,
    "test_type": "功能测试/接口测试/全面测试"
}"""

        user_prompt = f"""用户输入: {user_input}

数据库中已有的测试模块: {', '.join(module_list) if module_list else '暂无'}

请分析用户的测试意图。"""

        try:
            response = llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            # 清理 markdown
            cleaned = response.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```\w*\n?', '', cleaned)
                cleaned = re.sub(r'\n?```$', '', cleaned)
            return json.loads(cleaned)
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

        system_prompt = """你是一个专业的自动化测试专家。根据用户需求和已有信息，生成完整的测试用例列表。

每条测试用例包含：
- title: 用例标题
- module: 所属模块
- steps: 测试步骤（数组）
- expected: 预期结果
- priority: 优先级 (1-4)
- test_data: 测试数据（JSON对象，如账号密码等）
- need_browser: 是否需要浏览器执行 (true/false)

返回 JSON 格式：
{
    "cases": [
        {
            "title": "...",
            "module": "...",
            "steps": ["步骤1", "步骤2"],
            "expected": "...",
            "priority": "3",
            "test_data": {},
            "need_browser": true
        }
    ],
    "summary": "测试计划摘要"
}

要求：
1. 用例要全面覆盖功能的正常流程和异常场景
2. 步骤描述要具体、可执行
3. 如果数据库中已有相关用例，参考但不完全复制
4. 所有内容使用中文"""

        user_prompt = f"""用户需求: {user_input}

意图分析: {json.dumps(intent, ensure_ascii=False)}

{context}

请生成完整的测试用例列表。"""

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

            # 解析
            cleaned = response.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```\w*\n?', '', cleaned)
                cleaned = re.sub(r'\n?```$', '', cleaned)
            result = json.loads(cleaned)

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
        _running_sessions[session_id] = {
            "cancel_event": cancel_event,
            "browser_session": None,
        }

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
                        # 使用共享浏览器执行
                        result = await OneClickService._execute_browser_test(
                            case, target_url, env_info, db,
                            browser_session=shared_browser,
                            cancel_event=cancel_event,
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
            }

        finally:
            # ===== 关闭共享浏览器 =====
            if shared_browser:
                try:
                    logger.info(f"[OneClick] 正在关闭共享浏览器...")
                    await shared_browser.stop()
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
        )

        logger.info(f"[OneClick] 🚀 创建共享浏览器: headless={headless}, chrome={chrome_path or '自动'}")
        return browser_session

    @staticmethod
    async def _execute_browser_test(
        case: Dict, target_url: str, env_info: Dict, db: Session,
        browser_session=None,
        cancel_event: asyncio.Event = None,
    ) -> Dict:
        """
        使用 browser-use 执行单条浏览器测试

        改进：
        - 接受外部传入的 browser_session（共享浏览器）
        - 接受 cancel_event 用于中途取消
        - 检测 429 限流错误并返回特殊状态
        """
        start = time.time()

        try:
            from llm import get_active_browser_use_llm
            from browser_use import Agent
            from Api_request.prompts import BROWSER_USE_CHINESE_SYSTEM

            llm = get_active_browser_use_llm()
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

            return {
                "status": status,
                "message": final_result if final_result else ("测试通过" if status == "pass" else "测试失败"),
                "duration": duration,
                "steps": total_steps,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[OneClick] 浏览器测试失败: {error_msg}")

            # 检测 429 限流
            if _is_rate_limit_error(error_msg):
                return {
                    "status": "rate_limited",
                    "message": f"API 配额耗尽: {error_msg}",
                    "duration": int(time.time() - start),
                    "steps": 0,
                }

            return {
                "status": "error",
                "message": error_msg,
                "duration": int(time.time() - start),
                "steps": 0,
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
                    await browser.stop()
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
