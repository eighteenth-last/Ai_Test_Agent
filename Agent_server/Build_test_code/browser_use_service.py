"""
Browser-Use 执行服务 - 完全重写版本

使用 web-ui 的核心组件实现更强大的浏览器自动化:
- BrowserUseAgent: 增强的 Agent
- CustomBrowser: 自定义浏览器配置  
- CustomController: 自定义动作 + MCP 工具

作者: Web-UI Team (移植并适配到 Ai_Test_Agent)
版本: 2.0 (重写版)
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
from Api_request.llm_client import get_llm_client

# 导入 web-ui 的核心组件
from browser_use_core import (
    BrowserUseAgent,
    CustomBrowser,
    CustomBrowserContext,
    CustomController
)

# 导入 browser-use 配置类
from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContextConfig

load_dotenv()


class BrowserUseService:
    """
    Browser-Use 测试执行服务 (重写版)
    
    使用 web-ui 的成熟架构替代旧实现
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
        使用 BrowserUseAgent 执行测试
        
        Args:
            test_case_id: 测试用例 ID
            db: 数据库会话
            headless: 无头模式 (None=从.env读取)
            max_steps: 最大执行步数 (None=从.env读取)
            use_vision: 是否启用视觉 (None=从.env读取)
            max_actions: 每步最大动作数 (None=从.env读取)
        
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
        browser = None
        context = None
        
        try:
            # 3. 初始化 LLM
            # 注意: BrowserUseAgent 需要 LangChain 兼容的 LLM 对象
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                print("[Warning] langchain_openai not found, trying langchain_community")
                from langchain_community.chat_models import ChatOpenAI

            llm = ChatOpenAI(
                base_url=os.getenv('LLM_BASE_URL'),
                api_key=os.getenv('LLM_API_KEY'),
                model=os.getenv('LLM_MODEL'),
                temperature=0.0,
            )
            
            # 4. 配置浏览器
            browser_config = BrowserConfig(
                headless=headless,
                disable_security=os.getenv('DISABLE_SECURITY', 'false').lower() == 'true',
                extra_browser_args=[],
                chrome_remote_debugging_port=int(os.getenv('BROWSER_DEBUGGING_PORT', '9222')),
                new_context_config=BrowserContextConfig(
                    window_width=int(os.getenv('BROWSER_WINDOW_WIDTH', '1280')),
                    window_height=int(os.getenv('BROWSER_WINDOW_HEIGHT', '1100'))
                )
            )
            
            # 5. 初始化 CustomBrowser
            browser = CustomBrowser(config=browser_config)
            
            # 6. 创建浏览器上下文
            context = await browser.new_context()
            
            # 7. 初始化 CustomController (带 MCP 支持)
            controller = CustomController()
            
            # TODO: 如果需要 MCP 工具,在这里配置
            #  mcp_config = {...}
            # await controller.setup_mcp_client(mcp_config)
            
            # 8. 创建 BrowserUseAgent
            # 设置 OpenAI 环境变量以满足 Mem0 (Memory) 的依赖检查，即使禁用了 memory
            os.environ["OPENAI_API_KEY"] = os.getenv('LLM_API_KEY', '')
            os.environ["OPENAI_BASE_URL"] = os.getenv('LLM_BASE_URL', '')
            
            # 注意: browser-use 的 Agent 基类不接受 settings 参数
            # 相关配置直接作为参数传入
            agent = BrowserUseAgent(
                task=task_description,
                llm=llm,
                browser=browser,
                browser_context=context,
                controller=controller,
                use_vision=use_vision,
                max_actions_per_step=max_actions
            )
            
            print(f"[BrowserUse] 🚀 开始执行测试: {test_case.title}")
            print(f"[BrowserUse] ⚙️  配置: max_steps={max_steps}, vision={use_vision}, headless={headless}")
            
            # 10. 执行测试
            history = await agent.run(max_steps=max_steps)
            
            # 11. 处理执行结果
            execution_time = int(time.time() - start_time)
            execution_result = BrowserUseService._process_execution_result(
                history, test_case, execution_time
            )
            
            # 12. 保存到数据库
            test_result = TestResult(
                test_code_id=None,  # Browser-Use 不生成代码文件
                test_case_id=test_case_id,
                execution_log=json.dumps(execution_result["history"], ensure_ascii=False, indent=2),
                screenshots=[],  # TODO: 保存截图路径
                status=execution_result["status"],
                error_message=execution_result["error_message"],
                duration=execution_time
            )
            
            db.add(test_result)
            db.commit()
            db.refresh(test_result)
            
            print(f"[BrowserUse] {'✅ 成功' if execution_result['status'] == 'pass' else '❌ 失败'}")
            print(f"[BrowserUse] 📊 共执行 {execution_result['total_steps']} 步，耗时 {execution_time} 秒")
            
            # 自动生成测试报告
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
                    "report": report_data  # 返回报告数据
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
            
            return {
                "success": False,
                "message": f"测试执行失败: {error_msg}",
                "error_details": error_trace
            }
        
        finally:
            # 清理资源
            if context:
                try:
                    await context.close()
                except:
                    pass
            
            if browser:
                try:
                    await browser.close()
                except:
                    pass
    
    @staticmethod
    def _build_task_description(test_case: TestCase) -> str:
        """构建给 LLM 的任务描述"""
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
        
        task = f"""
【测试任务】
标题：{test_case.title}

【前置条件】
{test_case.precondition or '无'}

【执行步骤】
{formatted_steps}

【预期结果】
{test_case.expected}

【测试数据】
{formatted_data if formatted_data else '无'}

【重要提示】
1. 严格按照步骤顺序执行
2. 每个步骤执行后验证是否成功
3. 遇到问题时智能调整策略（如元素未找到，尝试滚动或等待）
4. 关键步骤建议截图验证
5. 完成所有步骤后明确说明"测试完成"
6. 如果无法继续，说明原因并停止

【成功标准】
所有步骤顺利执行且预期结果达成
"""
        return task.strip()
    
    @staticmethod
    def _process_execution_result(history, test_case: TestCase, execution_time: int) -> Dict[str, Any]:
        """处理 Browser-Use 的执行结果"""
        history_data = {
            "total_steps": 0,
            "steps": [],
            "final_state": {
                "url": "",
                "success": False
            }
        }
        
        # 提取执行步骤
        if hasattr(history, 'history') and history.history:
            history_data["total_steps"] = len(history.history)
            
            for i, step in enumerate(history.history):
                step_data = {
                    "step_number": i + 1,
                    "timestamp": datetime.now().isoformat(),
                    "url": getattr(step.state, 'url', '') if hasattr(step, 'state') else '',
                    "title": getattr(step.state, 'title', '') if hasattr(step, 'state') else '',
                }
                
                # 提取 LLM 的思考过程
                if hasattr(step, 'model_output'):
                    if hasattr(step.model_output, 'current_state'):
                        step_data["thinking"] = getattr(step.model_output.current_state, 'think', '')
                    
                    # 提取执行的动作
                    if hasattr(step.model_output, 'action'):
                        actions = step.model_output.action if isinstance(step.model_output.action, list) else  [step.model_output.action]
                        step_data["actions"] = [
                            {
                                "action_name": action.__class__.__name__,
                                "params": str(action.__dict__)
                            }
                            for action in actions
                        ]
                    else:
                        step_data["actions"] = []
                else:
                    step_data["thinking"] = ""
                    step_data["actions"] = []
                
                history_data["steps"].append(step_data)
        
        # 判断执行状态
        is_done = history.is_done() if hasattr(history, 'is_done') and callable(history.is_done) else False
        
        # 提取最终状态
        final_res = None
        if hasattr(history, 'final_result'):
            if callable(history.final_result):
                final_res = history.final_result()
            else:
                final_res = history.final_result
        
        if final_res and isinstance(final_res, dict):
            history_data["final_state"]["url"] = final_res.get('url', '')
        else:
            # 如果是字符串或其他类型，尝试作为 URL 或忽略
             history_data["final_state"]["url"] = str(final_res) if final_res else ''
            
        history_data["final_state"]["success"] = is_done

        
        return {
            "status": "pass" if is_done else "fail",
            "error_message": "" if is_done else f"测试未完成，执行了 {history_data['total_steps']} 步后终止",
            "total_steps": history_data["total_steps"],
            "history": history_data,
            "final_url": history_data["final_state"]["url"]
        }
