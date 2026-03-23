import asyncio
import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

try:
    from browser_use.agent.views import ActionResult
    from browser_use.tools.service import Tools
    from browser_use.tools.views import ClickElementAction
    try:
        from browser_use import BrowserSession
    except ImportError:
        from browser_use.browser import BrowserSession
except ImportError as exc:
    logging.error("failed to import browser-use: %s", exc)
    raise

logger = logging.getLogger(__name__)


class ExplorationController(Tools):
    def __init__(self, exploration_state):
        super().__init__(exclude_actions=["search", "extract", "upload_file", "screenshot"])
        self.exploration_state = exploration_state
        self._register_exploration_actions()
        logger.info("[ExplorationController] initialized")

    def _register_exploration_actions(self):
        class RecordPageParams(BaseModel):
            page_id: str = Field(description="Stable page identifier")
            elements: List[Dict[str, Any]] = Field(description="Interactive elements detected on the page")

        @self.registry.action(
            description="Record the current page before navigating away from it.",
            param_model=RecordPageParams,
        )
        async def record_page(params: RecordPageParams, browser_session: BrowserSession) -> ActionResult:
            logger.info(
                "[ExplorationController] record_page page_id=%s elements=%s",
                params.page_id,
                len(params.elements),
            )

            current_url = ""
            try:
                current_url = await browser_session.get_current_page_url()
            except Exception as exc:
                logger.warning("[ExplorationController] failed to read current url: %s", exc)

            dom_mode_hint = ""
            dom_summary: Dict[str, Any] = {}

            try:
                from Execute_test.dom_mode.detector import DomRichnessDetector

                detect_result = await DomRichnessDetector.detect(browser_session)
                mode = detect_result.get("mode", "vision")
                interactive = detect_result.get("interactive", 0)
                total = detect_result.get("total", 0)
                dom_mode_hint = f" DOM detect: interactive={interactive}, total={total}, mode={mode}"
            except Exception as exc:
                logger.debug("[ExplorationController] DOM richness detection skipped: %s", exc)

            try:
                from Exploration.browser_use_tools import extract_dom_summary

                dom_summary = await extract_dom_summary(browser_session)
            except Exception as exc:
                logger.warning("[ExplorationController] failed to extract DOM summary: %s", exc)

            result = self.exploration_state.record_page(
                page_id=params.page_id,
                elements=params.elements,
                url=current_url,
                dom_summary=dom_summary,
            )
            if not result["success"]:
                return ActionResult(error=result["message"], include_in_memory=True)

            title = str(dom_summary.get("title") or params.page_id)
            msg = (
                f"Recorded page '{params.page_id}' ({title}) with "
                f"{len(dom_summary.get('interactive_elements') or params.elements)} interactive elements."
                f"{dom_mode_hint}"
            )
            return ActionResult(extracted_content=msg, include_in_memory=True)

        class ExploreLinkParams(BaseModel):
            element_index: int = Field(description="Interactive element index to click")
            target_page_name: str = Field(description="Expected target page name")

        @self.registry.action(
            description="Click a link or button to explore a child page, then continue exploration there.",
            param_model=ExploreLinkParams,
        )
        async def explore_link(params: ExploreLinkParams, browser_session: BrowserSession) -> ActionResult:
            logger.info(
                "[ExplorationController] explore_link index=%s target=%s",
                params.element_index,
                params.target_page_name,
            )

            validation = self.exploration_state.validate_navigate()
            if not validation["success"]:
                return ActionResult(error=validation["message"], include_in_memory=True)

            if self.exploration_state.is_link_explored(params.element_index):
                return ActionResult(
                    error=f"element {params.element_index} has already been explored",
                    include_in_memory=True,
                )

            try:
                click_action = self.registry.registry.actions.get("click")
                if not click_action:
                    return ActionResult(error="click action is unavailable", include_in_memory=True)

                click_params = ClickElementAction(index=params.element_index)
                click_result = await click_action.function(
                    params=click_params,
                    browser_session=browser_session,
                )
                if isinstance(click_result, ActionResult) and click_result.error:
                    return click_result
            except Exception as exc:
                return ActionResult(error=f"click failed: {exc}", include_in_memory=True)

            await asyncio.sleep(3)
            self.exploration_state.mark_link_explored(
                element_index=params.element_index,
                target_page_name=params.target_page_name,
            )
            msg = (
                f"Entered '{params.target_page_name}'. Record the new page, explore it deeply, "
                "then use go_back() after it is complete."
            )
            return ActionResult(extracted_content=msg, include_in_memory=True)

        @self.registry.action(
            description="Mark the current page as fully explored before going back.",
        )
        async def mark_page_completed() -> ActionResult:
            self.exploration_state.mark_page_completed()
            return ActionResult(
                extracted_content="Current page is complete. Use go_back() to return to the parent page.",
                include_in_memory=True,
            )

        @self.registry.action(
            description="Refresh the current page when the UI is stuck or did not finish loading.",
        )
        async def refresh_page(browser_session: BrowserSession) -> ActionResult:
            try:
                page = browser_session.context.pages[0] if browser_session.context and browser_session.context.pages else None
                if not page:
                    return ActionResult(error="current page is unavailable", include_in_memory=True)
                await page.reload()
                await asyncio.sleep(3)
                current_url = await browser_session.get_current_page_url()
                return ActionResult(
                    extracted_content=f"Refreshed page: {current_url}",
                    include_in_memory=True,
                )
            except Exception as exc:
                return ActionResult(error=f"refresh failed: {exc}", include_in_memory=True)

        @self.registry.action(
            description="Complete exploration after all reachable pages and branches have been explored.",
        )
        async def complete_exploration() -> ActionResult:
            validation = self.exploration_state.validate_completion()
            if not validation["success"]:
                return ActionResult(
                    error=f"exploration is not complete: {validation['message']}",
                    include_in_memory=True,
                )

            report = self.exploration_state.generate_report()
            return ActionResult(extracted_content=report, include_in_memory=True)

        logger.info("[ExplorationController] actions registered")
