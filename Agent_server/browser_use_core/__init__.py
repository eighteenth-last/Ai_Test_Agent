"""
Browser-Use Core Package (0.11.1)

包含适配 browser-use 0.11.1 的核心组件:
- BrowserUseAgent: 增强的 Agent (支持 token 跟踪和自动截图)
- TokenTracker: 新的 Token 统计跟踪器（browser-use 0.11.1 风格）
"""

from .browser_use_agent import BrowserUseAgent, create_browser_use_agent, ScreenshotManager

__all__ = [
    'BrowserUseAgent',
    'create_browser_use_agent',
    'ScreenshotManager',
]
