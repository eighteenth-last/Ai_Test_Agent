"""
BrowserUseAgent - 从 web-ui 移植过来的增强Agent

相比 browser-use 原生 Agent，增强了:
- 自定义 tool calling 方法支持
- 更好的错误处理和控制流

作者: Web-UI Team (移植到 Ai_Test_Agent)
"""
from __future__ import annotations

import asyncio
import logging
import os

from browser_use.agent.gif import create_history_gif
from browser_use.agent.service import Agent, AgentHookFunc
from browser_use.agent.views import (
    ActionResult,
    AgentHistory,
    AgentHistoryList,
    AgentStepInfo,
)
from browser_use.browser.views import BrowserStateHistory
from browser_use.utils import time_execution_async
from dotenv import load_dotenv

# 尝试导入 ToolCallingMethod，如果不存在则使用字符串类型
try:
    from browser_use.agent.views import ToolCallingMethod
except ImportError:
    # browser-use 0.3.3 可能没有这个类型，使用字符串
    ToolCallingMethod = str

# 尝试导入 is_model_without_tool_support
try:
    from browser_use.agent.message_manager.utils import is_model_without_tool_support
except ImportError:
    # 如果不存在，提供一个默认实现
    def is_model_without_tool_support(model_name: str) -> bool:
        """检查模型是否不支持 tool calling"""
        # 简单的启发式检查
        unsupported_keywords = ['claude-2', 'gpt-3.5-turbo-instruct']
        return any(keyword in model_name.lower() for keyword in unsupported_keywords)

load_dotenv()
logger = logging.getLogger(__name__)

SKIP_LLM_API_KEY_VERIFICATION = (
        os.environ.get("SKIP_LLM_API_KEY_VERIFICATION", "false").lower()[0] in "ty1"
)


class BrowserUseAgent(Agent):
    def _set_tool_calling_method(self):
        """
        设置 tool calling 方法
        
        这是关键！不同的 LLM 需要不同的 tool calling 方法
        """
        tool_calling_method = self.settings.tool_calling_method
        if tool_calling_method == 'auto':
            # 检查是否是不支持 tool 的模型
            if is_model_without_tool_support(self.model_name):
                logger.info(f"[BrowserUseAgent] 模型 {self.model_name} 不支持 tool calling，使用 'raw' 模式")
                return 'raw'
            elif self.chat_model_library == 'ChatGoogleGenerativeAI':
                return None
            elif self.chat_model_library == 'ChatOpenAI':
                # Qwen 通过 OpenAI 兼容接口，使用 function_calling
                logger.info(f"[BrowserUseAgent] 使用 function_calling 模式")
                return 'function_calling'
            elif self.chat_model_library == 'AzureChatOpenAI':
                return 'function_calling'
            else:
                logger.info(f"[BrowserUseAgent] 未知模型库 {self.chat_model_library}，使用默认模式")
                return None
        else:
            logger.info(f"[BrowserUseAgent] 使用指定的 tool calling 方法: {tool_calling_method}")
            return tool_calling_method
    @time_execution_async("--run (agent)")
    async def run(
            self, max_steps: int = 100, on_step_start: AgentHookFunc | None = None,
            on_step_end: AgentHookFunc | None = None
    ) -> AgentHistoryList:
        """Execute the task with maximum number of steps"""

        loop = asyncio.get_event_loop()

        # Set up the Ctrl+C signal handler with callbacks specific to this agent
        from browser_use.utils import SignalHandler

        signal_handler = SignalHandler(
            loop=loop,
            pause_callback=self.pause,
            resume_callback=self.resume,
            custom_exit_callback=None,  # No special cleanup needed on forced exit
            exit_on_second_int=True,
        )
        signal_handler.register()

        try:
            self._log_agent_run()

            # Execute initial actions if provided
            if self.initial_actions:
                result = await self.multi_act(self.initial_actions, check_for_new_elements=False)
                self.state.last_result = result

            for step in range(max_steps):
                # Check if waiting for user input after Ctrl+C
                if self.state.paused:
                    signal_handler.wait_for_resume()
                    signal_handler.reset()

                # Check if we should stop due to too many failures
                if self.state.consecutive_failures >= self.settings.max_failures:
                    logger.error(f'❌ Stopping due to {self.settings.max_failures} consecutive failures')
                    break

                # Check control flags before each step
                if self.state.stopped:
                    logger.info('Agent stopped')
                    break

                while self.state.paused:
                    await asyncio.sleep(0.2)  # Small delay to prevent CPU spinning
                    if self.state.stopped:  # Allow stopping while paused
                        break

                if on_step_start is not None:
                    await on_step_start(self)

                step_info = AgentStepInfo(step_number=step, max_steps=max_steps)
                await self.step(step_info)

                if on_step_end is not None:
                    await on_step_end(self)

                if self.state.history.is_done():
                    if self.settings.validate_output and step < max_steps - 1:
                        if not await self._validate_output():
                            continue

                    await self.log_completion()
                    break
            else:
                error_message = 'Failed to complete task in maximum steps'

                self.state.history.history.append(
                    AgentHistory(
                        model_output=None,
                        result=[ActionResult(error=error_message, include_in_memory=True)],
                        state=BrowserStateHistory(
                            url='',
                            title='',
                            tabs=[],
                            interacted_element=[],
                            screenshot=None,
                        ),
                        metadata=None,
                    )
                )

                logger.info(f'❌ {error_message}')

            return self.state.history

        except KeyboardInterrupt:
            # Already handled by our signal handler, but catch any direct KeyboardInterrupt as well
            logger.info('Got KeyboardInterrupt during execution, returning current history')
            return self.state.history

        finally:
            # Unregister signal handlers before cleanup
            signal_handler.unregister()

            await self.close()
