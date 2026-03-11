"""
安全测试任务管理器

负责任务的启动、进度更新、停止、超时控制

作者: Ai_Test_Agent Team
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 全局任务注册表: task_id -> asyncio.Task
_running_tasks: Dict[int, asyncio.Task] = {}
# 停止信号: task_id -> asyncio.Event
_stop_events: Dict[int, asyncio.Event] = {}


def register_task(task_id: int, task: asyncio.Task):
    """注册正在运行的任务"""
    _running_tasks[task_id] = task
    _stop_events[task_id] = asyncio.Event()
    logger.info(f"[Security] 注册任务: task_id={task_id}")


def get_stop_event(task_id: int) -> Optional[asyncio.Event]:
    """获取停止信号"""
    return _stop_events.get(task_id)


def should_stop(task_id: int) -> bool:
    """检查任务是否应该停止"""
    event = _stop_events.get(task_id)
    return event.is_set() if event else False


def request_stop(task_id: int) -> bool:
    """请求停止任务"""
    event = _stop_events.get(task_id)
    if event:
        event.set()
        logger.info(f"[Security] 已发送停止信号: task_id={task_id}")
        return True
    
    # 如果没有 event，尝试直接 cancel task
    task = _running_tasks.get(task_id)
    if task and not task.done():
        task.cancel()
        logger.info(f"[Security] 已取消任务: task_id={task_id}")
        return True
    
    return False


def cleanup_task(task_id: int):
    """清理已完成的任务"""
    _running_tasks.pop(task_id, None)
    _stop_events.pop(task_id, None)
    logger.info(f"[Security] 清理任务: task_id={task_id}")


def get_running_tasks() -> Dict[int, asyncio.Task]:
    """获取正在运行的任务列表"""
    return _running_tasks.copy()


def get_task_count() -> int:
    """获取正在运行的任务数量"""
    return len(_running_tasks)
