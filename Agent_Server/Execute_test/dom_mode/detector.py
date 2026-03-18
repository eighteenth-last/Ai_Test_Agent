"""
DOM 丰富度检测器

每次访问新页面时执行 JS 脚本，判断是否切换到 DOM 模式。
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# DOM 丰富度判断阈值
DOM_INTERACTIVE_THRESHOLD = int(10)   # 交互元素最少数量
DOM_TOTAL_THRESHOLD = int(50)         # 总节点最少数量

# 检测脚本：统计交互元素和总节点数
_DOM_RICHNESS_SCRIPT = """
(function() {
  var interactive = document.querySelectorAll(
    'button, a[href], input, select, textarea, ' +
    '[role="button"], [role="link"], [role="menuitem"], ' +
    '[onclick], [tabindex]:not([tabindex="-1"])'
  ).length;
  var total = document.querySelectorAll('*').length;
  var rich = interactive >= %d && total >= %d;
  return JSON.stringify({ interactive: interactive, total: total, rich: rich });
})()
""" % (DOM_INTERACTIVE_THRESHOLD, DOM_TOTAL_THRESHOLD)


class DomRichnessDetector:
    """
    DOM 丰富度检测器

    通过 browser-use BrowserSession 执行 JS 脚本，
    判断当前页面是否具备足够的 DOM 节点以支持 DOM 模式。
    """

    @staticmethod
    async def detect(browser_session) -> Dict:
        """
        在当前页面执行 DOM 检测脚本。

        Args:
            browser_session: browser-use BrowserSession 实例

        Returns:
            {
                "rich": bool,          # 是否 DOM 丰富
                "interactive": int,    # 交互元素数量
                "total": int,          # 总节点数量
                "mode": str,           # "dom" | "vision"
                "error": str | None    # 检测失败时的错误信息
            }
        """
        try:
            # 获取当前页面对象（Playwright Page）
            page = await DomRichnessDetector._get_page(browser_session)
            if page is None:
                logger.warning("[DomDetector] 无法获取页面对象，回退到视觉模式")
                return _fallback_result("无法获取页面对象")

            result_str = await page.evaluate(_DOM_RICHNESS_SCRIPT)

            import json
            data = json.loads(result_str) if isinstance(result_str, str) else result_str

            rich = bool(data.get("rich", False))
            interactive = int(data.get("interactive", 0))
            total = int(data.get("total", 0))
            mode = "dom" if rich else "vision"

            logger.info(
                f"[DomDetector] 检测结果: interactive={interactive}, total={total}, "
                f"rich={rich} → 模式={mode}"
            )
            return {
                "rich": rich,
                "interactive": interactive,
                "total": total,
                "mode": mode,
                "error": None,
            }

        except Exception as e:
            logger.warning(f"[DomDetector] 检测失败，回退到视觉模式: {e}")
            return _fallback_result(str(e))

    @staticmethod
    async def _get_page(browser_session):
        """从 BrowserSession 中提取 Playwright Page 对象"""
        try:
            # browser-use 0.11.x: browser_session.context.pages
            if hasattr(browser_session, "context") and browser_session.context:
                pages = browser_session.context.pages
                if pages:
                    return pages[-1]  # 取最新页面
            # 兼容旧版本
            if hasattr(browser_session, "page") and browser_session.page:
                return browser_session.page
        except Exception as e:
            logger.debug(f"[DomDetector] 获取页面对象异常: {e}")
        return None

    @staticmethod
    def is_rich(detect_result: Dict) -> bool:
        """快捷判断：检测结果是否为 DOM 丰富"""
        return detect_result.get("rich", False)


def _fallback_result(error_msg: Optional[str] = None) -> Dict:
    """返回回退结果（视觉模式）"""
    return {
        "rich": False,
        "interactive": 0,
        "total": 0,
        "mode": "vision",
        "error": error_msg,
    }
