"""
Compatibility wrapper for DOM-first detection.

The implementation now lives in Exploration.browser_use_tools so the same
DOM-first adapter can be reused by exploration and execution flows.
"""

from Exploration.browser_use_tools import DomRichnessDetector

__all__ = ["DomRichnessDetector"]
