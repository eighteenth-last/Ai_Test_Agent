"""
CustomBrowser - 从 web-ui 移植

相比 browser-use 原生 Browser，增强了:
- CDP/WSS 连接支持
- 更灵活的浏览器配置
- 窗口尺寸自定义

作者: Web-UI Team (移植到 Ai_Test_Agent)
"""
import asyncio
import pdb

from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import (
    BrowserContext as PlaywrightBrowserContext,
)
from playwright.async_api import (
    Playwright,
    async_playwright,
)
from browser_use.browser.browser import Browser
from playwright.async_api import BrowserContext as PlaywrightBrowserContext
import logging

from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.utils import time_execution_async
import socket

logger = logging.getLogger(__name__)

# IN_DOCKER is not available in browser-use 0.3.3, define locally
IN_DOCKER = False

# Chrome constants not available in browser-use 0.3.3, define locally
CHROME_ARGS = [
    '--no-first-run',
    '--no-default-browser-check',
    '--no-sandbox',
    '--disable-blink-features=AutomationControlled',
]

CHROME_HEADLESS_ARGS = [
    '--headless=new',
]

CHROME_DISABLE_SECURITY_ARGS = [
    '--disable-web-security',
    '--disable-site-isolation-trials',
]

CHROME_DETERMINISTIC_RENDERING_ARGS = [
    '--deterministic-mode',
]

CHROME_DOCKER_ARGS = [
    '--disable-dev-shm-usage',
]


# Screen resolution utilities not available in browser-use 0.3.3, define locally
def get_screen_resolution() -> dict:
    """Get screen resolution from environment variables"""
    import os
    width = int(os.getenv('BROWSER_WINDOW_WIDTH', '1920'))
    height = int(os.getenv('BROWSER_WINDOW_HEIGHT', '1200'))
    return {'width': width, 'height': height}


def get_window_adjustments() -> tuple:
    """Get window position adjustments, defaults to (0, 0)"""
    return (0, 0)


class CustomBrowser(Browser):

    async def new_context(self, config: BrowserContextConfig | None = None) -> 'CustomBrowser':
        """Create a browser context - returns self since Browser IS the context in browser-use 0.3.3"""
        # 在 browser-use 0.3.3 中，Browser 继承自 BrowserContext
        # new_context 只是向后兼容的方法，直接返回 self
        return self

    async def _setup_builtin_browser(self, playwright: Playwright) -> PlaywrightBrowser:
        """Sets up and returns a Playwright Browser instance with anti-detection measures."""
        assert self.config.browser_binary_path is None, 'browser_binary_path should be None if trying to use the builtin browsers'

        # Use the configured window size from new_context_config if available
        if (
                not self.config.headless
                and hasattr(self.config, 'new_context_config')
                and hasattr(self.config.new_context_config, 'window_width')
                and hasattr(self.config.new_context_config, 'window_height')
        ):
            screen_size = {
                'width': self.config.new_context_config.window_width,
                'height': self.config.new_context_config.window_height,
            }
            offset_x, offset_y = get_window_adjustments()
        elif self.config.headless:
            import os
            width = int(os.getenv('BROWSER_WINDOW_WIDTH', '1920'))
            height = int(os.getenv('BROWSER_WINDOW_HEIGHT', '1200'))
            screen_size = {'width': width, 'height': height}
            offset_x, offset_y = 0, 0
        else:
            screen_size = get_screen_resolution()
            offset_x, offset_y = get_window_adjustments()

        chrome_args = {
            f'--remote-debugging-port={self.config.chrome_remote_debugging_port}',
            *CHROME_ARGS,
            *(CHROME_DOCKER_ARGS if IN_DOCKER else []),
            *(CHROME_HEADLESS_ARGS if self.config.headless else []),
            *(CHROME_DISABLE_SECURITY_ARGS if self.config.disable_security else []),
            *(CHROME_DETERMINISTIC_RENDERING_ARGS if self.config.deterministic_rendering else []),
            f'--window-position={offset_x},{offset_y}',
            f'--window-size={screen_size["width"]},{screen_size["height"]}',
            *self.config.extra_browser_args,
        }

        # check if chrome remote debugging port is already taken,
        # if so remove the remote-debugging-port arg to prevent conflicts
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', self.config.chrome_remote_debugging_port)) == 0:
                chrome_args.remove(f'--remote-debugging-port={self.config.chrome_remote_debugging_port}')

        browser_class = getattr(playwright, self.config.browser_class)
        args = {
            'chromium': list(chrome_args),
            'firefox': [
                *{
                    '-no-remote',
                    *self.config.extra_browser_args,
                }
            ],
            'webkit': [
                *{
                    '--no-startup-window',
                    *self.config.extra_browser_args,
                }
            ],
        }

        browser = await browser_class.launch(
            channel='chromium',  # https://github.com/microsoft/playwright/issues/33566
            headless=self.config.headless,
            args=args[self.config.browser_class],
            proxy=self.config.proxy.model_dump() if self.config.proxy else None,
            handle_sigterm=False,
            handle_sigint=False,
        )
        return browser
