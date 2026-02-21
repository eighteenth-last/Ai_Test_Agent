"""
安全测试 API 路由

提供安全扫描的启动、停止、状态查询、历史记录等接口

作者: Ai_Test_Agent Team
"""
import asyncio
import json
import logging
from typing import Optional, Dict, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db, SecurityScanTask

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/security",
    tags=["安全测试"]
)


# ============================================
# 请求模型
# ============================================

class RunScanRequest(BaseModel):
    type: str  # web_scan / api_attack / dependency_scan / baseline_check
    target: str
    config: Optional[Dict] = {}


class StopScanRequest(BaseModel):
    task_id: int


# ============================================
# API 端点
# ============================================

@router.post("/run")
async def run_security_scan(
    request: RunScanRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    启动安全扫描任务

    支持 4 种类型: web_scan / api_attack / dependency_scan / baseline_check
    任务异步执行，立即返回 task_id
    """
    valid_types = ["web_scan", "api_attack", "dependency_scan", "baseline_check"]
    if request.type not in valid_types:
        raise HTTPException(status_code=400, detail=f"无效的扫描类型，支持: {valid_types}")

    if not request.target:
        raise HTTPException(status_code=400, detail="扫描目标不能为空")

    # 安全校验: web_scan 和 baseline_check 需要验证目标白名单
    if request.type in ("web_scan", "baseline_check"):
        from Security_Test.service import _validate_target
        if not _validate_target(request.target):
            raise HTTPException(
                status_code=403,
                detail="安全限制: 仅允许扫描内网地址 (localhost / 10.x / 172.16-31.x / 192.168.x)"
            )

    # 创建任务
    from Security_Test.service import SecurityTestService
    task = SecurityTestService.create_task(
        scan_type=request.type,
        target=request.target,
        config=request.config or {},
        db=db,
    )

    # 异步执行
    async def _run():
        await SecurityTestService.run_scan(
            task_id=task.id,
            scan_type=request.type,
            target=request.target,
            config=request.config or {},
        )

    loop = asyncio.get_event_loop()
    async_task = loop.create_task(_run())

    from Security_Test.task_manager import register_task
    register_task(task.id, async_task)

    return {
        "success": True,
        "data": {
            "task_id": task.id,
            "type": request.type,
            "target": request.target,
            "status": "pending",
        },
        "message": "扫描任务已创建，正在后台执行",
    }


@router.post("/stop")
async def stop_security_scan(
    request: StopScanRequest,
    db: Session = Depends(get_db)
):
    """停止正在运行的扫描任务"""
    task = db.query(SecurityScanTask).filter(SecurityScanTask.id == request.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status not in ("pending", "running"):
        return {"success": False, "message": f"任务已处于 {task.status} 状态，无法停止"}

    from Security_Test.task_manager import request_stop
    request_stop(request.task_id)

    task.status = "stopped"
    db.commit()

    return {"success": True, "message": "已发送停止信号"}


@router.get("/status/{task_id}")
async def get_scan_status(task_id: int, db: Session = Depends(get_db)):
    """获取扫描任务状态"""
    task = db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "success": True,
        "data": {
            "task_id": task.id,
            "type": task.scan_type,
            "target": task.target,
            "status": task.status,
            "progress": task.progress,
            "risk_score": task.risk_score,
            "risk_level": task.risk_level,
            "vuln_summary": task.vuln_summary,
            "duration": task.duration,
            "error_message": task.error_message,
            "start_time": task.start_time.isoformat() if task.start_time else None,
            "end_time": task.end_time.isoformat() if task.end_time else None,
        },
    }


@router.get("/result/{task_id}")
async def get_scan_result(task_id: int, db: Session = Depends(get_db)):
    """获取扫描结果详情（含漏洞列表和报告）"""
    task = db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    vulnerabilities = []
    if task.vulnerabilities:
        try:
            vulnerabilities = json.loads(task.vulnerabilities) if isinstance(task.vulnerabilities, str) else task.vulnerabilities
        except Exception:
            pass

    return {
        "success": True,
        "data": {
            "task_id": task.id,
            "type": task.scan_type,
            "target": task.target,
            "status": task.status,
            "risk_score": task.risk_score,
            "risk_level": task.risk_level,
            "vuln_summary": task.vuln_summary,
            "vulnerabilities": vulnerabilities,
            "report_content": task.report_content,
            "duration": task.duration,
        },
    }


@router.get("/history")
async def get_scan_history(
    page: int = 1,
    page_size: int = 20,
    scan_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取扫描历史记录"""
    query = db.query(SecurityScanTask)
    if scan_type:
        query = query.filter(SecurityScanTask.scan_type == scan_type)

    total = query.count()
    tasks = query.order_by(SecurityScanTask.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "task_id": t.id,
                    "type": t.scan_type,
                    "target": t.target,
                    "status": t.status,
                    "progress": t.progress,
                    "risk_score": t.risk_score,
                    "risk_level": t.risk_level,
                    "vuln_summary": t.vuln_summary,
                    "duration": t.duration,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tasks
            ],
        },
    }


@router.delete("/{task_id}")
async def delete_scan_task(task_id: int, db: Session = Depends(get_db)):
    """删除扫描任务记录"""
    task = db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status == "running":
        raise HTTPException(status_code=400, detail="任务正在运行中，请先停止")

    db.delete(task)
    db.commit()
    return {"success": True, "message": "已删除"}


# ============================================
# 安全测试用例任务列表
# ============================================

@router.get("/cases")
async def get_security_cases(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取安全测试用例任务列表

    筛选 case_type='安全测试' 的用例，支持按 security_status 过滤
    """
    from database.connection import ExecutionCase

    query = db.query(ExecutionCase).filter(ExecutionCase.case_type == '安全测试')

    if status and status != 'all':
        query = query.filter(ExecutionCase.security_status == status)

    if search:
        query = query.filter(
            ExecutionCase.title.like(f"%{search}%") |
            ExecutionCase.module.like(f"%{search}%")
        )

    total = query.count()
    cases = query.order_by(ExecutionCase.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    items = []
    for c in cases:
        steps = c.steps
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except Exception:
                steps = [steps]

        items.append({
            "id": c.id,
            "title": c.title,
            "module": c.module,
            "steps": steps,
            "expected": c.expected,
            "priority": c.priority,
            "case_type": c.case_type,
            "keywords": c.keywords,
            "security_status": c.security_status or '待测试',
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    # 统计各状态数量
    all_count = db.query(ExecutionCase).filter(ExecutionCase.case_type == '安全测试').count()
    pending_count = db.query(ExecutionCase).filter(
        ExecutionCase.case_type == '安全测试',
        (ExecutionCase.security_status == '待测试') | (ExecutionCase.security_status.is_(None))
    ).count()
    pass_count = db.query(ExecutionCase).filter(
        ExecutionCase.case_type == '安全测试', ExecutionCase.security_status == '通过'
    ).count()
    bug_count = db.query(ExecutionCase).filter(
        ExecutionCase.case_type == '安全测试', ExecutionCase.security_status == 'bug'
    ).count()

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
            "stats": {
                "all": all_count,
                "pending": pending_count,
                "pass": pass_count,
                "bug": bug_count,
            },
        },
    }


class UpdateSecurityStatusRequest(BaseModel):
    status: str  # 待测试 / 通过 / bug


@router.put("/cases/{case_id}/status")
async def update_security_case_status(
    case_id: int,
    request: UpdateSecurityStatusRequest,
    db: Session = Depends(get_db)
):
    """更新安全测试用例的状态"""
    from database.connection import ExecutionCase

    valid_statuses = ['待测试', '通过', 'bug']
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效状态，支持: {valid_statuses}")

    case = db.query(ExecutionCase).filter(ExecutionCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    case.security_status = request.status
    db.commit()

    return {"success": True, "message": f"已更新为 {request.status}"}
