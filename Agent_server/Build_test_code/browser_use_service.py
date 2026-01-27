"""
Browser-Use 执行服务 - 升级版本

使用 browser-use 0.11.1，支持:
- Token 统计和成本计算
- 自动截图保存
- 增强的错误处理

作者: Ai_Test_Agent Team
版本: 3.0 (browser-use 0.11.1)
"""

import asyncio
import json
import time
import os
import re
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import ExecutionCase, ExecutionBatch, TestRecord, TestCase, TestResult
from Build_test_code.task_manager import get_task_manager
import uuid
from Build_test_code.custom_actions import register_custom_actions
from Api_request.prompts import BROWSER_USE_CHINESE_SYSTEM, BROWSER_USE_BATCH_CHINESE_SYSTEM, BATCH_TEST_TASK_TEMPLATE

# browser-use 0.11.1 imports
from browser_use import Agent, BrowserSession, BrowserProfile
from browser_use.tools.service import Tools

# Token 统计服务
from utils.token_tracker import TokenStatisticsService
from browser_use_core.browser_use_agent import BrowserUseAgent, ScreenshotManager, BUG_IMG_SAVE_PATH

load_dotenv()


# 答题相关关键词
ANSWER_KEYWORDS = [
    '错题再练', '错题集', '练习', '答题', '做题',
    '完成题目', '完成所有题目', '提交答案',
    '开始答题', '进入练习', '开始练习',
    'practice', 'exercise', 'answer', 'question',
]


# 批量执行任务ID前缀
BATCH_TASK_ID_PREFIX = 10000000


def generate_batch_id(mode: str = 'single') -> str:
    """生成执行批次号
    
    Args:
        mode: 执行模式，'single' 或 'batch'
    
    Returns:
        批次号，格式: {MODE}_{YYYYMMDD}_{HHMMSS}_{UUID前8位}
    """
    prefix = 'SINGLE' if mode == 'single' else 'BATCH'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = uuid.uuid4().hex[:8].upper()
    return f"{prefix}_{timestamp}_{unique_id}"


class BrowserUseService:
    """
    Browser-Use 测试执行服务 (0.11.1 版本)
    
    支持 Token 统计和截图保存
    """
    
    @staticmethod
    async def execute_test_with_browser_use(
        test_case_id: int,
        db: Session,
        headless: bool = None,
        max_steps: int = None,
        use_vision: bool = None,
        max_actions: int = None
    ) -> Dict[str, Any]:
        """
        使用 browser-use 0.11.1 Agent 执行测试
        
        Args:
            test_case_id: 测试用例 ID
            db: 数据库会话
            headless: 无头模式
            max_steps: 最大执行步数
            use_vision: 是否启用视觉
            max_actions: 每步最大动作数
        
        Returns:
            执行结果字典，包含 token 统计和截图
        """
        # 从 .env 读取默认配置
        if headless is None:
            headless = os.getenv('HEADLESS', 'false').lower() == 'true'
        if max_steps is None:
            max_steps = int(os.getenv('MAX_STEPS', '100'))
        if use_vision is None:
            use_vision = os.getenv('LLM_USE_VISION', 'false').lower() == 'true'
        if max_actions is None:
            max_actions = int(os.getenv('MAX_ACTIONS', '10'))
        
        # 1. 获取测试用例
        test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
        
        if not test_case:
            return {
                "success": False,
                "message": f"测试用例 ID {test_case_id} 不存在"
            }
        
        # 2. 检查是否需要答题
        need_answer = BrowserUseService._need_auto_answer(test_case)
        
        # 3. 构建任务描述（根据是否需要答题调整提示）
        task_description = BrowserUseService._build_task_description(test_case, enable_auto_answer=need_answer)
        
        start_time = time.time()
        
        # 创建任务
        task_manager = get_task_manager()
        task_manager.create_task(test_case_id, test_case_id)
        
        # ========== 测试开始前：立即写入 execution_batches 和 test_records ==========
        # 生成执行批次号
        batch_id = generate_batch_id('single')
        
        # 1. 创建中间表记录（用例与批次映射）
        execution_batch = ExecutionBatch(
            execution_case_id=test_case_id,
            batch=batch_id
        )
        db.add(execution_batch)
        db.flush()
        
        # 2. 创建执行记录（状态为"执行中"）
        test_record = TestRecord(
            batch_id=execution_batch.id,
            test_case_id=test_case_id,
            execution_mode='单量',
            total_cases=1,
            passed_cases=0,
            failed_cases=0,
            execution_log=json.dumps({"status": "执行中", "message": "测试正在执行..."}, ensure_ascii=False),
            status="running",  # 执行中状态
            error_message=None,
            duration=0,
            test_steps=0
        )
        db.add(test_record)
        db.commit()
        db.refresh(test_record)
        
        print(f"[BrowserUse] ✓ 已创建执行记录，批次: {batch_id}, 记录ID: {test_record.id}, 状态: running")
        # ========== 记录创建完成 ==========
        
        # 初始化截图管理器（用于 Bug 截图）
        screenshot_manager = ScreenshotManager(BUG_IMG_SAVE_PATH)
        
        # Token 使用量统计
        token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        try:
            # 3. 创建 LLM（使用数据库中的模型配置）
            from Model_manage.config_manager import get_active_llm_config
            
            try:
                llm_config = get_active_llm_config()
                model_name = llm_config['model_name']
                print(f"[BrowserUse] 🔧 使用数据库模型配置: model={model_name}, provider={llm_config['provider']}")
            except Exception as e:
                print(f"[BrowserUse] ⚠️ 获取数据库模型配置失败: {e}")
                print(f"[BrowserUse] 🔧 回退到环境变量配置")
                llm_config = {
                    'model_name': os.getenv('LLM_MODEL'),
                    'api_key': os.getenv('LLM_API_KEY'),
                    'base_url': os.getenv('LLM_BASE_URL'),
                    'temperature': float(os.getenv('LLM_TEMPERATURE', '0.0'))
                }
                model_name = llm_config['model_name']
            
            # browser-use 0.11.1 使用新的 LLM 创建方式
            from browser_use.llm.openai.chat import ChatOpenAI
            
            # 检查是否为 DeepSeek 或其他不支持结构化输出的提供商
            provider = llm_config.get('provider', 'openai').lower()
            dont_force_structured = provider in ['deepseek', 'other']
            
            llm = ChatOpenAI(
                model=model_name,
                api_key=llm_config['api_key'],
                base_url=llm_config['base_url'],
                temperature=llm_config.get('temperature', 0.0),
                dont_force_structured_output=dont_force_structured,  # DeepSeek 不支持结构化输出
            )
            
            if dont_force_structured:
                print(f"[BrowserUse] ⚠️ 提供商 '{provider}' 不支持结构化输出，已禁用")
            
            # 4. 创建浏览器配置 (browser-use 0.11.1 使用 BrowserProfile)
            window_width = int(os.getenv('BROWSER_WINDOW_WIDTH', '1920'))
            window_height = int(os.getenv('BROWSER_WINDOW_HEIGHT', '1200'))
            
            browser_profile = BrowserProfile(
                headless=headless,
                disable_security=os.getenv('DISABLE_SECURITY', 'false').lower() == 'true',
                extra_browser_args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--disable-extensions',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-popup-blocking',
                    '--disable-translate',
                    f'--window-size={window_width},{window_height}',
                    '--start-maximized',
                ],
            )
            
            # 创建 BrowserSession
            browser_session = BrowserSession(browser_profile=browser_profile)
            
            # 5. 创建 Tools 并注册自定义 actions
            tools = Tools()
            
            # 根据之前的检测结果决定是否注册答题 action
            if need_answer:
                print("[BrowserUse] ✅ 该测试用例需要答题，注册自定义答题 action")
                # register_custom_actions(tools)  # TODO: 适配 0.11.1 的自定义 action 注册
            else:
                print("[BrowserUse] ⚠️ 该测试用例不需要答题（或明确要求不答题）")
            
            # 6. 创建 Agent（使用增强版 BrowserUseAgent）
            print(f"[BrowserUse] 🚀 开始执行测试: {test_case.title}")
            print(f"[BrowserUse] ⚙️  配置: max_steps={max_steps}, vision={use_vision}, headless={headless}")
            
            # 使用增强版 Agent，启用 token 跟踪和自动截图
            agent = BrowserUseAgent(
                task=task_description,
                llm=llm,
                browser_session=browser_session,
                tools=tools,
                use_vision=use_vision,
                max_actions_per_step=max_actions,
                extend_system_message=BROWSER_USE_CHINESE_SYSTEM,  # 启用中文系统提示词
                calculate_cost=True,  # 启用成本计算
                enable_token_tracking=True,  # 启用 token 跟踪
                enable_auto_screenshot=True,  # 启用自动截图
                screenshot_save_dir=BUG_IMG_SAVE_PATH,  # Bug 截图保存目录
            )
            
            # 7. 执行测试（使用 Task 以支持取消）
            task = asyncio.create_task(agent.run(max_steps=max_steps))
            
            # 监控任务状态
            try:
                while not task.done():
                    # 检查停止标志
                    if task_manager.should_stop(test_case_id):
                        print(f"[BrowserUse] ⚠️ 检测到停止信号，正在停止 Agent...")
                        
                        # 调用 Agent 的 stop 方法
                        try:
                            agent.stop()
                            print(f"[BrowserUse] ✓ Agent.stop() 已调用")
                        except Exception as e:
                            print(f"[BrowserUse] ⚠️ 调用 Agent.stop() 时出错: {e}")
                        
                        # 取消任务
                        task.cancel()
                        
                        # 等待任务取消完成（最多等待20秒）
                        try:
                            await asyncio.wait_for(task, timeout=20)
                        except asyncio.TimeoutError:
                            print(f"[BrowserUse] ⚠️ 任务未在20秒内完成，强制取消")
                        except asyncio.CancelledError:
                            print(f"[BrowserUse] ✓ 任务已被取消")
                        except Exception as e:
                            print(f"[BrowserUse] ⚠️ 等待任务时出错: {e}")
                        
                        # 强制关闭浏览器会话
                        try:
                            await browser_session.close()
                            print(f"[BrowserUse] ✓ 浏览器已关闭")
                        except Exception as e:
                            print(f"[BrowserUse] ⚠️ 关闭浏览器时出错: {e}")
                        
                        raise Exception("用户手动停止")
                    
                    # 检查暂停
                    await task_manager.check_pause(test_case_id)
                    
                    await asyncio.sleep(0.2)  # 每0.2秒检查一次
                
                # 获取执行结果
                try:
                    history = task.result()
                    print(f"[BrowserUse] ✓ Agent 执行完成，获取到 history")
                except Exception as result_err:
                    print(f"[BrowserUse] ⚠️ 获取 task.result() 时出错: {result_err}")
                    # 尝试从 agent 获取 history
                    if hasattr(agent, 'history'):
                        history = agent.history
                        print(f"[BrowserUse] ✓ 从 agent.history 获取到结果")
                    else:
                        # 如果无法获取 history，创建空的
                        from browser_use.agent.views import AgentHistoryList
                        history = AgentHistoryList(history=[])
                        print(f"[BrowserUse] ⚠️ 无法获取 history，使用空结果")
                    
            except asyncio.CancelledError:
                print(f"[BrowserUse] ✓ 任务已被取消")
                raise Exception("用户手动停止")
            
            # 7. 获取 Token 使用量统计
            token_usage = agent.get_token_usage()
            bug_screenshots = agent.get_screenshots()
            
            print(f"[BrowserUse] 📊 Token 统计: {token_usage}")
            print(f"[BrowserUse] 📸 截图数量: {len(bug_screenshots)}")
            
            # 8. 处理执行结果
            try:
                execution_time = int(time.time() - start_time)
                execution_result = BrowserUseService._process_execution_result(
                    history, test_case, execution_time
                )
                print(f"[BrowserUse] ✓ 执行结果处理完成: status={execution_result['status']}, steps={execution_result['total_steps']}")
            except Exception as process_err:
                print(f"[BrowserUse] ⚠️ 处理执行结果时出错: {process_err}")
                import traceback
                traceback.print_exc()
                # 创建默认结果
                execution_time = int(time.time() - start_time)
                execution_result = {
                    "status": "fail",
                    "error_message": f"处理结果失败: {str(process_err)}",
                    "total_steps": 0,
                    "history": {"steps": [], "total_steps": 0},
                    "final_url": ""
                }
            
            # 添加 token 统计到结果
            execution_result["token_usage"] = token_usage
            execution_result["screenshots"] = bug_screenshots
            
            # 9. 更新数据库记录（测试开始前已创建，现在更新最终结果）
            try:
                # 更新执行记录（更新状态和执行详情）
                test_record.passed_cases = 1 if execution_result["status"] == 'pass' else 0
                test_record.failed_cases = 1 if execution_result["status"] in ('fail', 'error') else 0
                test_record.execution_log = json.dumps({
                    "history": execution_result["history"],
                    "screenshots": bug_screenshots
                }, ensure_ascii=False, indent=2)
                test_record.status = execution_result["status"]
                test_record.error_message = execution_result["error_message"]
                test_record.duration = execution_time
                test_record.test_steps = execution_result["total_steps"]
                
                db.commit()
                db.refresh(test_record)
                
                # 兼容旧代码：test_result 指向 test_record
                test_result = test_record
                
                print(f"[BrowserUse] ✓ 测试结果已更新，批次: {batch_id}, 记录ID: {test_record.id}, 状态: {execution_result['status']}")
            except Exception as db_err:
                print(f"[BrowserUse] ❌ 保存数据库失败: {db_err}")
                import traceback
                traceback.print_exc()
                db.rollback()
                raise
            
            # 10. 更新数据库中的 Token 统计（使用激活模型）
            if token_usage.get('total_tokens', 0) > 0:
                try:
                    # 优先使用激活模型更新方法，更可靠
                    TokenStatisticsService.update_active_model_token_usage(db, token_usage)
                except Exception as token_err:
                    print(f"[BrowserUse] ⚠️ Token 统计更新失败: {token_err}")
            
            print(f"[BrowserUse] {'✅ 成功' if execution_result['status'] == 'pass' else '❌ 失败'}")
            print(f"[BrowserUse] 📊 共执行 {execution_result['total_steps']} 步，耗时 {execution_time} 秒")
            
            # 11. 如果测试失败，分析 Bug
            bug_analysis_result = None
            if execution_result['status'] == 'fail':
                try:
                    from Bug_Analysis.service import BugAnalysisService
                    
                    print("[BrowserUse] 🔍 正在分析 Bug...")
                    
                    # 分析 Bug
                    bug_analysis_result = await BugAnalysisService.analyze_bug_from_execution(
                        test_case_id=test_case_id,
                        test_record_id=test_result.id,
                        execution_history=execution_result["history"],
                        error_message=execution_result.get("error_message", "测试未完成或失败"),
                        db=db,
                        execution_mode='单量'
                    )
                    
                    if bug_analysis_result:
                        severity = bug_analysis_result['severity_level']
                        should_stop = bug_analysis_result['should_stop']
                        print(f"[BrowserUse] 🐛 Bug 已记录: 严重程度={severity}, 是否中止={'是' if should_stop else '否'}")
                    
                except Exception as bug_error:
                    import traceback as tb
                    print(f"[BrowserUse] ⚠️ Bug 分析失败: {str(bug_error)}")
                    print(tb.format_exc())
            
            # 10. 自动生成测试报告
            report_data = None
            try:
                from Build_Report.service import TestReportService
                print("[BrowserUse] 🔄 正在生成测试报告...")
                report_res = await TestReportService.generate_report(
                    test_result_ids=[test_result.id],
                    db=db,
                    format_type="markdown"
                )
                if report_res.get("success"):
                    report_data = report_res.get("data")
                    print(f"[BrowserUse] 📝 测试报告已生成: {report_data.get('title')}")
                else:
                    print(f"[BrowserUse] ⚠️ 生成报告失败: {report_res.get('message')}")
            except Exception as e:
                print(f"[BrowserUse] ⚠️ 自动生成报告异常: {str(e)}")
            
            try:
                if bug_analysis_result and report_data:
                    from Email_manage.service import EmailService
                    bug_id = bug_analysis_result.get("bug_id")
                    severity = bug_analysis_result.get("severity_level")
                    report_title = report_data.get("title") if isinstance(report_data, dict) else None
                    if not report_title:
                        report_title = test_case.title
                    email_subject = f"[Bug测试报告] {report_title} - 严重程度：{severity}"
                    bug_info_html = ""
                    if bug_id or severity:
                        bug_info_html = "<div>"
                        if bug_id:
                            bug_info_html += f"<p>Bug ID: {bug_id}</p>"
                        if severity:
                            bug_info_html += f"<p>严重程度: {severity}</p>"
                        bug_info_html += "</div>"
                    report_html = ""
                    if isinstance(report_data, dict):
                        report_html = report_data.get("details") or ""
                    html_content = (bug_info_html or "") + report_html
                    send_res = EmailService.send_to_auto_receive_bug_contacts(
                        subject=email_subject,
                        html_content=html_content,
                        db=db
                    )
                    if send_res.get("success"):
                        print("[BrowserUse] 📨 Bug 测试报告已自动发送给自动接收BUG的联系人")
                    else:
                        print(f"[BrowserUse] ⚠️ Bug 测试报告发送失败: {send_res.get('message')}")
            except Exception as email_error:
                import traceback as tb
                print(f"[BrowserUse] ⚠️ 自动发送 Bug 测试报告异常: {str(email_error)}")
                print(tb.format_exc())
            
            return {
                "success": True,
                "message": f"测试执行{'成功' if execution_result['status'] == 'pass' else '失败'}",
                "data": {
                    "result_id": test_result.id,
                    "status": execution_result["status"],
                    "total_steps": execution_result["total_steps"],
                    "history": execution_result["history"],
                    "final_url": execution_result["final_url"],
                    "duration": execution_time,
                    "report": report_data,
                    "bug_analysis": bug_analysis_result,
                    "token_usage": token_usage,
                    "screenshots": bug_screenshots
                }
            }
        
        except asyncio.CancelledError:
            # 任务被取消（用户停止）
            execution_time = int(time.time() - start_time)
            print(f"[BrowserUse] ⚠️ 任务被用户取消")
            
            # 更新执行记录（状态改为失败）
            test_record.passed_cases = 0
            test_record.failed_cases = 1
            test_record.execution_log = json.dumps({"message": "用户手动停止"}, ensure_ascii=False)
            test_record.status = "fail"
            test_record.error_message = "用户手动停止"
            test_record.duration = execution_time
            test_record.test_steps = 0
            
            db.commit()
            
            # 兼容旧代码
            test_result = test_record
            
            return {
                "success": False,
                "message": "测试已被用户停止",
                "data": {
                    "result_id": test_record.id,
                    "status": "fail",
                    "error_message": "用户手动停止",
                    "duration": execution_time
                }
            }
        
        except Exception as e:
            import traceback
            error_msg = str(e)
            error_trace = traceback.format_exc()
            
            print(f"[BrowserUse] ❌ 错误: {error_msg}")
            print(f"[BrowserUse] 堆栈跟踪:\n{error_trace}")
            
            # 保存失败结果
            execution_time = int(time.time() - start_time)
            
            # 更新执行记录（状态改为错误）
            test_record.passed_cases = 0
            test_record.failed_cases = 1
            test_record.execution_log = json.dumps({"error": error_msg, "trace": error_trace}, ensure_ascii=False)
            test_record.status = "error"
            test_record.error_message = error_msg
            test_record.duration = execution_time
            test_record.test_steps = 0
            
            db.commit()
            db.refresh(test_record)
            
            # 兼容旧代码
            test_result = test_record
            
            # ========== 新增：Bug 分析 ==========
            bug_analysis_result = None
            try:
                from Bug_Analysis.service import BugAnalysisService
                
                print("[BrowserUse] 🔍 正在分析 Bug...")
                
                # 分析 Bug
                bug_analysis_result = await BugAnalysisService.analyze_bug_from_execution(
                    test_case_id=test_case_id,
                    test_record_id=test_result.id,
                    execution_history={"error": error_msg, "trace": error_trace},
                    error_message=error_msg,
                    db=db,
                    execution_mode='单量'
                )
                
                if bug_analysis_result:
                    severity = bug_analysis_result['severity_level']
                    should_stop = bug_analysis_result['should_stop']
                    print(f"[BrowserUse] 🐛 Bug 已记录: 严重程度={severity}, 是否中止={'是' if should_stop else '否'}")
                else:
                    print("[BrowserUse] ⚠️ Bug 分析未返回结果")
                
            except Exception as bug_error:
                import traceback as tb
                print(f"[BrowserUse] ⚠️ Bug 分析失败: {str(bug_error)}")
                print(tb.format_exc())
            # ========== Bug 分析结束 ==========
            
            return {
                "success": False,
                "message": f"测试执行失败: {error_msg}",
                "error_details": error_trace,
                "bug_analysis": bug_analysis_result
            }
        
        finally:
            # 清理任务
            task_manager.remove_task(test_case_id)
    
    @staticmethod
    def _build_task_description(test_case: TestCase, enable_auto_answer: bool = False) -> str:
        """
        构建给 Agent 的任务描述
        
        Args:
            test_case: 测试用例
            enable_auto_answer: 是否启用自动答题功能
        """
        steps_list = json.loads(test_case.steps) if test_case.steps else []
        test_data = test_case.test_data or {}
        
        # 格式化步骤
        formatted_steps = "\n".join([
            f"{i+1}. {step}" for i, step in enumerate(steps_list)
        ])
        
        # 格式化测试数据
        formatted_data = "\n".join([
            f"- {key}: {value}" for key, value in test_data.items()
        ])
        
        # 尝试从测试数据或步骤中提取目标URL
        target_url = test_data.get('url') or test_data.get('target_url') or test_data.get('网址')
        
        # 如果没有明确的URL，尝试从第一个步骤中提取
        if not target_url and steps_list:
            first_step = steps_list[0].lower()
            if 'http' in first_step:
                # 简单提取URL（可以改进）
                import re
                url_match = re.search(r'https?://[^\s]+', steps_list[0])
                if url_match:
                    target_url = url_match.group(0)
        
        # 构建任务描述，如果有URL则添加导航指令
        url_instruction = f"\n⚠️ 首先立即访问目标网址：{target_url}\n" if target_url else ""
        
        # 根据是否启用答题功能，生成不同的提示
        if enable_auto_answer:
            answer_instruction = "6. ⚠️ **重要：如果测试步骤要求答题，进入答题页面后使用 auto_answer 动作自动完成所有题目，然后继续执行后续步骤（如点击提交）**"
        else:
            answer_instruction = '6. ⚠️ **重要：严格按照测试步骤执行，不要主动答题。如果步骤要求"不作答"或"直接提交"，请严格遵守**'
        
        task = f"""
【测试任务】
标题：{test_case.title}
{url_instruction}
【前置条件】
{test_case.precondition or '无'}

【执行步骤】
{formatted_steps}

【预期结果】
{test_case.expected}

【测试数据】
{formatted_data if formatted_data else '无'}

【重要提示】
1. 立即开始执行，不要停留在空白页面
2. ⚠️ 严格按照步骤顺序执行，每个步骤只执行一次，完成后立即进入下一步
3. ⚠️ 如果页面显示错误提示（如"密码错误"）后元素消失，等待2-3秒让页面恢复，或者点击页面空白处关闭提示
4. ⚠️ 如果元素未找到，先尝试：等待2秒 → 滚动页面 → 点击关闭弹窗 → 刷新页面，不要重复执行已完成的步骤
5. ⚠️ 绝对不要使用 go_back()，这会导致页面变成空白
{answer_instruction}
7. 关键步骤可使用 screenshot 动作请求截图验证
8. 完成所有步骤后明确说明"测试完成"并调用 done 动作
9. 如果连续3次无法找到元素，说明原因并调用 done 动作停止

【成功标准】
所有步骤顺利执行且预期结果达成
"""
        return task.strip()
    
    @staticmethod
    def _translate_thinking(thinking_text: str) -> str:
        """
        翻译 AI 思考内容为中文
        如果已经是中文则直接返回
        """
        if not thinking_text:
            return ""
        
        # 简单判断：如果包含中文字符，认为已经是中文
        if any('\u4e00' <= char <= '\u9fff' for char in thinking_text):
            return thinking_text
        
        # 常见英文短语翻译映射
        translations = {
            "I have successfully completed": "我已成功完成",
            "by clicking on": "通过点击",
            "The page has transitioned to": "页面已转换到",
            "which appears to be": "看起来是",
            "According to the user request": "根据用户请求",
            "I now need to proceed to": "我现在需要继续",
            "which is to": "即",
            "Since the current view shows": "由于当前视图显示",
            "I need to look for": "我需要查找",
            "which may require": "这可能需要",
            "I will first attempt to": "我将首先尝试",
            "to see if": "看看是否",
            "becomes visible": "变得可见",
            "course button": "课程按钮",
            "option": "选项",
            "within this course interface": "在此课程界面中",
            "study plan reminders": "学习计划提醒",
            "scrolling or waiting for additional elements to load": "滚动或等待其他元素加载",
        }
        
        # 应用翻译
        result = thinking_text
        for en, zh in translations.items():
            result = result.replace(en, zh)
        
        return result
    
    @staticmethod
    def _format_action_name(action_dict: dict) -> str:
        """
        格式化动作名称为可读的中文描述
        
        Args:
            action_dict: 动作字典
            
        Returns:
            格式化后的动作名称
        """
        # 动作类型映射
        action_type_map = {
            "click": "点击",
            "input_text": "输入文本",
            "input": "输入文本",
            "go_to_url": "访问网址",
            "navigate": "导航到",
            "scroll": "滚动页面",
            "wait": "等待",
            "done": "完成",
            "screenshot": "请求截图",
            "extract_content": "提取内容",
            "extract": "提取内容",
            "go_back": "返回",
            "switch_tab": "切换标签页",
            "switch": "切换标签页",
            "open_tab": "打开新标签页",
            "close_tab": "关闭标签页",
            "close": "关闭标签页",
            "auto_answer": "自动答题",
            "send_keys": "发送按键",
            "find_text": "查找文本",
            "upload_file": "上传文件",
            "evaluate": "执行JS",
            "search": "搜索",
        }
        
        # 获取动作类型
        action_keys = list(action_dict.keys())
        if not action_keys:
            return "未知动作"
        
        # 第一个键通常是动作类型
        action_type = action_keys[0]
        action_name = action_type_map.get(action_type, action_type)
        
        # 添加详细信息
        action_data = action_dict.get(action_type, {})
        
        if action_type == "click":
            if isinstance(action_data, dict):
                index = action_data.get("index", "")
                if index:
                    action_name = f"点击元素 (索引 {index})"
        
        elif action_type == "input_text":
            if isinstance(action_data, dict):
                index = action_data.get("index", "")
                text = action_data.get("text", "")
                if index and text:
                    # 隐藏密码
                    display_text = "******" if "密码" in str(text) or "password" in str(text).lower() else text[:20]
                    action_name = f"输入文本 (索引 {index}): {display_text}"
        
        elif action_type == "go_to_url":
            if isinstance(action_data, dict):
                url = action_data.get("url", "")
                if url:
                    action_name = f"访问: {url[:50]}"
        
        elif action_type == "scroll":
            if isinstance(action_data, dict):
                direction = action_data.get("direction", "down")
                direction_map = {"down": "向下", "up": "向上"}
                action_name = f"滚动{direction_map.get(direction, direction)}"
        
        elif action_type == "done":
            if isinstance(action_data, dict):
                text = action_data.get("text", "")
                if text:
                    action_name = f"完成: {text[:30]}"
        
        return action_name
    
    @staticmethod
    def _need_auto_answer(test_case: TestCase) -> bool:
        """
        分析测试用例是否需要自动答题
        通过检查步骤中的关键词判断
        
        规则：
        1. 如果明确要求"不作答"、"不答题"、"直接提交"等，则不启用答题
        2. 如果包含答题关键词且没有"不作答"等否定词，则启用答题
        """
        steps = json.loads(test_case.steps) if test_case.steps else []
        
        # 否定关键词（明确要求不答题）
        NEGATIVE_KEYWORDS = [
            '不作答', '不答题', '不做题', '不回答',
            '直接提交', '直接点击提交', '跳过答题',
            '不填写', '不选择', '空白提交',
            '未作答', '未答题',
        ]
        
        # 首先检查是否有否定关键词
        for i, step in enumerate(steps):
            for neg_keyword in NEGATIVE_KEYWORDS:
                if neg_keyword in step:
                    print(f"[BrowserUse] 步骤 {i+1} 包含否定关键词 '{neg_keyword}': {step}")
                    print("[BrowserUse] ❌ 测试用例明确要求不答题，不注册答题 action")
                    return False
        
        # 检查步骤中是否包含答题关键词
        for i, step in enumerate(steps):
            # 精确匹配
            for keyword in ANSWER_KEYWORDS:
                if keyword in step:
                    print(f"[BrowserUse] 步骤 {i+1} 包含答题关键词 '{keyword}': {step}")
                    return True
            
            # 正则匹配（支持模糊匹配）
            patterns = [
                r'点击.*[练习|答题|做题]',
                r'进入.*[题|练习]',
                r'完成.*题',
            ]
            
            for pattern in patterns:
                if re.search(pattern, step):
                    print(f"[BrowserUse] 步骤 {i+1} 匹配答题模式 '{pattern}': {step}")
                    return True
        
        print("[BrowserUse] 未检测到答题相关步骤")
        return False
    
    @staticmethod
    async def _is_question_page(page) -> bool:
        """
        检测是否进入答题页面
        通过 URL 和页面元素判断
        """
        try:
            # 方法1: 检查 URL 关键词
            current_url = page.url
            if 'practice' in current_url or 'exercise' in current_url or 'question' in current_url:
                print("[PageMonitor] 检测到答题页面 URL")
                return True
            
            # 方法2: 检查页面是否有题目元素
            has_questions = await page.evaluate("""
                () => {
                    const wrappers = document.querySelectorAll('.question-wrapper, .topic-item, .question-item');
                    return wrappers.length > 0;
                }
            """)
            
            if has_questions:
                print("[PageMonitor] 检测到题目元素")
                return True
            
            return False
            
        except Exception as e:
            print(f"[PageMonitor] 检测答题页面失败: {str(e)}")
            return False
    
    @staticmethod
    async def _verify_practice_ready(page) -> bool:
        """
        验证练习页面是否加载完成
        检查题目是否渲染完成
        """
        try:
            # 等待题目元素出现
            await page.wait_for_function("""
                () => {
                    const wrappers = document.querySelectorAll('.question-wrapper, .topic-item, .question-item');
                    return wrappers.length > 0;
                }
            """, timeout=5000)
            
            print("[PageMonitor] ✓ 题目加载完成")
            return True
            
        except Exception as e:
            print(f"[PageMonitor] 题目加载超时: {str(e)}")
            return False
    
    @staticmethod
    def _process_execution_result(history, test_case: TestCase, execution_time: int) -> Dict[str, Any]:
        """处理 browser-use 的执行结果"""
        history_data = {
            "total_steps": history.number_of_steps(),
            "steps": [],
            "final_state": {
                "url": "",
                "success": False
            }
        }
        
        # 提取执行步骤
        for i, h in enumerate(history.history):
            step_data = {
                "step_number": i + 1,
                "timestamp": datetime.now().isoformat(),
                "url": h.state.url if h.state else '',
                "title": h.state.title if h.state else '',
            }
            
            # 提取 Agent 的思考过程
            if h.model_output:
                # 翻译思考内容为中文（如果是英文）
                thinking_text = h.model_output.current_state.thinking
                step_data["thinking"] = BrowserUseService._translate_thinking(thinking_text)
                step_data["evaluation"] = h.model_output.current_state.evaluation_previous_goal
                step_data["memory"] = h.model_output.current_state.memory
                step_data["next_goal"] = h.model_output.current_state.next_goal
                
                # 提取并格式化执行的动作
                step_data["actions"] = []
                for action in h.model_output.action:
                    action_dict = action.model_dump(exclude_none=True)
                    # 添加可读的动作名称
                    action_dict["action_name"] = BrowserUseService._format_action_name(action_dict)
                    step_data["actions"].append(action_dict)
            else:
                step_data["actions"] = []
            
            # 提取结果
            if h.result:
                step_data["results"] = [
                    r.model_dump(exclude_none=True)
                    for r in h.result
                ]
            
            history_data["steps"].append(step_data)
        
        # 判断执行状态
        is_done = history.is_done()
        is_successful = history.is_successful()
        
        # 提取最终 URL
        final_url = history.urls()[-1] if history.urls() else ""
        
        history_data["final_state"]["url"] = final_url
        history_data["final_state"]["success"] = is_done and (is_successful is not False)
        
        return {
            "status": "pass" if (is_done and is_successful is not False) else "fail",
            "error_message": "" if (is_done and is_successful is not False) else f"测试未完成或失败",
            "total_steps": history_data["total_steps"],
            "history": history_data,
            "final_url": final_url
        }

    @staticmethod
    async def execute_batch_test_cases(
        test_case_ids: list,
        db: Session,
        headless: bool = None,
        max_steps: int = None,
        use_vision: bool = None,
        max_actions: int = None
    ) -> Dict[str, Any]:
        """
        批量执行多条测试用例，智能合并共同步骤
        
        Args:
            test_case_ids: 测试用例 ID 列表
            db: 数据库会话
            headless: 无头模式
            max_steps: 最大执行步数
            use_vision: 是否启用视觉
            max_actions: 每步最大动作数
        
        Returns:
            批量执行结果，包含合并后的步骤和每条用例的结果
        """
        # 从 .env 读取默认配置
        if headless is None:
            headless = os.getenv('HEADLESS', 'false').lower() == 'true'
        if max_steps is None:
            max_steps = int(os.getenv('MAX_STEPS', '100'))
        if use_vision is None:
            use_vision = os.getenv('LLM_USE_VISION', 'false').lower() == 'true'
        if max_actions is None:
            max_actions = int(os.getenv('MAX_ACTIONS', '10'))
        
        # 1. 获取所有测试用例
        test_cases = db.query(TestCase).filter(TestCase.id.in_(test_case_ids)).all()
        
        if not test_cases:
            return {
                "success": False,
                "message": "未找到任何测试用例"
            }
        
        if len(test_cases) < 2:
            return {
                "success": False,
                "message": "批量执行需要至少2条测试用例"
            }
        
        print(f"[BatchBrowserUse] 🚀 开始批量执行 {len(test_cases)} 条测试用例")
        
        # 2. 构建批量任务描述（让 LLM 分析并合并步骤）
        batch_task_description = BrowserUseService._build_batch_task_description(test_cases)
        
        start_time = time.time()
        
        # 创建批量任务ID
        batch_task_id = BATCH_TASK_ID_PREFIX + test_case_ids[0]
        task_manager = get_task_manager()
        task_manager.create_task(batch_task_id, batch_task_id)
        
        # ========== 批量执行开始前：立即写入 execution_batches 和 test_records ==========
        # 生成批量执行批次号（所有用例共用）
        batch_id = generate_batch_id('batch')
        
        # 为每条用例创建中间表记录
        execution_batch_ids = []
        for tc in test_cases:
            execution_batch = ExecutionBatch(
                execution_case_id=tc.id,
                batch=batch_id
            )
            db.add(execution_batch)
            db.flush()
            execution_batch_ids.append(execution_batch.id)
        
        # 创建执行记录（状态为"执行中"）
        test_record = TestRecord(
            batch_id=execution_batch_ids[0] if execution_batch_ids else 0,
            test_case_id=test_case_ids[0] if test_case_ids else None,
            execution_mode='批量',
            total_cases=len(test_cases),
            passed_cases=0,
            failed_cases=0,
            execution_log=json.dumps({
                "status": "执行中",
                "message": "批量测试正在执行...",
                "batch_cases": test_case_ids
            }, ensure_ascii=False),
            status="running",  # 执行中状态
            error_message=None,
            duration=0,
            test_steps=0
        )
        db.add(test_record)
        db.commit()
        db.refresh(test_record)
        
        print(f"[BatchBrowserUse] ✓ 已创建执行记录，批次: {batch_id}, 记录ID: {test_record.id}, 状态: running")
        # ========== 记录创建完成 ==========
        
        # Token 使用量统计
        token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        try:
            # 3. 创建 LLM
            from Model_manage.config_manager import get_active_llm_config
            
            try:
                llm_config = get_active_llm_config()
                model_name = llm_config['model_name']
                print(f"[BatchBrowserUse] 🔧 使用数据库模型配置: model={model_name}")
            except Exception as e:
                print(f"[BatchBrowserUse] ⚠️ 获取数据库模型配置失败: {e}")
                llm_config = {
                    'model_name': os.getenv('LLM_MODEL'),
                    'api_key': os.getenv('LLM_API_KEY'),
                    'base_url': os.getenv('LLM_BASE_URL'),
                    'temperature': float(os.getenv('LLM_TEMPERATURE', '0.0'))
                }
                model_name = llm_config['model_name']
            
            from browser_use.llm.openai.chat import ChatOpenAI
            
            provider = llm_config.get('provider', 'openai').lower()
            dont_force_structured = provider in ['deepseek', 'other']
            
            llm = ChatOpenAI(
                model=model_name,
                api_key=llm_config['api_key'],
                base_url=llm_config['base_url'],
                temperature=llm_config.get('temperature', 0.0),
                dont_force_structured_output=dont_force_structured,
            )
            
            # 4. 创建浏览器配置
            window_width = int(os.getenv('BROWSER_WINDOW_WIDTH', '1920'))
            window_height = int(os.getenv('BROWSER_WINDOW_HEIGHT', '1200'))
            
            browser_profile = BrowserProfile(
                headless=headless,
                disable_security=os.getenv('DISABLE_SECURITY', 'false').lower() == 'true',
                extra_browser_args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--disable-extensions',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-popup-blocking',
                    '--disable-translate',
                    f'--window-size={window_width},{window_height}',
                    '--start-maximized',
                ],
            )
            
            browser_session = BrowserSession(browser_profile=browser_profile)
            tools = Tools()
            
            # 5. 创建 Agent
            agent = BrowserUseAgent(
                task=batch_task_description,
                llm=llm,
                browser_session=browser_session,
                tools=tools,
                use_vision=use_vision,
                max_actions_per_step=max_actions,
                extend_system_message=BROWSER_USE_BATCH_CHINESE_SYSTEM,  # 启用中文系统提示词
                calculate_cost=True,
                enable_token_tracking=True,
                enable_auto_screenshot=True,
                screenshot_save_dir=BUG_IMG_SAVE_PATH,
            )
            
            # 6. 执行测试
            task = asyncio.create_task(agent.run(max_steps=max_steps))
            
            try:
                while not task.done():
                    if task_manager.should_stop(batch_task_id):
                        print(f"[BatchBrowserUse] ⚠️ 检测到停止信号")
                        try:
                            agent.stop()
                        except Exception as e:
                            print(f"[BatchBrowserUse] ⚠️ 停止 Agent 时出错: {e}")
                        task.cancel()
                        try:
                            await asyncio.wait_for(task, timeout=20)
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            pass
                        await browser_session.close()
                        raise Exception("用户手动停止")
                    
                    await task_manager.check_pause(batch_task_id)
                    await asyncio.sleep(0.2)
                
                history = task.result()
                
            except asyncio.CancelledError:
                raise Exception("用户手动停止")
            
            # 7. 获取统计
            token_usage = agent.get_token_usage()
            bug_screenshots = agent.get_screenshots()
            
            # 8. 处理执行结果
            execution_time = int(time.time() - start_time)
            execution_result = BrowserUseService._process_batch_execution_result(
                history, test_cases, execution_time
            )
            
            execution_result["token_usage"] = token_usage
            execution_result["screenshots"] = bug_screenshots
            
            # 9. 更新数据库记录（批量执行开始前已创建，现在更新最终结果）
            # 计算通过/失败数
            passed_count = 0
            failed_count = 0
            
            for tc in test_cases:
                # 确定单条用例的状态（简化处理：批量执行时所有用例共享整体状态）
                case_status = execution_result["status"]
                if case_status == 'pass':
                    passed_count += 1
                else:
                    failed_count += 1
            
            # 确定汇总状态
            if passed_count == len(test_cases):
                overall_status = 'pass'
            elif failed_count == len(test_cases):
                overall_status = 'fail'
            else:
                overall_status = 'partial'  # 部分通过
            
            # 更新执行记录（更新状态和执行详情）
            test_record.passed_cases = passed_count
            test_record.failed_cases = failed_count
            test_record.execution_log = json.dumps({
                "batch_execution": True,
                "batch_cases": test_case_ids,
                "execution_batch_ids": execution_batch_ids,
                "history": execution_result["history"],
                "screenshots": bug_screenshots
            }, ensure_ascii=False, indent=2)
            test_record.status = overall_status
            test_record.error_message = execution_result.get("error_message", "")
            test_record.duration = execution_time
            test_record.test_steps = execution_result["total_steps"]
            
            db.commit()
            db.refresh(test_record)
            
            # 兼容旧代码
            test_result = test_record
            result_ids = [test_record.id]
            
            print(f"[BatchBrowserUse] ✓ 批量结果已更新，批次号: {batch_id}, 执行记录ID: {test_record.id}, 状态: {overall_status}")
            
            # 10. 更新 Token 统计
            if token_usage.get('total_tokens', 0) > 0:
                try:
                    TokenStatisticsService.update_active_model_token_usage(db, token_usage)
                except Exception as token_err:
                    print(f"[BatchBrowserUse] ⚠️ Token 统计更新失败: {token_err}")
            
            print(f"[BatchBrowserUse] {'✅ 成功' if overall_status == 'pass' else '⚠️ 部分通过' if overall_status == 'partial' else '❌ 失败'}")
            print(f"[BatchBrowserUse] 📊 共执行 {execution_result['total_steps']} 步，耗时 {execution_time} 秒")
            
            # 11. 如果有失败，进行 Bug 分析并发送通知
            bug_analysis_results = []
            if failed_count > 0:
                print(f"[BatchBrowserUse] 🐛 开始分析批量测试中的 Bug...")
                from Bug_Analysis.service import BugAnalysisService
                
                # 为每个失败的用例分析 Bug
                # 批量执行时，只为失败的用例创建 Bug 报告
                # 整个批量只创建一条 Bug 报告，记录失败信息
                # 由于批量执行时所有用例共享状态，整体失败则所有用例都认为失败
                failed_case_ids = [tc.id for tc in test_cases]
                failed_case_titles = [tc.title for tc in test_cases]
                
                # 只为第一个失败用例创建 Bug 报告（代表整个批量）
                if failed_case_ids:
                    first_failed_id = failed_case_ids[0]
                    try:
                        bug_result = await BugAnalysisService.analyze_bug_from_execution(
                            test_case_id=first_failed_id,
                            test_record_id=test_result.id,
                            execution_history=execution_result["history"],
                            error_message=f"批量测试执行失败，失败用例: {', '.join(failed_case_titles)}",
                            db=db,
                            execution_mode='批量'
                        )
                        if bug_result:
                            bug_analysis_results.append(bug_result)
                            print(f"[BatchBrowserUse] 🐛 批量Bug已记录: ID={bug_result.get('bug_id')}, 失败用例数: {len(failed_case_ids)}")
                    except Exception as bug_err:
                        print(f"[BatchBrowserUse] ⚠️ 分析批量Bug失败: {bug_err}")
                
                # 发送 Bug 通知邮件
                if bug_analysis_results:
                    try:
                        from Email_manage.service import EmailService
                        
                        # 构建邮件内容
                        bug_count = len(bug_analysis_results)
                        case_names = ", ".join([tc.title for tc in test_cases[:3]])
                        if len(test_cases) > 3:
                            case_names += f" 等{len(test_cases)}条用例"
                        
                        email_subject = f"[批量Bug测试报告] {case_names} - 发现 {bug_count} 个Bug"
                        
                        bug_info_html = f"<h3>批量测试Bug报告</h3>"
                        bug_info_html += f"<p>共执行 {len(test_cases)} 条用例，发现 {bug_count} 个Bug</p>"
                        bug_info_html += "<hr/>"
                        
                        for idx, bug in enumerate(bug_analysis_results, 1):
                            bug_info_html += f"""
                            <div style='margin-bottom: 15px; padding: 10px; background: #f5f5f5; border-radius: 5px;'>
                                <p><strong>Bug #{idx}</strong></p>
                                <p>Bug ID: {bug.get('bug_id')}</p>
                                <p>严重程度: {bug.get('severity_level')}</p>
                                <p>错误类型: {bug.get('error_type')}</p>
                                <p>分析: {bug.get('result_feedback', '')[:200]}...</p>
                            </div>
                            """
                        
                        send_res = EmailService.send_to_auto_receive_bug_contacts(
                            subject=email_subject,
                            html_content=bug_info_html,
                            db=db
                        )
                        if send_res.get("success"):
                            print("[BatchBrowserUse] 📨 批量Bug测试报告已自动发送给自动接收BUG的联系人")
                        else:
                            print(f"[BatchBrowserUse] ⚠️ 批量Bug测试报告发送失败: {send_res.get('message')}")
                    except Exception as email_error:
                        print(f"[BatchBrowserUse] ⚠️ 自动发送批量Bug测试报告异常: {str(email_error)}")
            
            return {
                "success": True,
                "message": f"批量测试执行{'成功' if execution_result['status'] == 'pass' else '失败'}",
                "data": {
                    "result_ids": result_ids,
                    "status": execution_result["status"],
                    "total_steps": execution_result["total_steps"],
                    "merged_steps": execution_result.get("merged_steps", []),
                    "case_results": execution_result.get("case_results", {}),
                    "history": execution_result["history"],
                    "final_url": execution_result["final_url"],
                    "duration": execution_time,
                    "token_usage": token_usage,
                    "screenshots": bug_screenshots,
                    "bug_analysis": bug_analysis_results
                }
            }
        
        except Exception as e:
            import traceback
            error_msg = str(e)
            error_trace = traceback.format_exc()
            
            print(f"[BatchBrowserUse] ❌ 错误: {error_msg}")
            
            # 更新 test_record 状态为 error（如果已创建）
            try:
                if test_record:
                    test_record.status = 'error'
                    test_record.error_message = error_msg[:1000] if error_msg else "未知错误"
                    test_record.execution_log = json.dumps({
                        "status": "error",
                        "message": "批量执行发生异常",
                        "error": error_msg,
                        "trace": error_trace[:2000] if error_trace else ""
                    }, ensure_ascii=False, indent=2)
                    db.commit()
                    print(f"[BatchBrowserUse] ✓ 已更新执行记录状态为 error，记录ID: {test_record.id}")
            except Exception as update_err:
                print(f"[BatchBrowserUse] ⚠️ 更新执行记录状态失败: {update_err}")
            
            return {
                "success": False,
                "message": f"批量执行失败: {error_msg}",
                "error_details": error_trace
            }
        
        finally:
            task_manager.remove_task(batch_task_id)

    @staticmethod
    def _build_batch_task_description(test_cases: list) -> str:
        """
        构建批量测试任务描述
        让 LLM 分析多条用例并智能合并步骤
        
        Args:
            test_cases: 测试用例列表
        """
        # 收集所有用例信息
        cases_info = []
        all_urls = set()
        
        for i, tc in enumerate(test_cases, 1):
            steps_list = json.loads(tc.steps) if tc.steps else []
            test_data = tc.test_data or {}
            
            # 提取URL
            target_url = test_data.get('url') or test_data.get('target_url') or test_data.get('网址')
            if not target_url and steps_list:
                import re
                url_match = re.search(r'https?://[^\s]+', steps_list[0])
                if url_match:
                    target_url = url_match.group(0)
            
            if target_url:
                all_urls.add(target_url)
            
            formatted_steps = "\n".join([f"   {j+1}. {step}" for j, step in enumerate(steps_list)])
            formatted_data = "\n".join([f"   - {key}: {value}" for key, value in test_data.items()])
            
            cases_info.append(f"""
【用例 {i}】{tc.title}
 - 前置条件: {tc.precondition or '无'}
 - 测试步骤:
{formatted_steps}
 - 预期结果: {tc.expected}
 - 测试数据:
{formatted_data if formatted_data else '   无'}
""")
        
        cases_text = "\n".join(cases_info)
        
        # 确定共同URL（如果所有用例都访问同一个URL）
        common_url = list(all_urls)[0] if len(all_urls) == 1 else None
        url_instruction = f"\n⚠️ 首先立即访问目标网址：{common_url}\n" if common_url else ""
        
        # 使用提示词模板
        task = BATCH_TEST_TASK_TEMPLATE.format(
            case_count=len(test_cases),
            url_instruction=url_instruction,
            cases_text=cases_text
        )
        return task.strip()

    @staticmethod
    def _process_batch_execution_result(history, test_cases: list, execution_time: int) -> Dict[str, Any]:
        """处理批量执行的结果"""
        history_data = {
            "total_steps": history.number_of_steps(),
            "steps": [],
            "final_state": {
                "url": "",
                "success": False
            }
        }
        
        # 提取执行步骤
        for i, h in enumerate(history.history):
            step_data = {
                "step_number": i + 1,
                "timestamp": datetime.now().isoformat(),
                "url": h.state.url if h.state else '',
                "title": h.state.title if h.state else '',
            }
            
            if h.model_output:
                thinking_text = h.model_output.current_state.thinking
                step_data["thinking"] = BrowserUseService._translate_thinking(thinking_text)
                step_data["evaluation"] = h.model_output.current_state.evaluation_previous_goal
                step_data["memory"] = h.model_output.current_state.memory
                step_data["next_goal"] = h.model_output.current_state.next_goal
                
                step_data["actions"] = []
                for action in h.model_output.action:
                    action_dict = action.model_dump(exclude_none=True)
                    action_dict["action_name"] = BrowserUseService._format_action_name(action_dict)
                    step_data["actions"].append(action_dict)
            else:
                step_data["actions"] = []
            
            if h.result:
                step_data["results"] = [
                    r.model_dump(exclude_none=True)
                    for r in h.result
                ]
            
            history_data["steps"].append(step_data)
        
        is_done = history.is_done()
        is_successful = history.is_successful()
        final_url = history.urls()[-1] if history.urls() else ""
        
        history_data["final_state"]["url"] = final_url
        history_data["final_state"]["success"] = is_done and (is_successful is not False)
        
        # 尝试从 memory 中提取每条用例的结果
        case_results = {}
        for tc in test_cases:
            case_results[tc.id] = {
                "title": tc.title,
                "status": "unknown"  # 默认未知，后续可以通过分析 memory 确定
            }
        
        return {
            "status": "pass" if (is_done and is_successful is not False) else "fail",
            "error_message": "" if (is_done and is_successful is not False) else "批量测试未完成或部分失败",
            "total_steps": history_data["total_steps"],
            "history": history_data,
            "final_url": final_url,
            "case_results": case_results
        }
