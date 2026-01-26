"""
CustomBrowserContext - 从 web-ui 移植

简单的浏览器上下文包装类

作者: Web-UI Team (移植到 Ai_Test_Agent)
"""
import json
import logging
import os

from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import BrowserContext as PlaywrightBrowserContext
from typing import Optional

logger = logging.getLogger(__name__)


class CustomBrowserContext(BrowserContext):
    def __init__(
            self,
            browser: 'Browser',
            config: BrowserContextConfig | None = None,
            **kwargs
    ):
        super(CustomBrowserContext, self).__init__(browser=browser, config=config, **kwargs)
