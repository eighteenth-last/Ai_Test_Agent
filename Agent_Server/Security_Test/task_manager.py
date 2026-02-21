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


def update_task_progress(db, task_id: int, progress: int, status: str = None):
    """更新任务进度"""
    from database.connection import SecurityScanTask
    task = db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
    if task:
        task.progress = min(progress, 100)
        if status:
            task.status = status
        task.updated_at = datetime.now()
        db.commit()


def finish_task(db, task_id: int, status: str, risk_score: int = None,
                risk_level: str = None, vuln_summary: dict = None,
                vulnerabilities: str = None, report_content: str = None,
                error_message: str = None):
    """完成任务（成功或失败）"""
    from database.connection import SecurityScanTask
    task = db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
    if task:
        task.status = status
        task.progress = 100 if status == 'finished' else task.progress
        task.end_time = datetime.now()
        if task.start_time:
            task.duration = int((task.end_time - task.start_time).total_seconds())
        if risk_score is not None:
            task.risk_score = risk_score
        if risk_level:
            task.risk_level = risk_level
        if vuln_summary:
            task.vuln_summary = vuln_summary
        if vulnerabilities:
            task.vulnerabilities = vulnerabilities
        if report_content:
            task.report_content = report_content
        if error_message:
            task.error_message = error_message
        db.commit()
    cleanup_task(task_id)
