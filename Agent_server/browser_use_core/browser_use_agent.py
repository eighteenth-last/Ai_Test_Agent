"""
BrowserUseAgent - 适配 browser-use 0.11.1 的增强 Agent

主要功能:
- Token 统计和成本计算（基于 browser-use 0.11.1）
- 截图自动保存
- 支持多种 LLM Provider
- 增强的错误处理

作者: Ai_Test_Agent Team
版本: 4.0 (browser-use 0.11.1 + 新 TokenTracker)
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Awaitable

from dotenv import load_dotenv

# browser-use 0.11.1 imports
from browser_use.agent.service import Agent
from browser_use.agent.views import (
    ActionResult,
    AgentHistory,
    AgentHistoryList,
    AgentStepInfo,
)
from browser_use.utils import time_execution_async

# 导入新的 TokenTracker
from utils.token_tracker import TokenTracker, TokenUsage

load_dotenv()
logger = logging.getLogger(__name__)

# 截图保存目录
BUG_IMG_SAVE_PATH = Path(r"R:\Code\Python\Python_selenium_test_Agent\Ai_Test_Agent\save_floder\bug_img")
BUG_IMG_SAVE_PATH.mkdir(parents=True, exist_ok=True)


class ScreenshotManager:
    """截图管理器"""
    
    def __init__(self, save_dir: Path = BUG_IMG_SAVE_PATH):
        self.save_dir = save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots: List[str] = []
    
    async def save_screenshot(self, page, prefix: str = "bug") -> Optional[str]:
        """
        保存截图
        
        Args:
            page: Playwright Page 对象
            prefix: 文件名前缀
            
        Returns:
            保存的文件路径，失败返回 None
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}.png"
            filepath = self.save_dir / filename
            
            await page.screenshot(path=str(filepath), full_page=True)
            
            self.screenshots.append(str(filepath))
            logger.info(f"📸 截图已保存: {filepath}")
            
            return str(filepath)
        except Exception as e:
            logger.error(f"截图保存失败: {e}")
            return None
    
    def get_all_screenshots(self) -> List[str]:
        """获取所有截图路径"""
        return self.screenshots.copy()


AgentHookFunc = Callable[['BrowserUseAgent'], Awaitable[None]]


class BrowserUseAgent(Agent):
    """
    增强版 Browser-Use Agent
    
    新增功能:
    - Token 使用量跟踪
    - 自动截图保存
    - 改进的错误处理
    """
    
    def __init__(self, *args, **kwargs):
        # 提取自定义参数
        self.enable_token_tracking = kwargs.pop('enable_token_tracking', True)
        self.enable_auto_screenshot = kwargs.pop('enable_auto_screenshot', True)
        self.screenshot_save_dir = kwargs.pop('screenshot_save_dir', BUG_IMG_SAVE_PATH)
        
        # 调用父类初始化
        super().__init__(*args, **kwargs)
        
        # 初始化新的 Token 跟踪器
        self.token_tracker = TokenTracker()
        
        # 初始化截图管理器
        self.screenshot_manager = ScreenshotManager(self.screenshot_save_dir)
        
        logger.info(f"[BrowserUseAgent] 初始化完成 - Token跟踪: {self.enable_token_tracking}, 自动截图: {self.enable_auto_screenshot}")
    
    async def _track_token_usage(self, step_number: Optional[int] = None):
        """
        从 Agent 的 message_manager 提取 token 使用量
        
        Args:
            step_number: 当前步骤编号
        """
        if not self.enable_token_tracking:
            return
        
        try:
            # 设置当前步骤
            if step_number is not None:
                self.token_tracker.set_current_step(step_number)
            
            # 从 message_manager 获取最近的 token 使用情况
            if hasattr(self, 'message_manager') and hasattr(self.message_manager, 'state'):
                # 获取最后一条消息的 usage 信息
                messages = self.message_manager.state.history
                if messages and len(messages) > 0:
                    last_message = messages[-1]
                    
                    # 检查是否有 usage 信息（从 LLM 响应中获取）
                    if hasattr(last_message, 'usage') and last_message.usage:
                        usage = last_message.usage
                        
                        # 添加到 tracker
                        self.token_tracker.add_usage(
                            model_name=self.llm.model if hasattr(self.llm, 'model') else 'unknown',
                            prompt_tokens=usage.prompt_tokens,
                            completion_tokens=usage.completion_tokens,
                            prompt_cached_tokens=getattr(usage, 'prompt_cached_tokens', None),
                            prompt_cache_creation_tokens=getattr(usage, 'prompt_cache_creation_tokens', None),
                            action_type=None  # 可以从 agent state 获取当前 action
                        )
        except Exception as e:
            logger.debug(f"Token 跟踪失败: {e}")
    
    async def _auto_screenshot_on_error(self, error_message: str = ""):
        """错误时自动截图"""
        if not self.enable_auto_screenshot:
            return None
        
        try:
            if not hasattr(self, 'browser') or not self.browser:
                return None
            
            page = await self.browser.get_current_page()
            if not page:
                return None
            
            prefix = f"error_{error_message.replace(' ', '_')}"
            return await self.screenshot_manager.save_screenshot(page, prefix)
        except Exception as e:
            logger.debug(f"自动截图失败: {e}")
        
        return None
    
    @time_execution_async("--run (agent)")
    async def run(
        self, 
        max_steps: int = 100, 
        on_step_start: AgentHookFunc | None = None,
        on_step_end: AgentHookFunc | None = None
    ) -> AgentHistoryList:
        """
        执行任务
        
        增强功能:
        - Token 使用量跟踪
        - 错误时自动截图
        """
        logger.info(f"[BrowserUseAgent] 开始执行任务，最大步数: {max_steps}")
        
        try:
            # 调用父类的 run 方法
            result = await super().run(
                max_steps=max_steps,
                on_step_start=on_step_start,
                on_step_end=on_step_end
            )
            
            # 跟踪最终 token 使用量
            await self._track_token_usage()
            
            # 检查是否失败，如果失败则截图
            if result.is_done() and not result.is_successful():
                logger.warning("[BrowserUseAgent] 任务执行失败，正在保存截图...")
                await self._auto_screenshot_on_error("task_failed")
            
            return result
            
        except Exception as e:
            logger.error(f"[BrowserUseAgent] 执行错误: {e}")
            
            # 错误时自动截图
            await self._auto_screenshot_on_error(str(e)[:50])
            
            raise
    
    async def step(self, step_info: AgentStepInfo) -> None:
        """
        执行单步操作
        
        增强:
        - 每步后跟踪 token 使用量（带步骤编号）
        """
        try:
            await super().step(step_info)
            
            # 每步后跟踪 token 使用量，传递步骤编号
            await self._track_token_usage(step_number=step_info.step_number)
            
        except Exception as e:
            logger.error(f"[BrowserUseAgent] 步骤 {step_info.step_number} 执行失败: {e}")
            
            # 步骤失败时截图
            await self._auto_screenshot_on_error(f"step_{step_info.step_number}_error")
            
            raise
    
    def get_token_usage(self) -> Dict[str, Any]:
        """
        获取 Token 使用量统计（兼容旧格式）
        
        Returns:
            Dict: {'prompt_tokens': xxx, 'completion_tokens': xxx, 'total_tokens': xxx, ...}
        """
        summary = self.token_tracker.get_summary()
        
        # 转换为旧格式兼容字典
        return {
            'prompt_tokens': summary.total_prompt_tokens,
            'completion_tokens': summary.total_completion_tokens,
            'total_tokens': summary.total_tokens,
            'cached_tokens': summary.total_cached_tokens,
            'cache_creation_tokens': summary.total_cache_creation_tokens,
            'invocations': summary.total_invocations,
            'cache_hit_rate': summary.cache_hit_rate,
            'by_model': {
                model: {
                    'prompt_tokens': stats.prompt_tokens,
                    'completion_tokens': stats.completion_tokens,
                    'total_tokens': stats.total_tokens,
                    'cached_tokens': stats.cached_tokens,
                    'cache_creation_tokens': stats.cache_creation_tokens,
                    'invocations': stats.invocations,
                    'cache_hit_rate': stats.cache_hit_rate,
                    'average_tokens_per_call': stats.average_tokens_per_call
                }
                for model, stats in summary.by_model.items()
            }
        }
    
    def get_screenshots(self) -> List[str]:
        """获取所有截图路径"""
        return self.screenshot_manager.get_all_screenshots()
    
    async def save_bug_screenshot(self, prefix: str = "bug") -> Optional[str]:
        """
        手动保存 Bug 截图
        
        Args:
            prefix: 文件名前缀
            
        Returns:
            保存的文件路径
        """
        try:
            if hasattr(self, 'browser_session') and self.browser_session:
                page = await self.browser_session.get_current_page()
                if page:
                    return await self.screenshot_manager.save_screenshot(page, prefix)
        except Exception as e:
            logger.error(f"保存 Bug 截图失败: {e}")
        
        return None


def create_browser_use_agent(
    task: str,
    llm,
    browser_session=None,
    browser=None,
    tools=None,
    use_vision: bool = True,
    max_actions_per_step: int = 3,
    extend_system_message: str = None,
    calculate_cost: bool = True,
    enable_token_tracking: bool = True,
    enable_auto_screenshot: bool = True,
    screenshot_save_dir: Path = BUG_IMG_SAVE_PATH,
    **kwargs
) -> BrowserUseAgent:
    """
    创建 BrowserUseAgent 实例的工厂函数
    
    Args:
        task: 任务描述
        llm: LLM 实例
        browser_session: 浏览器会话
        browser: 浏览器实例（别名）
        tools: 工具集
        use_vision: 是否启用视觉
        max_actions_per_step: 每步最大动作数
        extend_system_message: 扩展系统消息
        calculate_cost: 是否计算成本
        enable_token_tracking: 是否启用 token 跟踪
        enable_auto_screenshot: 是否启用自动截图
        screenshot_save_dir: 截图保存目录
        **kwargs: 其他参数
        
    Returns:
        BrowserUseAgent 实例
    """
    return BrowserUseAgent(
        task=task,
        llm=llm,
        browser_session=browser_session,
        browser=browser,
        tools=tools,
        use_vision=use_vision,
        max_actions_per_step=max_actions_per_step,
        extend_system_message=extend_system_message,
        calculate_cost=calculate_cost,
        enable_token_tracking=enable_token_tracking,
        enable_auto_screenshot=enable_auto_screenshot,
        screenshot_save_dir=screenshot_save_dir,
        **kwargs
    )
