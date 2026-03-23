from __future__ import annotations

from typing import Any, Dict

from .browser_use_tools import click_by_coordinates, click_by_selector


async def execute_click(browser_session, locator: Dict[str, Any]) -> Dict[str, Any]:
    locator_type = locator.get("type")
    if locator_type == "selector":
        return await click_by_selector(browser_session, locator.get("value", ""))
    if locator_type == "point":
        return await click_by_coordinates(browser_session, locator.get("x", 0), locator.get("y", 0))
    return {"success": False, "error": f"unsupported_locator:{locator_type}"}
