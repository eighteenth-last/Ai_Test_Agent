"""
探索状态管理 - 独立于 LLM memory

核心特性：
1. 独立的 Python 对象管理状态
2. 不依赖 LLM 的 memory
3. 支持状态持久化
4. 提供验证方法

作者: Kiro AI Assistant
日期: 2025-01-XX
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


@dataclass
class PageInfo:
    """页面信息"""
    page_id: str
    url: str
    elements: List[dict] = field(default_factory=list)
    is_recorded: bool = False
    explored_links: set[int] = field(default_factory=set)


class ExplorationState:
    """探索状态管理（独立于 LLM memory）- 支持深度优先探索"""
    
    def __init__(self):
        self.pages: Dict[str, PageInfo] = {}
        self.current_page_id: Optional[str] = None
        self.navigation_history: List[str] = []
        self.total_links_explored: int = 0
        self.exploration_stack: List[str] = []  # DFS 栈：记录探索路径
        self.max_depth: int = 0  # 记录最大探索深度
        logger.info("✅ ExplorationState 初始化完成（深度优先模式）")
    
    def record_page(self, page_id: str, elements: List[dict], url: str) -> dict:
        """记录页面（不限制元素数量）"""
        if page_id not in self.pages:
            self.pages[page_id] = PageInfo(page_id=page_id, url=url)
        
        page = self.pages[page_id]
        page.elements = elements
        page.is_recorded = True
        self.current_page_id = page_id
        
        # 更新探索深度
        current_depth = len(self.exploration_stack)
        if current_depth > self.max_depth:
            self.max_depth = current_depth
        
        logger.info(f"✅ 记录页面 '{page_id}': {len(elements)} 个元素（深度: {current_depth}）")
        return {'success': True, 'message': f'已记录 {len(elements)} 个元素'}
    
    def validate_navigate(self) -> dict:
        """验证是否可以导航"""
        if not self.current_page_id:
            return {'success': False, 'message': '当前页面未设置'}
        
        current_page = self.pages.get(self.current_page_id)
        if not current_page or not current_page.is_recorded:
            return {'success': False, 'message': '当前页面未记录，请先调用 record_page'}
        
        return {'success': True}
    
    def is_link_explored(self, element_index: int) -> bool:
        """检查链接是否已探索"""
        if not self.current_page_id:
            return False
        
        current_page = self.pages.get(self.current_page_id)
        if not current_page:
            return False
        
        return element_index in current_page.explored_links
    
    def mark_link_explored(self, element_index: int, target_page_name: str):
        """标记链接已探索（进入子页面）"""
        if self.current_page_id:
            current_page = self.pages.get(self.current_page_id)
            if current_page:
                current_page.explored_links.add(element_index)
        
        # 压入 DFS 栈
        self.exploration_stack.append(target_page_name)
        self.navigation_history.append(target_page_name)
        self.total_links_explored += 1
        
        depth = len(self.exploration_stack)
        logger.info(f"✅ 探索链接: {target_page_name} (总计: {self.total_links_explored}, 深度: {depth})")
    
    def mark_page_completed(self):
        """标记当前页面探索完成（返回上一页）"""
        if self.exploration_stack:
            completed_page = self.exploration_stack.pop()
            logger.info(f"✅ 页面探索完成: {completed_page}（返回上一层，当前深度: {len(self.exploration_stack)}）")
    
    def validate_completion(self) -> dict:
        """验证是否可以完成（移除硬性数量限制）"""
        # 检查是否还有未探索的页面
        if self.exploration_stack:
            return {
                'success': False,
                'message': f'还有 {len(self.exploration_stack)} 个页面未完成探索，请先返回'
            }
        
        # 检查探索深度
        if self.max_depth < 2:
            return {
                'success': False,
                'message': f'探索深度不足（当前: {self.max_depth}，建议: ≥3）'
            }
        
        # 检查最少探索数量（降低要求）
        if len(self.pages) < 3:
            return {
                'success': False,
                'message': f'探索页面数不足（当前: {len(self.pages)}，最少: 3）'
            }
        
        if self.total_links_explored < 5:
            return {
                'success': False,
                'message': f'探索链接数不足（当前: {self.total_links_explored}，最少: 5）'
            }
        
        return {'success': True}
    
    def generate_report(self) -> str:
        """生成探索报告"""
        report_lines = [
            "## 探索完成报告（深度优先）",
            f"- 探索页面数: {len(self.pages)}",
            f"- 探索链接数: {self.total_links_explored}",
            f"- 最大探索深度: {self.max_depth}",
            "",
            "### 页面列表",
        ]
        
        for page_id, page in self.pages.items():
            report_lines.append(
                f"- {page_id}: {len(page.elements)} 个元素, "
                f"{len(page.explored_links)} 个链接已探索"
            )
        
        return "\n".join(report_lines)
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            'total_pages': len(self.pages),
            'total_links_explored': self.total_links_explored,
            'current_page': self.current_page_id,
            'recorded_pages': sum(1 for p in self.pages.values() if p.is_recorded),
            'max_depth': self.max_depth,
            'current_depth': len(self.exploration_stack),
        }
