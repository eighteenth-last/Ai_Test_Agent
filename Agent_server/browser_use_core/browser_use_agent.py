"""
BrowserUseAgent - 适配 browser-use 0.11.1 的增强 Agent

主要功能:
- Token 统计和成本计算
- 截图自动保存
- 支持多种 LLM Provider
- 增强的错误处理

作者: Ai_Test_Agent Team
版本: 3.0 (browser-use 0.11.1)
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

load_dotenv()
logger = logging.getLogger(__name__)

# 截图保存目录
BUG_IMG_SAVE_PATH = Path(r"R:\Code\Python\Python_selenium_test_Agent\Ai_Test_Agent\save_floder\bug_img")
BUG_IMG_SAVE_PATH.mkdir(parents=True, exist_ok=True)


class TokenUsageTracker:
    """Token 使用量跟踪器"""
    
    def __init__(self):
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self.cached_tokens: int = 0
        self.invocations: int = 0
        self.start_time: datetime = datetime.now()
        self.usage_history: List[Dict[str, Any]] = []
    
    def add_usage(self, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0):
        """添加一次 token 使用记录"""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        self.cached_tokens += cached_tokens
        self.invocations += 1
        
        self.usage_history.append({
            "timestamp": datetime.now().isoformat(),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
            "total": prompt_tokens + completion_tokens
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """获取使用量摘要"""
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cached_tokens": self.cached_tokens,
            "invocations": self.invocations,
            "elapsed_seconds": elapsed_time,
            "tokens_per_second": self.total_tokens / elapsed_time if elapsed_time > 0 else 0
        }


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
        
        # 初始化 Token 跟踪器
        self.token_tracker = TokenUsageTracker()
        
        # 初始化截图管理器
        self.screenshot_manager = ScreenshotManager(self.screenshot_save_dir)
        
        # 初始化 token 计数器
        self._last_prompt_tokens = 0
        self._last_completion_tokens = 0
        self._last_cached_tokens = 0
        
        logger.info(f"[BrowserUseAgent] 初始化完成 - Token跟踪: {self.enable_token_tracking}, 自动截图: {self.enable_auto_screenshot}")
    
    async def _track_token_usage(self):
        """从 token_cost_service 提取使用量"""
        if not self.enable_token_tracking:
            return
        
        try:
            # 获取所有注册的 LLM 的使用量
            if hasattr(self, 'token_cost_service') and self.token_cost_service:
                for instance_id, llm in self.token_cost_service.registered_llms.items():
                    usage = self.token_cost_service.get_usage_tokens_for_model(llm.model)
                    if usage.total_tokens > 0:
                        # 更新跟踪器（增量计算）
                        new_prompt = usage.prompt_tokens - self._last_prompt_tokens
                        new_completion = usage.completion_tokens - self._last_completion_tokens
                        new_cached = usage.prompt_cached_tokens - self._last_cached_tokens
                        
                        if new_prompt > 0 or new_completion > 0:
                            self.token_tracker.add_usage(new_prompt, new_completion, new_cached)
                        
                        self._last_prompt_tokens = usage.prompt_tokens
                        self._last_completion_tokens = usage.completion_tokens
                        self._last_cached_tokens = usage.prompt_cached_tokens
        except Exception as e:
            logger.debug(f"Token 跟踪失败: {e}")
    
    async def _auto_screenshot_on_error(self, error_message: str = ""):
        """错误时自动截图"""
        if not self.enable_auto_screenshot:
            return None
        
        try:
            # 获取当前页面
            if hasattr(self, 'browser_session') and self.browser_session:
                page = await self.browser_session.get_current_page()
                if page:
                    # 清理前缀中的特殊字符
                    safe_prefix = "".join(c if c.isalnum() or c in "_-" else "_" for c in error_message[:20]) if error_message else "error"
                    prefix = f"error_{safe_prefix}" if safe_prefix else "error"
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
        
        # 重置 token 计数器
        self._last_prompt_tokens = 0
        self._last_completion_tokens = 0
        self._last_cached_tokens = 0
        
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
        - 每步后跟踪 token 使用量
        """
        try:
            await super().step(step_info)
            
            # 每步后跟踪 token 使用量
            await self._track_token_usage()
            
        except Exception as e:
            logger.error(f"[BrowserUseAgent] 步骤 {step_info.step_number} 执行失败: {e}")
            
            # 步骤失败时截图
            await self._auto_screenshot_on_error(f"step_{step_info.step_number}_error")
            
            raise
    
    def get_token_usage(self) -> Dict[str, Any]:
        """获取 Token 使用量统计"""
        return self.token_tracker.get_summary()
    
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
