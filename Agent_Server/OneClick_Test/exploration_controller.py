"""
探索专用 Controller - 基于 browser-use 0.11.1

核心特性：
1. 继承 Tools 类
2. 注册 3 个精准 action：record_page, explore_link, complete_exploration
3. 内置验证逻辑
4. 独立状态管理

作者: Kiro AI Assistant
日期: 2025-01-XX
"""

import logging
import asyncio
from typing import Optional
from pydantic import BaseModel, Field

try:
    from browser_use.tools.service import Tools
    from browser_use.agent.views import ActionResult
    from browser_use.browser import BrowserSession
    from browser_use.tools.views import ClickElementAction
except ImportError as e:
    logging.error(f"无法导入 browser-use: {e}")
    raise

logger = logging.getLogger(__name__)


class ExplorationController(Tools):
    """探索专用 Controller（继承 Tools）"""
    
    def __init__(self, exploration_state):
        """初始化探索 Controller"""
        # 排除不需要的默认 actions
        super().__init__(
            exclude_actions=['search', 'extract', 'upload_file', 'screenshot']
        )
        
        self.exploration_state = exploration_state
        self._register_exploration_actions()
        
        logger.info("✅ ExplorationController 初始化完成")
    
    def _register_exploration_actions(self):
        """注册探索专用 actions"""
        
        # Action 1: record_page（移除元素数量限制）
        class RecordPageParams(BaseModel):
            page_id: str = Field(description="页面标识")
            elements: list[dict] = Field(description="页面元素列表（记录所有可点击元素，越多越好）")
        
        @self.registry.action(
            description='记录当前页面的所有元素（必须在导航前调用，记录所有可点击元素）',
            param_model=RecordPageParams
        )
        async def record_page(
            params: RecordPageParams,
            browser_session: BrowserSession
        ) -> ActionResult:
            """记录当前页面元素"""
            logger.info(f"🔍 record_page: page_id={params.page_id}, elements={len(params.elements)}")
            
            # 获取当前 URL
            try:
                current_url = await browser_session.get_current_page_url()
            except Exception as e:
                logger.warning(f"⚠️ 获取 URL 失败: {e}")
                current_url = ""
            
            # 更新状态
            result = self.exploration_state.record_page(
                page_id=params.page_id,
                elements=params.elements,
                url=current_url
            )
            
            if not result['success']:
                return ActionResult(error=result['message'], include_in_memory=True)
            
            msg = f"✅ 已记录页面 '{params.page_id}'，共 {len(params.elements)} 个元素"
            logger.info(msg)
            return ActionResult(extracted_content=msg, include_in_memory=True)
        
        # Action 2: explore_link（增强：自动等待+返回提示）
        class ExploreLinkParams(BaseModel):
            element_index: int = Field(description="要点击的元素索引")
            target_page_name: str = Field(description="目标页面名称")
        
        @self.registry.action(
            description='点击链接探索新页面（必须先调用 record_page，探索完子页面后必须 go_back）',
            param_model=ExploreLinkParams
        )
        async def explore_link(
            params: ExploreLinkParams,
            browser_session: BrowserSession
        ) -> ActionResult:
            """探索链接"""
            logger.info(f"🔗 explore_link: index={params.element_index}, target={params.target_page_name}")
            
            # 验证：当前页面是否已记录
            validation = self.exploration_state.validate_navigate()
            if not validation['success']:
                logger.warning(f"❌ {validation['message']}")
                return ActionResult(error=validation['message'], include_in_memory=True)
            
            # 验证：是否重复探索
            if self.exploration_state.is_link_explored(params.element_index):
                error_msg = f"元素 {params.element_index} 已探索过"
                logger.warning(f"❌ {error_msg}")
                return ActionResult(error=error_msg, include_in_memory=True)
            
            # 执行点击
            try:
                click_action = self.registry.registry.actions.get('click')
                if not click_action:
                    return ActionResult(error="click action 不可用")
                
                click_params = ClickElementAction(index=params.element_index)
                click_result = await click_action.function(
                    params=click_params,
                    browser_session=browser_session
                )
                
                if isinstance(click_result, ActionResult) and click_result.error:
                    logger.error(f"❌ 点击失败: {click_result.error}")
                    return click_result
                
            except Exception as e:
                error_msg = f"点击失败: {str(e)}"
                logger.error(f"❌ {error_msg}")
                return ActionResult(error=error_msg, include_in_memory=True)
            
            # 等待页面加载
            await asyncio.sleep(3)
            
            # 更新状态（进入子页面）
            self.exploration_state.mark_link_explored(
                element_index=params.element_index,
                target_page_name=params.target_page_name
            )
            
            msg = f"✅ 已进入 '{params.target_page_name}'，请记录该页面后继续探索（探索完毕后调用 go_back）"
            logger.info(msg)
            return ActionResult(extracted_content=msg, include_in_memory=True)
        
        # Action 3: mark_page_completed（新增：标记页面探索完成）
        @self.registry.action(
            description='标记当前页面探索完成（所有子元素都已探索后调用，然后 go_back 返回上一页）',
        )
        async def mark_page_completed() -> ActionResult:
            """标记页面探索完成"""
            logger.info("✅ mark_page_completed 被调用")
            
            self.exploration_state.mark_page_completed()
            
            msg = "✅ 当前页面探索完成，请调用 go_back 返回上一页继续探索"
            logger.info(msg)
            return ActionResult(extracted_content=msg, include_in_memory=True)
        
        # Action 4: refresh_page（新增：刷新页面）
        @self.registry.action(
            description='刷新当前页面（页面显示异常或加载失败时使用）',
        )
        async def refresh_page(browser_session: BrowserSession) -> ActionResult:
            """刷新页面"""
            logger.info("🔄 refresh_page 被调用")
            
            try:
                # 获取当前 URL
                current_url = await browser_session.get_current_page_url()
                
                # 重新导航到当前 URL（相当于刷新）
                from browser_use.browser.views import BrowserState
                page = browser_session.context.pages[0] if browser_session.context.pages else None
                if page:
                    await page.reload()
                    await asyncio.sleep(3)  # 等待页面加载
                    
                    msg = f"✅ 页面已刷新: {current_url}"
                    logger.info(msg)
                    return ActionResult(extracted_content=msg, include_in_memory=True)
                else:
                    return ActionResult(error="无法获取页面对象", include_in_memory=True)
                    
            except Exception as e:
                error_msg = f"刷新页面失败: {str(e)}"
                logger.error(f"❌ {error_msg}")
                return ActionResult(error=error_msg, include_in_memory=True)
        
        # Action 5: complete_exploration（修改：移除硬性数量限制）
        @self.registry.action(
            description='完成探索（所有页面都探索完毕后调用，会验证探索深度和完整性）',
        )
        async def complete_exploration() -> ActionResult:
            """完成探索"""
            logger.info("🏁 complete_exploration 被调用")
            
            # 验证完成条件
            validation = self.exploration_state.validate_completion()
            if not validation['success']:
                error_msg = f"探索未完成: {validation['message']}"
                logger.warning(f"❌ {error_msg}")
                return ActionResult(error=error_msg, include_in_memory=True)
            
            # 生成探索报告
            report = self.exploration_state.generate_report()
            logger.info("✅ 探索完成")
            return ActionResult(extracted_content=report, include_in_memory=True)
        
        logger.info("✅ 探索 actions 注册完成")
