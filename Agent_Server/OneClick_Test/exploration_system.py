"""
页面探索系统 - 参考 OpenClaw 的精准执行机制

核心设计理念：
1. 明确的工具定义和约束
2. 强制的验证机制
3. 循环检测和防护
4. 结构化的状态追踪
5. 清晰的任务边界

作者: Kiro AI Assistant
日期: 2025-01-12
"""

from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, field
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


# ============================================
# 1. 探索状态定义（类似 OpenClaw 的 SessionState）
# ============================================

class PageStatus(Enum):
    """页面探索状态"""
    PENDING = "pending"      # 待探索
    EXPLORING = "exploring"  # 探索中
    COMPLETED = "completed"  # 已完成
    SKIPPED = "skipped"      # 已跳过
    FAILED = "failed"        # 失败


@dataclass
class PageRecord:
    """页面记录"""
    page_id: str
    page_name: str
    page_url: str
    status: PageStatus = PageStatus.PENDING
    elements_recorded: int = 0
    min_elements_required: int = 5
    depth: int = 0
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_complete(self) -> bool:
        """检查页面是否完成探索"""
        return self.elements_recorded >= self.min_elements_required
    
    def to_dict(self) -> Dict:
        return {
            "page_id": self.page_id,
            "page_name": self.page_name,
            "page_url": self.page_url,
            "status": self.status.value,
            "elements_recorded": self.elements_recorded,
            "min_elements_required": self.min_elements_required,
            "depth": self.depth,
            "parent_id": self.parent_id,
            "children": self.children,
            "metadata": self.metadata,
        }


@dataclass
class ExplorationState:
    """探索状态（类似 OpenClaw 的 SessionState）"""
    session_id: str
    user_goal: str
    pages: Dict[str, PageRecord] = field(default_factory=dict)
    current_page_id: Optional[str] = None
    exploration_stack: List[str] = field(default_factory=list)
    total_steps: int = 0
    max_steps: int = 50
    
    # 循环检测
    action_history: List[Dict] = field(default_factory=list)
    loop_warnings: int = 0
    max_loop_warnings: int = 3
    
    def add_page(self, page: PageRecord):
        """添加页面"""
        self.pages[page.page_id] = page
    
    def get_page(self, page_id: str) -> Optional[PageRecord]:
        """获取页面"""
        return self.pages.get(page_id)
    
    def get_pending_pages(self) -> List[PageRecord]:
        """获取待探索页面"""
        return [p for p in self.pages.values() if p.status == PageStatus.PENDING]
    
    def get_completed_pages(self) -> List[PageRecord]:
        """获取已完成页面"""
        return [p for p in self.pages.values() if p.status == PageStatus.COMPLETED]
    
    def is_complete(self) -> bool:
        """检查探索是否完成"""
        pending = self.get_pending_pages()
        return len(pending) == 0
    
    def record_action(self, action_type: str, details: Dict):
        """记录动作（用于循环检测）"""
        self.action_history.append({
            "step": self.total_steps,
            "action_type": action_type,
            "details": details,
        })
        self.total_steps += 1
    
    def detect_loop(self) -> Optional[str]:
        """检测循环（类似 OpenClaw 的 detectToolCallLoop）"""
        if len(self.action_history) < 5:
            return None
        
        # 检查最近 5 个动作是否重复
        recent = self.action_history[-5:]
        action_types = [a["action_type"] for a in recent]
        
        # 如果连续 3 次相同动作
        if len(set(action_types[-3:])) == 1:
            self.loop_warnings += 1
            if self.loop_warnings >= self.max_loop_warnings:
                return f"检测到循环：连续 {self.loop_warnings} 次执行相同动作 '{action_types[-1]}'"
        
        return None
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "user_goal": self.user_goal,
            "pages": {k: v.to_dict() for k, v in self.pages.items()},
            "current_page_id": self.current_page_id,
            "exploration_stack": self.exploration_stack,
            "total_steps": self.total_steps,
            "max_steps": self.max_steps,
            "loop_warnings": self.loop_warnings,
        }


# ============================================
# 2. 探索动作定义（类似 OpenClaw 的 Tools）
# ============================================

class ExplorationAction(Enum):
    """探索动作类型"""
    RECORD_PAGE = "record_page"      # 记录页面元素
    NAVIGATE = "navigate"            # 导航到新页面
    GO_BACK = "go_back"              # 返回上一页
    COMPLETE = "complete"            # 完成探索


@dataclass
class ActionResult:
    """动作执行结果"""
    success: bool
    action: ExplorationAction
    message: str
    data: Optional[Dict] = None
    blocked: bool = False
    block_reason: Optional[str] = None


# ============================================
# 3. 动作验证器（类似 OpenClaw 的 before_tool_call）
# ============================================

class ActionValidator:
    """动作验证器 - 在执行前验证动作是否合法"""
    
    @staticmethod
    def validate_record_page(state: ExplorationState, page_id: str) -> ActionResult:
        """验证记录页面动作"""
        page = state.get_page(page_id)
        
        if not page:
            return ActionResult(
                success=False,
                action=ExplorationAction.RECORD_PAGE,
                message=f"页面 {page_id} 不存在",
                blocked=True,
                block_reason="页面不存在"
            )
        
        if page.status == PageStatus.COMPLETED:
            return ActionResult(
                success=False,
                action=ExplorationAction.RECORD_PAGE,
                message=f"页面 {page_id} 已完成探索，不需要重复记录",
                blocked=True,
                block_reason="页面已完成"
            )
        
        return ActionResult(
            success=True,
            action=ExplorationAction.RECORD_PAGE,
            message="验证通过"
        )
    
    @staticmethod
    def validate_navigate(state: ExplorationState, target_page_id: str) -> ActionResult:
        """验证导航动作"""
        current_page = state.get_page(state.current_page_id) if state.current_page_id else None
        
        # 检查当前页面是否已完成探索
        if current_page and not current_page.is_complete():
            return ActionResult(
                success=False,
                action=ExplorationAction.NAVIGATE,
                message=f"当前页面 '{current_page.page_name}' 尚未完成探索（已记录 {current_page.elements_recorded}/{current_page.min_elements_required} 个元素），不能导航到其他页面",
                blocked=True,
                block_reason="当前页面未完成探索"
            )
        
        target_page = state.get_page(target_page_id)
        if not target_page:
            return ActionResult(
                success=False,
                action=ExplorationAction.NAVIGATE,
                message=f"目标页面 {target_page_id} 不存在",
                blocked=True,
                block_reason="目标页面不存在"
            )
        
        return ActionResult(
            success=True,
            action=ExplorationAction.NAVIGATE,
            message="验证通过"
        )
    
    @staticmethod
    def validate_complete(state: ExplorationState) -> ActionResult:
        """验证完成动作"""
        pending = state.get_pending_pages()
        
        if len(pending) > 0:
            pending_names = [p.page_name for p in pending[:5]]
            return ActionResult(
                success=False,
                action=ExplorationAction.COMPLETE,
                message=f"还有 {len(pending)} 个页面未探索：{', '.join(pending_names)}{'...' if len(pending) > 5 else ''}",
                blocked=True,
                block_reason="探索未完成"
            )
        
        # 检查所有页面是否都记录了足够的元素
        incomplete = [p for p in state.pages.values() if not p.is_complete()]
        if len(incomplete) > 0:
            incomplete_info = [
                f"{p.page_name}({p.elements_recorded}/{p.min_elements_required})"
                for p in incomplete[:3]
            ]
            return ActionResult(
                success=False,
                action=ExplorationAction.COMPLETE,
                message=f"有 {len(incomplete)} 个页面元素记录不足：{', '.join(incomplete_info)}",
                blocked=True,
                block_reason="元素记录不足"
            )
        
        return ActionResult(
            success=True,
            action=ExplorationAction.COMPLETE,
            message="所有页面已完成探索"
        )


# ============================================
# 4. 探索执行器
# ============================================

class ExplorationExecutor:
    """探索执行器 - 执行探索动作"""
    
    def __init__(self, state: ExplorationState):
        self.state = state
        self.validator = ActionValidator()
    
    async def execute_action(
        self,
        action: ExplorationAction,
        params: Dict
    ) -> ActionResult:
        """执行动作（带验证）"""
        
        # 1. 循环检测
        loop_message = self.state.detect_loop()
        if loop_message:
            logger.error(f"[ExplorationExecutor] {loop_message}")
            return ActionResult(
                success=False,
                action=action,
                message=loop_message,
                blocked=True,
                block_reason="检测到循环"
            )
        
        # 2. 动作验证
        if action == ExplorationAction.RECORD_PAGE:
            validation = self.validator.validate_record_page(
                self.state,
                params.get("page_id")
            )
        elif action == ExplorationAction.NAVIGATE:
            validation = self.validator.validate_navigate(
                self.state,
                params.get("target_page_id")
            )
        elif action == ExplorationAction.COMPLETE:
            validation = self.validator.validate_complete(self.state)
        else:
            validation = ActionResult(
                success=True,
                action=action,
                message="无需验证"
            )
        
        if validation.blocked:
            logger.warning(f"[ExplorationExecutor] 动作被阻止: {validation.message}")
            return validation
        
        # 3. 记录动作
        self.state.record_action(action.value, params)
        
        # 4. 执行动作
        if action == ExplorationAction.RECORD_PAGE:
            return await self._execute_record_page(params)
        elif action == ExplorationAction.NAVIGATE:
            return await self._execute_navigate(params)
        elif action == ExplorationAction.GO_BACK:
            return await self._execute_go_back(params)
        elif action == ExplorationAction.COMPLETE:
            return await self._execute_complete(params)
        
        return ActionResult(
            success=False,
            action=action,
            message=f"未知动作: {action}"
        )
    
    async def _execute_record_page(self, params: Dict) -> ActionResult:
        """执行记录页面动作"""
        page_id = params.get("page_id")
        elements = params.get("elements", [])
        
        page = self.state.get_page(page_id)
        if not page:
            return ActionResult(
                success=False,
                action=ExplorationAction.RECORD_PAGE,
                message=f"页面 {page_id} 不存在"
            )
        
        page.elements_recorded = len(elements)
        page.status = PageStatus.COMPLETED if page.is_complete() else PageStatus.EXPLORING
        page.metadata["elements"] = elements
        
        logger.info(
            f"[ExplorationExecutor] 记录页面 '{page.page_name}': "
            f"{page.elements_recorded}/{page.min_elements_required} 个元素"
        )
        
        return ActionResult(
            success=True,
            action=ExplorationAction.RECORD_PAGE,
            message=f"已记录 {page.elements_recorded} 个元素",
            data={"page": page.to_dict()}
        )
    
    async def _execute_navigate(self, params: Dict) -> ActionResult:
        """执行导航动作"""
        target_page_id = params.get("target_page_id")
        
        target_page = self.state.get_page(target_page_id)
        if not target_page:
            return ActionResult(
                success=False,
                action=ExplorationAction.NAVIGATE,
                message=f"目标页面 {target_page_id} 不存在"
            )
        
        # 更新状态
        if self.state.current_page_id:
            self.state.exploration_stack.append(self.state.current_page_id)
        
        self.state.current_page_id = target_page_id
        target_page.status = PageStatus.EXPLORING
        
        logger.info(f"[ExplorationExecutor] 导航到页面 '{target_page.page_name}'")
        
        return ActionResult(
            success=True,
            action=ExplorationAction.NAVIGATE,
            message=f"已导航到 '{target_page.page_name}'",
            data={"page": target_page.to_dict()}
        )
    
    async def _execute_go_back(self, params: Dict) -> ActionResult:
        """执行返回动作"""
        if not self.state.exploration_stack:
            return ActionResult(
                success=False,
                action=ExplorationAction.GO_BACK,
                message="已在根页面，无法返回"
            )
        
        previous_page_id = self.state.exploration_stack.pop()
        self.state.current_page_id = previous_page_id
        
        previous_page = self.state.get_page(previous_page_id)
        page_name = previous_page.page_name if previous_page else previous_page_id
        
        logger.info(f"[ExplorationExecutor] 返回到页面 '{page_name}'")
        
        return ActionResult(
            success=True,
            action=ExplorationAction.GO_BACK,
            message=f"已返回到 '{page_name}'"
        )
    
    async def _execute_complete(self, params: Dict) -> ActionResult:
        """执行完成动作"""
        completed = self.state.get_completed_pages()
        
        logger.info(
            f"[ExplorationExecutor] 探索完成: "
            f"共探索 {len(completed)} 个页面，"
            f"总步骤 {self.state.total_steps}"
        )
        
        return ActionResult(
            success=True,
            action=ExplorationAction.COMPLETE,
            message=f"探索完成，共探索 {len(completed)} 个页面",
            data={
                "total_pages": len(completed),
                "total_steps": self.state.total_steps,
                "pages": [p.to_dict() for p in completed]
            }
        )


# ============================================
# 5. 探索系统主类
# ============================================

class ExplorationSystem:
    """探索系统 - 统一管理探索流程"""
    
    def __init__(self, session_id: str, user_goal: str):
        self.state = ExplorationState(
            session_id=session_id,
            user_goal=user_goal
        )
        self.executor = ExplorationExecutor(self.state)
    
    def initialize_pages(self, pages: List[Dict]):
        """初始化页面列表"""
        for page_data in pages:
            page = PageRecord(
                page_id=page_data["page_id"],
                page_name=page_data["page_name"],
                page_url=page_data.get("page_url", ""),
                min_elements_required=page_data.get("min_elements", 5),
                depth=page_data.get("depth", 0),
                parent_id=page_data.get("parent_id"),
            )
            self.state.add_page(page)
    
    async def execute_action(
        self,
        action: ExplorationAction,
        params: Dict
    ) -> ActionResult:
        """执行动作"""
        return await self.executor.execute_action(action, params)
    
    def get_state(self) -> Dict:
        """获取状态"""
        return self.state.to_dict()
    
    def get_next_action_hint(self) -> str:
        """获取下一步动作提示"""
        current_page = self.state.get_page(self.state.current_page_id) if self.state.current_page_id else None
        
        if not current_page:
            pending = self.state.get_pending_pages()
            if pending:
                return f"请导航到待探索页面：{pending[0].page_name}"
            return "请初始化探索"
        
        if not current_page.is_complete():
            return f"请记录当前页面 '{current_page.page_name}' 的元素（至少 {current_page.min_elements_required} 个）"
        
        pending = self.state.get_pending_pages()
        if pending:
            return f"当前页面已完成，请导航到下一个页面：{pending[0].page_name}"
        
        return "所有页面已探索完成，请调用 complete 完成探索"
