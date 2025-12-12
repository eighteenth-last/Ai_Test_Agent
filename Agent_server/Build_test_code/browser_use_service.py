"""
Browser-Use 执行服务 - 原生版本

使用 browser-use 0.3.3 原生的 LLM 和 Agent，无需任何适配层

作者: Ai_Test_Agent Team
版本: 2.0 (原生实现)
"""

import asyncio
import json
import time
import os
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import TestCase, TestResult
from Build_test_code.task_manager import get_task_manager

# 使用 browser-use 原生的 LLM（不是 LangChain）
from browser_use.llm.openai.chat import ChatOpenAI
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig

load_dotenv()


class BrowserUseService:
    """
    Browser-Use 测试执行服务 (原生版本)
    
    使用 browser-use 0.3.3 原生 API，无需适配层
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
        使用 browser-use 原生 Agent 执行测试
        
        Args:
            test_case_id: 测试用例 ID
            db: 数据库会话
            headless: 无头模式
            max_steps: 最大执行步数
            use_vision: 是否启用视觉
            max_actions: 每步最大动作数
        
        Returns:
            执行结果字典
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
        
        # 2. 构建任务描述
        task_description = BrowserUseService._build_task_description(test_case)
        
        start_time = time.time()
        
        # 创建任务
        task_manager = get_task_manager()
        task_manager.create_task(test_case_id, test_case_id)
        
        try:
            # 3. 创建 LLM（使用 browser-use 原生的 ChatOpenAI）
            print(f"[BrowserUse] 🔧 LLM配置: model={os.getenv('LLM_MODEL')}, base_url={os.getenv('LLM_BASE_URL')}")
            
            llm = ChatOpenAI(
                model=os.getenv('LLM_MODEL'),
                api_key=os.getenv('LLM_API_KEY'),
                base_url=os.getenv('LLM_BASE_URL'),
                temperature=float(os.getenv('LLM_TEMPERATURE', '0.0')),
            )
            
            # 4. 创建浏览器配置 参考web ui 的浏览器设置
            window_width = int(os.getenv('BROWSER_WINDOW_WIDTH', '1920'))
            window_height = int(os.getenv('BROWSER_WINDOW_HEIGHT', '1200'))
            
            browser_config = BrowserConfig(
                headless=headless,
                disable_security=os.getenv('DISABLE_SECURITY', 'false').lower() == 'true',
                extra_browser_args=[
                    '--disable-blink-features=AutomationControlled',  # 隐藏自动化特征
                    '--disable-infobars',  # 禁用信息栏
                    '--disable-extensions',  # 禁用扩展
                    '--no-first-run',  # 跳过首次运行
                    '--no-default-browser-check',  # 跳过默认浏览器检查
                    '--disable-popup-blocking',  # 禁用弹窗阻止
                    '--disable-translate',  # 禁用翻译提示
                    f'--window-size={window_width},{window_height}',  # 设置窗口大小
                    '--start-maximized',  # 最大化窗口
                ],
            )
            browser = Browser(config=browser_config)
            
            # 5. 创建 Agent（使用 browser-use 原生的 Agent）
            print(f"[BrowserUse] 🚀 开始执行测试: {test_case.title}")
            print(f"[BrowserUse] ⚙️  配置: max_steps={max_steps}, vision={use_vision}, headless={headless}")
            
            agent = Agent(
                task=task_description,
                llm=llm,
                browser=browser,
                use_vision=use_vision,
                max_actions_per_step=max_actions,
            )
            
            # 6. 执行测试（使用 Task 以支持取消）
            # 创建可取消的任务
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
                        
                        # 等待任务取消完成（最多等待2秒）
                        try:
                            await asyncio.wait_for(task, timeout=2.0)
                        except asyncio.TimeoutError:
                            print(f"[BrowserUse] ⚠️ 任务未在2秒内完成，强制取消")
                        except asyncio.CancelledError:
                            print(f"[BrowserUse] ✓ 任务已被取消")
                        except Exception as e:
                            print(f"[BrowserUse] ⚠️ 等待任务时出错: {e}")
                        
                        # 强制关闭浏览器
                        try:
                            await browser.close()
                            print(f"[BrowserUse] ✓ 浏览器已关闭")
                        except Exception as e:
                            print(f"[BrowserUse] ⚠️ 关闭浏览器时出错: {e}")
                        
                        raise Exception("用户手动停止")
                    
                    # 检查暂停
                    await task_manager.check_pause(test_case_id)
                    
                    await asyncio.sleep(0.2)  # 每0.2秒检查一次
                
                history = task.result()
            except asyncio.CancelledError:
                print(f"[BrowserUse] ✓ 任务已被取消")
                raise Exception("用户手动停止")
            
            # 7. 处理执行结果
            execution_time = int(time.time() - start_time)
            execution_result = BrowserUseService._process_execution_result(
                history, test_case, execution_time
            )
            
            # 8. 保存到数据库
            test_result = TestResult(
                test_code_id=None,
                test_case_id=test_case_id,
                execution_log=json.dumps(execution_result["history"], ensure_ascii=False, indent=2),
                screenshots=[],
                status=execution_result["status"],
                error_message=execution_result["error_message"],
                duration=execution_time
            )
            
            db.add(test_result)
            db.commit()
            db.refresh(test_result)
            
            print(f"[BrowserUse] {'✅ 成功' if execution_result['status'] == 'pass' else '❌ 失败'}")
            print(f"[BrowserUse] 📊 共执行 {execution_result['total_steps']} 步，耗时 {execution_time} 秒")
            
            # 9. 如果测试失败，分析 Bug
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
                    "bug_analysis": bug_analysis_result
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
    def _build_task_description(test_case: TestCase) -> str:
        """构建给 Agent 的任务描述"""
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
2. 严格按照步骤顺序执行
3. 每个步骤执行后验证是否成功
4. 遇到问题时智能调整策略（如元素未找到，尝试滚动或等待）
5. 关键步骤建议使用 save_screenshot 保存截图验证（PNG格式）
6. ⚠️ 重要：如果测试失败或遇到错误，必须先使用 save_screenshot 保存当前页面截图，然后再调用 done 动作
7. 完成所有步骤后明确说明"测试完成"
8. 如果无法继续，说明原因并停止

【成功标准】
所有步骤顺利执行且预期结果达成
"""
        return task.strip()
    
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
                step_data["thinking"] = h.model_output.current_state.thinking
                step_data["evaluation"] = h.model_output.current_state.evaluation_previous_goal
                step_data["memory"] = h.model_output.current_state.memory
                step_data["next_goal"] = h.model_output.current_state.next_goal
                
                # 提取执行的动作
                step_data["actions"] = [
                    action.model_dump(exclude_none=True)
                    for action in h.model_output.action
                ]
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
