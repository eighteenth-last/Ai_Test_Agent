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

from database.connection import TestCase, TestResult
from Build_test_code.task_manager import get_task_manager
from Build_test_code.custom_actions import register_custom_actions

# browser-use 0.11.1 imports
from browser_use import Agent, BrowserSession, BrowserProfile
from browser_use.tools.service import Tools

# Token 统计服务
from browser_use_core.token_service import TokenStatisticsService
from browser_use_core.browser_use_agent import BrowserUseAgent, ScreenshotManager, BUG_IMG_SAVE_PATH

load_dotenv()


# 答题相关关键词
ANSWER_KEYWORDS = [
    '错题再练', '错题集', '练习', '答题', '做题',
    '完成题目', '完成所有题目', '提交答案',
    '开始答题', '进入练习', '开始练习',
    'practice', 'exercise', 'answer', 'question',
]


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
            
            # 添加中文系统提示
            chinese_system_message = """
重要提示：
1. 请使用中文进行思考和描述
2. 所有的 thinking（思考过程）、evaluation（评估）、memory（记忆）、next_goal（下一步目标）都必须使用中文
3. 在描述操作时，使用清晰的中文说明
4. 例如：
   - thinking: "我需要点击登录按钮来完成登录操作"
   - next_goal: "输入用户名和密码"
   - evaluation: "上一步成功访问了登录页面"
"""
            
            # 使用增强版 Agent，启用 token 跟踪和自动截图
            agent = BrowserUseAgent(
                task=task_description,
                llm=llm,
                browser_session=browser_session,
                tools=tools,
                use_vision=use_vision,
                max_actions_per_step=max_actions,
                extend_system_message=chinese_system_message,
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
            
            # 9. 保存到数据库
            try:
                test_result = TestResult(
                    test_code_id=None,
                    test_case_id=test_case_id,
                    execution_log=json.dumps(execution_result["history"], ensure_ascii=False, indent=2),
                    screenshots=bug_screenshots,
                    status=execution_result["status"],
                    error_message=execution_result["error_message"],
                    duration=execution_time
                )
                
                db.add(test_result)
                db.commit()
                db.refresh(test_result)
                
                print(f"[BrowserUse] ✓ 测试结果已保存到数据库，ID: {test_result.id}")
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
                        test_result_id=test_result.id,
                        execution_history=execution_result["history"],
                        error_message=execution_result.get("error_message", "测试未完成或失败"),
                        db=db
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
            
            test_result = TestResult(
                test_code_id=None,
                test_case_id=test_case_id,
                execution_log=json.dumps({"message": "用户手动停止"}, ensure_ascii=False),
                screenshots=[],
                status="fail",
                error_message="用户手动停止",
                duration=execution_time
            )
            
            db.add(test_result)
            db.commit()
            
            return {
                "success": False,
                "message": "测试已被用户停止",
                "data": {
                    "result_id": test_result.id,
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
            test_result = TestResult(
                test_code_id=None,
                test_case_id=test_case_id,
                execution_log=json.dumps({"error": error_msg, "trace": error_trace}, ensure_ascii=False),
                screenshots=[],
                status="fail",
                error_message=error_msg,
                duration=execution_time
            )
            
            db.add(test_result)
            db.commit()
            db.refresh(test_result)
            
            # ========== 新增：Bug 分析 ==========
            bug_analysis_result = None
            try:
                from Bug_Analysis.service import BugAnalysisService
                
                print("[BrowserUse] 🔍 正在分析 Bug...")
                
                # 分析 Bug
                bug_analysis_result = await BugAnalysisService.analyze_bug_from_execution(
                    test_case_id=test_case_id,
                    test_result_id=test_result.id,
                    execution_history={"error": error_msg, "trace": error_trace},
                    error_message=error_msg,
                    db=db
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
7. 关键步骤建议使用 save_screenshot 保存截图验证（PNG格式）
8. ⚠️ 重要：如果测试失败或遇到错误，必须先使用 save_screenshot 保存当前页面截图，然后再调用 done 动作
9. 完成所有步骤后明确说明"测试完成"
10. 如果连续3次无法找到元素，说明原因并停止

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
            "go_to_url": "访问网址",
            "scroll": "滚动页面",
            "wait": "等待",
            "done": "完成",
            "save_screenshot": "保存截图",
            "extract_content": "提取内容",
            "go_back": "返回",
            "switch_tab": "切换标签页",
            "open_tab": "打开新标签页",
            "close_tab": "关闭标签页",
            "auto_answer": "自动答题",
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
