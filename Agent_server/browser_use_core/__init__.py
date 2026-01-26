"""
Browser-Use Core Package (0.11.1)

包含适配 browser-use 0.11.1 的核心组件:
- BrowserUseAgent: 增强的 Agent (支持 token 跟踪和自动截图)
- TokenStatisticsService: Token 统计服务
"""

from .browser_use_agent import BrowserUseAgent, create_browser_use_agent, TokenUsageTracker, ScreenshotManager
from .token_service import TokenStatisticsService

__all__ = [
    'BrowserUseAgent',
    'create_browser_use_agent',
    'TokenUsageTracker',
    'ScreenshotManager',
    'TokenStatisticsService',
]
