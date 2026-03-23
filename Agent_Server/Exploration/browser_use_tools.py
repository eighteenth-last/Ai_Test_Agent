from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import platform
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DOM_INTERACTIVE_THRESHOLD = int(os.getenv("EXPLORATION_DOM_INTERACTIVE_THRESHOLD", "10"))
DOM_TOTAL_THRESHOLD = int(os.getenv("EXPLORATION_DOM_TOTAL_THRESHOLD", "50"))
MAX_INTERACTIVE_ELEMENTS = int(os.getenv("EXPLORATION_MAX_INTERACTIVE", "60"))


def find_chrome_path() -> Optional[str]:
    """Lightweight browser executable discovery without importing Execute_test.service."""
    system = platform.system()

    if system == "Windows":
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
    elif system == "Darwin":
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    else:
        paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]

    for path in paths:
        if os.path.exists(path):
            return path
    return None

_DOM_RICHNESS_SCRIPT = """
() => {
  const interactive = document.querySelectorAll(
    'button, a[href], input, select, textarea, summary, ' +
    '[role="button"], [role="link"], [role="menuitem"], ' +
    '[onclick], [tabindex]:not([tabindex="-1"])'
  ).length;
  const total = document.querySelectorAll('*').length;
  const rich = interactive >= %d && total >= %d;
  return { interactive, total, rich };
}
""" % (DOM_INTERACTIVE_THRESHOLD, DOM_TOTAL_THRESHOLD)

_DOM_SUMMARY_SCRIPT = """
() => {
  function visible(el) {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style && style.display !== 'none' && style.visibility !== 'hidden' &&
      rect.width > 0 && rect.height > 0;
  }

  function cleanText(value) {
    return (value || '').replace(/\\s+/g, ' ').trim().slice(0, 120);
  }

  function getLabel(el) {
    return cleanText(
      el.innerText ||
      el.textContent ||
      el.getAttribute('aria-label') ||
      el.getAttribute('title') ||
      el.getAttribute('placeholder') ||
      el.value ||
      ''
    );
  }

  function cssPath(el) {
    if (!el || !el.tagName) return '';
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.getAttribute('data-testid')) {
      return '[data-testid="' + CSS.escape(el.getAttribute('data-testid')) + '"]';
    }
    if (el.getAttribute('name')) {
      return el.tagName.toLowerCase() + '[name="' + CSS.escape(el.getAttribute('name')) + '"]';
    }
    const parts = [];
    let current = el;
    let depth = 0;
    while (current && current.nodeType === Node.ELEMENT_NODE && depth < 5) {
      let selector = current.tagName.toLowerCase();
      const parent = current.parentElement;
      if (parent) {
        const sameTag = Array.from(parent.children).filter(n => n.tagName === current.tagName);
        if (sameTag.length > 1) {
          selector += ':nth-of-type(' + (sameTag.indexOf(current) + 1) + ')';
        }
      }
      parts.unshift(selector);
      if (selector === 'body') break;
      current = current.parentElement;
      depth += 1;
    }
    return parts.join(' > ');
  }

  function sectionName(el) {
    const holder = el.closest('form, table, nav, section, article, aside, main, [role="dialog"]');
    if (!holder) return '';
    return cleanText(
      holder.getAttribute('aria-label') ||
      holder.getAttribute('title') ||
      holder.querySelector('h1, h2, h3, legend')?.innerText ||
      holder.className ||
      holder.tagName
    );
  }

  const allInteractive = Array.from(document.querySelectorAll(
    'button, a[href], input, select, textarea, summary, [role="button"], [role="link"], [role="menuitem"], [onclick], [tabindex]:not([tabindex="-1"])'
  ))
    .filter(visible)
    .slice(0, %d)
    .map((el, idx) => {
      const rect = el.getBoundingClientRect();
      return {
        candidate_id: 'c' + (idx + 1),
        label: getLabel(el),
        selector: cssPath(el),
        tag: (el.tagName || '').toLowerCase(),
        role: el.getAttribute('role') || '',
        element_type: el.getAttribute('type') || '',
        section: sectionName(el),
        href: el.getAttribute('href') || '',
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        placeholder: cleanText(el.getAttribute('placeholder') || ''),
        title: cleanText(el.getAttribute('title') || ''),
        aria_label: cleanText(el.getAttribute('aria-label') || ''),
        name: cleanText(el.getAttribute('name') || '')
      };
    });

  const forms = Array.from(document.forms).map((form, idx) => ({
    name: cleanText(form.getAttribute('name') || form.getAttribute('id') || ('form_' + (idx + 1))),
    submit_button: cleanText(form.querySelector('button[type="submit"], input[type="submit"], button')?.innerText || ''),
    fields: Array.from(form.querySelectorAll('input, select, textarea')).map(field => ({
      name: cleanText(field.getAttribute('name') || field.getAttribute('id') || ''),
      type: cleanText(field.getAttribute('type') || field.tagName.toLowerCase()),
      label: cleanText(field.getAttribute('aria-label') || field.getAttribute('placeholder') || ''),
      required: field.required || field.getAttribute('aria-required') === 'true',
      placeholder: cleanText(field.getAttribute('placeholder') || '')
    }))
  })).filter(item => item.fields.length > 0).slice(0, 8);

  const tables = Array.from(document.querySelectorAll('table')).filter(visible).slice(0, 5).map((table, idx) => ({
    name: cleanText(
      table.getAttribute('aria-label') ||
      table.getAttribute('title') ||
      table.closest('section, article, div')?.querySelector('h1, h2, h3, caption')?.innerText ||
      ('table_' + (idx + 1))
    ),
    columns: Array.from(table.querySelectorAll('th')).slice(0, 10).map(th => cleanText(th.innerText)).filter(Boolean),
    row_actions: Array.from(table.querySelectorAll('tbody button, tbody a[href], button, a[href]')).slice(0, 10).map(el => getLabel(el)).filter(Boolean)
  }));

  const dialogs = Array.from(document.querySelectorAll('[role="dialog"], .modal, .drawer, .ant-modal, .n-modal, .el-dialog'))
    .filter(visible)
    .map(el => cleanText(el.querySelector('h1, h2, h3, .title, .modal-title')?.innerText || el.className || 'dialog'))
    .filter(Boolean)
    .slice(0, 6);

  const pageSections = Array.from(document.querySelectorAll('h1, h2, h3, legend, nav, section, aside'))
    .filter(visible)
    .map(el => cleanText(el.innerText || el.getAttribute('aria-label') || el.className || ''))
    .filter(Boolean)
    .slice(0, 15);

  return {
    title: document.title || '',
    url: location.href,
    total_dom_nodes: document.querySelectorAll('*').length,
    interactive_elements: allInteractive,
    forms,
    tables,
    dialogs,
    page_sections: pageSections
  };
}
""" % MAX_INTERACTIVE_ELEMENTS


class DomRichnessDetector:
    @staticmethod
    async def detect(browser_session) -> Dict[str, Any]:
        page = await get_current_page(browser_session)
        if page is None:
            return _fallback_result("cannot_get_page")
        try:
            data = await evaluate_script(page, _DOM_RICHNESS_SCRIPT)
            if not isinstance(data, dict):
                raise RuntimeError(f"invalid_dom_richness:{type(data).__name__}")
            interactive = int(data.get("interactive", 0))
            total = int(data.get("total", 0))
            rich = bool(data.get("rich", False))
            mode = "dom" if rich else "vision"
            return {
                "rich": rich,
                "interactive": interactive,
                "total": total,
                "mode": mode,
                "error": None,
            }
        except Exception as exc:
            logger.warning(f"[Exploration] DOM richness detect failed: {exc}")
            return _fallback_result(str(exc))


def _fallback_result(error_msg: Optional[str] = None) -> Dict[str, Any]:
    return {
        "rich": False,
        "interactive": 0,
        "total": 0,
        "mode": "vision",
        "error": error_msg,
    }


async def detect_dom_richness(browser_session) -> Dict[str, Any]:
    return await DomRichnessDetector.detect(browser_session)


async def create_browser_session(env_info: Dict[str, Any]):
    try:
        from browser_use import BrowserSession
    except ImportError:
        from browser_use.browser import BrowserSession

    headless = env_info.get("headless", False)
    chrome_path = os.getenv("BROWSER_PATH", "").strip() or find_chrome_path()
    return BrowserSession(
        headless=headless,
        disable_security=os.getenv("DISABLE_SECURITY", "false").lower() == "true",
        executable_path=chrome_path if chrome_path else None,
        minimum_wait_page_load_time=0.5,
        wait_between_actions=0.3,
        keep_alive=True,
    )


async def ensure_browser_started(browser_session):
    if hasattr(browser_session, "start"):
        await browser_session.start()
    return browser_session


async def stop_browser(browser_session):
    if not browser_session:
        return
    if hasattr(browser_session, "kill"):
        await browser_session.kill()
    elif hasattr(browser_session, "stop"):
        await browser_session.stop()


async def get_current_page(browser_session):
    try:
        if hasattr(browser_session, "must_get_current_page"):
            return await browser_session.must_get_current_page()
    except Exception:
        pass
    try:
        if hasattr(browser_session, "context") and browser_session.context and browser_session.context.pages:
            return browser_session.context.pages[-1]
    except Exception:
        pass
    try:
        if hasattr(browser_session, "page") and browser_session.page:
            return browser_session.page
    except Exception:
        pass
    return None


def _decode_eval_result(result: Any) -> Any:
    if isinstance(result, str):
        text = result.strip()
        if not text:
            return text
        if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
            try:
                return json.loads(text)
            except Exception:
                return result
    return result


async def evaluate_script(page, script: str, *args):
    result = await page.evaluate(script, *args)
    return _decode_eval_result(result)


async def navigate_to(browser_session, url: str):
    page = await get_current_page(browser_session)
    if page is None:
        raise RuntimeError("cannot_get_page")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except TypeError:
        # browser-use actor Page only accepts goto(url)
        await page.goto(url)
    await wait_page_stable(browser_session)
    return page


async def wait_page_stable(browser_session, delay: float = 1.0):
    page = await get_current_page(browser_session)
    if page is None:
        return
    try:
        if hasattr(page, "wait_for_load_state"):
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass
    await asyncio.sleep(delay)


async def read_url(browser_session) -> str:
    page = await get_current_page(browser_session)
    if page is None:
        return ""
    try:
        if hasattr(page, "url"):
            return page.url
        if hasattr(page, "get_url"):
            return await page.get_url()
    except Exception:
        return ""
    return ""


async def take_screenshot(browser_session, run_id: str) -> Dict[str, str]:
    page = await get_current_page(browser_session)
    if page is None:
        return {"path": "", "base64": ""}
    temp_dir = Path(tempfile.gettempdir()) / "ai_test_agent_exploration"
    temp_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = temp_dir / f"{run_id}_{uuid.uuid4().hex[:8]}.png"
    try:
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
            with open(screenshot_path, "rb") as file:
                encoded = base64.b64encode(file.read()).decode("utf-8")
        except TypeError:
            encoded = await page.screenshot()
            screenshot_path.write_bytes(base64.b64decode(encoded))
        return {"path": str(screenshot_path), "base64": encoded}
    except Exception as exc:
        logger.warning(f"[Exploration] Screenshot failed: {exc}")
        return {"path": "", "base64": ""}


async def extract_dom_summary(browser_session) -> Dict[str, Any]:
    page = await get_current_page(browser_session)
    if page is None:
        raise RuntimeError("cannot_get_page")
    data = await evaluate_script(page, _DOM_SUMMARY_SCRIPT)
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid_dom_summary:{type(data).__name__}")
    return data


async def click_by_selector(browser_session, selector: str) -> Dict[str, Any]:
    page = await get_current_page(browser_session)
    if page is None:
        return {"success": False, "error": "cannot_get_page"}
    try:
        if hasattr(page, "locator"):
            locator = page.locator(selector).first
            await locator.click(timeout=5000)
        else:
            result = await evaluate_script(
                page,
                """(selector) => {
                  const el = document.querySelector(selector);
                  if (!el) return { success: false, error: "not_found" };
                  el.scrollIntoView({ block: "center", inline: "center" });
                  el.click();
                  return { success: true };
                }""",
                selector,
            )
            if not isinstance(result, dict) or not result.get("success"):
                return {"success": False, "error": (result or {}).get("error", "click_failed")}
        await wait_page_stable(browser_session)
        return {"success": True}
    except Exception as exc:
        logger.warning(f"[Exploration] click_by_selector failed: selector={selector}, err={exc}")
        return {"success": False, "error": str(exc)}


async def click_by_coordinates(browser_session, x: float, y: float) -> Dict[str, Any]:
    page = await get_current_page(browser_session)
    if page is None:
        return {"success": False, "error": "cannot_get_page"}
    try:
        mouse = None
        try:
            mouse_attr = getattr(page, "mouse", None)
            if asyncio.iscoroutine(mouse_attr):
                mouse = await mouse_attr
            else:
                mouse = mouse_attr
        except Exception:
            mouse = None

        if mouse is not None and hasattr(mouse, "click"):
            await mouse.click(int(x), int(y))
        else:
            result = await evaluate_script(
                page,
                """(x, y) => {
                  const el = document.elementFromPoint(x, y);
                  if (!el) return { success: false, error: "not_found" };
                  el.scrollIntoView({ block: "center", inline: "center" });
                  el.click();
                  return { success: true, tag: (el.tagName || "").toLowerCase() };
                }""",
                x,
                y,
            )
            if not isinstance(result, dict) or not result.get("success"):
                return {"success": False, "error": (result or {}).get("error", "click_failed")}
        await wait_page_stable(browser_session)
        return {"success": True}
    except Exception as exc:
        logger.warning(f"[Exploration] click_by_coordinates failed: ({x}, {y}), err={exc}")
        return {"success": False, "error": str(exc)}


async def try_basic_login(browser_session, username: str, password: str) -> bool:
    if not username or not password:
        return False
    try:
        summary = await extract_dom_summary(browser_session)
        fields: List[Dict[str, Any]] = []
        for form in summary.get("forms", []):
            fields.extend(form.get("fields", []))
        has_password = any((field.get("type") or "").lower() == "password" for field in fields)
        if not has_password:
            return False

        page = await get_current_page(browser_session)
        if page is None:
            return False

        username_selector = ""
        password_selector = ""
        for element in summary.get("interactive_elements", []):
            element_type = (element.get("element_type") or "").lower()
            tag = (element.get("tag") or "").lower()
            label = " ".join([
                element.get("label", ""),
                element.get("placeholder", ""),
                element.get("aria_label", ""),
                element.get("name", ""),
            ]).lower()
            if not username_selector and tag in {"input", "textarea"} and element_type != "password":
                if any(key in label for key in ["user", "email", "account", "账号", "用户名", "邮箱"]):
                    username_selector = element.get("selector", "")
            if not password_selector and element_type == "password":
                password_selector = element.get("selector", "")

        if not username_selector:
            for element in summary.get("interactive_elements", []):
                if (element.get("tag") or "").lower() in {"input", "textarea"} and (element.get("element_type") or "").lower() != "password":
                    username_selector = element.get("selector", "")
                    if username_selector:
                        break

        if not username_selector or not password_selector:
            return False

        if hasattr(page, "locator"):
            await page.locator(username_selector).first.fill(username, timeout=5000)
            await page.locator(password_selector).first.fill(password, timeout=5000)
        else:
            for selector, value in ((username_selector, username), (password_selector, password)):
                fill_result = await evaluate_script(
                    page,
                    """(selector, value) => {
                      const el = document.querySelector(selector);
                      if (!el) return { success: false, error: "not_found" };
                      el.focus();
                      el.value = value;
                      el.dispatchEvent(new Event("input", { bubbles: true }));
                      el.dispatchEvent(new Event("change", { bubbles: true }));
                      return { success: true };
                    }""",
                    selector,
                    value,
                )
                if not isinstance(fill_result, dict) or not fill_result.get("success"):
                    return False

        submit_selector = ""
        for element in summary.get("interactive_elements", []):
            label = (element.get("label") or "").lower()
            if any(key in label for key in ["登录", "login", "sign in", "提交", "进入"]):
                submit_selector = element.get("selector", "")
                break
        if submit_selector:
            await click_by_selector(browser_session, submit_selector)
        else:
            if hasattr(page, "keyboard"):
                await page.keyboard.press("Enter")
            elif hasattr(page, "press"):
                await page.press("Enter")
            await wait_page_stable(browser_session, delay=1.5)
        return True
    except Exception as exc:
        logger.warning(f"[Exploration] basic login failed: {exc}")
        return False


def _contains_any(text: str, keywords: List[str]) -> bool:
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in keywords if keyword)


async def try_basic_login(browser_session, username: str, password: str) -> Dict[str, Any]:
    if not username or not password:
        return {"success": False, "attempted": False, "detected_login": False, "reason": "missing_credentials"}

    try:
        summary = await extract_dom_summary(browser_session)
        interactive_elements = summary.get("interactive_elements", [])
        page = await get_current_page(browser_session)
        if page is None:
            return {"success": False, "attempted": False, "detected_login": False, "reason": "cannot_get_page"}

        password_keywords = ["password", "passwd", "pwd", "\u5bc6\u7801"]
        username_keywords = [
            "user", "email", "account", "mobile", "phone", "login",
            "\u8d26\u53f7", "\u7528\u6237", "\u7528\u6237\u540d", "\u90ae\u7bb1", "\u624b\u673a",
        ]
        submit_keywords = [
            "login", "sign in", "submit", "enter",
            "\u767b\u5f55", "\u63d0\u4ea4", "\u8fdb\u5165", "\u786e\u8ba4",
        ]

        has_password = False
        for form in summary.get("forms", []):
            for field in form.get("fields", []):
                if (field.get("type") or "").lower() == "password":
                    has_password = True
                    break
            if has_password:
                break
        if not has_password:
            for element in interactive_elements:
                label = " ".join([
                    element.get("label", ""),
                    element.get("placeholder", ""),
                    element.get("aria_label", ""),
                    element.get("name", ""),
                    element.get("title", ""),
                ])
                if (element.get("element_type") or "").lower() == "password" or _contains_any(label, password_keywords):
                    has_password = True
                    break
        if not has_password:
            return {"success": False, "attempted": False, "detected_login": False, "reason": "password_field_not_found"}

        username_selector = ""
        password_selector = ""

        for element in interactive_elements:
            tag = (element.get("tag") or "").lower()
            element_type = (element.get("element_type") or "").lower()
            label = " ".join([
                element.get("label", ""),
                element.get("placeholder", ""),
                element.get("aria_label", ""),
                element.get("name", ""),
                element.get("title", ""),
            ])
            if not username_selector and tag in {"input", "textarea"} and element_type not in {"password", "hidden", "checkbox", "radio"}:
                if _contains_any(label, username_keywords):
                    username_selector = element.get("selector", "")
            if not password_selector and (
                element_type == "password" or _contains_any(label, password_keywords)
            ):
                password_selector = element.get("selector", "")

        if not username_selector:
            for element in interactive_elements:
                tag = (element.get("tag") or "").lower()
                element_type = (element.get("element_type") or "").lower()
                if tag in {"input", "textarea"} and element_type not in {"password", "hidden", "checkbox", "radio"}:
                    username_selector = element.get("selector", "")
                    if username_selector:
                        break

        if not password_selector:
            for element in interactive_elements:
                tag = (element.get("tag") or "").lower()
                if tag not in {"input", "textarea"}:
                    continue
                label = " ".join([
                    element.get("label", ""),
                    element.get("placeholder", ""),
                    element.get("aria_label", ""),
                    element.get("name", ""),
                    element.get("title", ""),
                ])
                if _contains_any(label, password_keywords):
                    password_selector = element.get("selector", "")
                    if password_selector:
                        break

        if not username_selector or not password_selector:
            return {
                "success": False,
                "attempted": True,
                "detected_login": True,
                "reason": "missing_login_selectors",
                "username_selector": username_selector,
                "password_selector": password_selector,
            }

        if hasattr(page, "locator"):
            await page.locator(username_selector).first.fill(username, timeout=5000)
            await page.locator(password_selector).first.fill(password, timeout=5000)
        else:
            for selector, value in ((username_selector, username), (password_selector, password)):
                fill_result = await evaluate_script(
                    page,
                    """(selector, value) => {
                      const el = document.querySelector(selector);
                      if (!el) return { success: false, error: "not_found" };
                      el.focus();
                      el.value = value;
                      el.dispatchEvent(new Event("input", { bubbles: true }));
                      el.dispatchEvent(new Event("change", { bubbles: true }));
                      return { success: true };
                    }""",
                    selector,
                    value,
                )
                if not isinstance(fill_result, dict) or not fill_result.get("success"):
                    return {"success": False, "attempted": True, "detected_login": True, "reason": "fill_failed"}

        submit_selector = ""
        for element in interactive_elements:
            label = " ".join([
                element.get("label", ""),
                element.get("placeholder", ""),
                element.get("aria_label", ""),
                element.get("title", ""),
            ])
            if _contains_any(label, submit_keywords):
                submit_selector = element.get("selector", "")
                break

        if submit_selector:
            click_result = await click_by_selector(browser_session, submit_selector)
            if not click_result.get("success"):
                return {"success": False, "attempted": True, "detected_login": True, "reason": "submit_click_failed"}
        else:
            if hasattr(page, "keyboard"):
                await page.keyboard.press("Enter")
            elif hasattr(page, "press"):
                await page.press("Enter")
            await wait_page_stable(browser_session, delay=1.5)

        return {
            "success": True,
            "attempted": True,
            "detected_login": True,
            "reason": "submitted",
            "username_selector": username_selector,
            "password_selector": password_selector,
            "submit_selector": submit_selector,
        }
    except Exception as exc:
        logger.warning(f"[Exploration] basic login failed: {exc}")
        return {"success": False, "attempted": True, "detected_login": True, "reason": str(exc)}


def build_multimodal_content(text: str, image_base64: str) -> List[Dict[str, Any]]:
    if not image_base64:
        return [{"type": "text", "text": text}]
    return [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
    ]
