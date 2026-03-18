"""
DOM 模式子包

提供基于 agent-browser CLI 的 DOM 驱动测试执行能力。
当页面 DOM 节点丰富时，自动切换到 DOM 模式，替代视觉大模型。
"""
from .detector import DomRichnessDetector
from .agent_browser_client import AgentBrowserClient
from .dom_executor import DomExecutor

__all__ = ["DomRichnessDetector", "AgentBrowserClient", "DomExecutor"]
