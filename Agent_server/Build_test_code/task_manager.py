"""
测试任务管理器 - 支持暂停和停止功能

管理正在执行的测试任务，提供暂停、恢复、停止等控制功能
"""

import asyncio
from typing import Dict, Optional
from datetime import datetime


class TaskManager:
    """测试任务管理器"""
    
    def __init__(self):
        self._tasks: Dict[int, dict] = {}  # task_id -> task_info
        self._pause_events: Dict[int, asyncio.Event] = {}  # task_id -> pause_event
        self._stop_flags: Dict[int, bool] = {}  # task_id -> stop_flag
    
    def create_task(self, task_id: int, test_case_id: int) -> None:
        """创建新任务"""
        self._tasks[task_id] = {
            'test_case_id': test_case_id,
            'status': 'running',
            'created_at': datetime.now(),
            'paused': False,
            'stopped': False
        }
        self._pause_events[task_id] = asyncio.Event()
        self._pause_events[task_id].set()  # 初始为运行状态
        self._stop_flags[task_id] = False
    
    def pause_task(self, task_id: int) -> bool:
        """暂停任务"""
        if task_id not in self._tasks:
            return False
        
        self._tasks[task_id]['status'] = 'paused'
        self._tasks[task_id]['paused'] = True
        self._pause_events[task_id].clear()  # 清除事件，阻塞任务
        return True
    
    def resume_task(self, task_id: int) -> bool:
        """恢复任务"""
        if task_id not in self._tasks:
            return False
        
        self._tasks[task_id]['status'] = 'running'
        self._tasks[task_id]['paused'] = False
        self._pause_events[task_id].set()  # 设置事件，恢复任务
        return True
    
    def stop_task(self, task_id: int) -> bool:
        """停止任务"""
        if task_id not in self._tasks:
            return False
        
        self._tasks[task_id]['status'] = 'stopped'
        self._tasks[task_id]['stopped'] = True
        self._stop_flags[task_id] = True
        self._pause_events[task_id].set()  # 确保任务不被阻塞
        return True
    
    def complete_task(self, task_id: int) -> None:
        """任务完成"""
        if task_id in self._tasks:
            self._tasks[task_id]['status'] = 'completed'
    
    def remove_task(self, task_id: int) -> None:
        """移除任务"""
        self._tasks.pop(task_id, None)
        self._pause_events.pop(task_id, None)
        self._stop_flags.pop(task_id, None)
    
    async def check_pause(self, task_id: int) -> None:
        """检查是否需要暂停（在任务执行过程中调用）"""
        if task_id in self._pause_events:
            await self._pause_events[task_id].wait()
    
    def should_stop(self, task_id: int) -> bool:
        """检查是否应该停止"""
        return self._stop_flags.get(task_id, False)
    
    def get_task_status(self, task_id: int) -> Optional[dict]:
        """获取任务状态"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[int, dict]:
        """获取所有任务"""
        return self._tasks.copy()


# 全局任务管理器实例
_task_manager = TaskManager()


def get_task_manager() -> TaskManager:
    """获取任务管理器实例"""
    return _task_manager
