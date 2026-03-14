"""
安全测试平台 API 路由

基于新架构设计的安全测试平台API，提供：
1. 资产管理 - 目标CRUD
2. 扫描任务 - 任务管理
3. 扫描结果 - 结果查询
4. 漏洞管理 - 漏洞跟踪
5. 仪表板 - 统计信息

作者: 程序员Eighteen
"""
import asyncio
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db
from Security_Test.service import SecurityPlatformService
from Security_Test.models import (
    SecurityTargetCreate, SecurityTargetUpdate, ScanTaskCreate,
    ScanTaskResponse, VulnerabilityResponse, ScanResultResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/security",
    tags=["安全测试平台"]
)

# ============================================
# 请求响应模型
# ============================================

class TargetResponse(BaseModel):
    """目标响应模型"""
    id: int
    name: str
    base_url: str
    description: Optional[str] = None
    target_type: str
    environment: str
    is_active: int
    created_at: str
    updated_at: str


class UpdateVulnStatusRequest(BaseModel):
    """更新漏洞状态请求"""
    status: str  # open/fixed/false_positive/accepted


# ============================================
# 资产管理 API
# ============================================

@router.post("/targets")
def create_target(
    target_data: SecurityTargetCreate,
    db: Session = Depends(get_db)
):
    """创建安全目标"""
    try:
        target = SecurityPlatformService.create_target(target_data, db)
        target_response = TargetResponse(
            id=target.id,
            name=target.name,
            base_url=target.base_url,
            description=target.description,
            target_type=target.target_type,
            environment=target.environment,
            is_active=target.is_active,
            created_at=target.created_at.isoformat(),
            updated_at=target.updated_at.isoformat()
        )
        
        return {
            "success": True,
            "data": target_response,
            "message": "目标创建成功"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/targets")
def get_targets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """获取目标列表"""
    targets = SecurityPlatformService.get_targets(db, skip, limit)
    target_list = [
        TargetResponse(
            id=target.id,
            name=target.name,
            base_url=target.base_url,
            description=target.description,
            target_type=target.target_type,
            environment=target.environment,
            is_active=target.is_active,
            created_at=target.created_at.isoformat(),
            updated_at=target.updated_at.isoformat()
        )
        for target in targets
    ]
    
    return {
        "success": True,
        "data": target_list,
        "message": "获取目标列表成功"
    }


@router.get("/targets/{target_id}")
def get_target(target_id: int, db: Session = Depends(get_db)):
    """获取单个目标"""
    target = SecurityPlatformService.get_target(target_id, db)
    if not target:
        raise HTTPException(status_code=404, detail="目标不存在")
    
    target_data = TargetResponse(
        id=target.id,
        name=target.name,
        base_url=target.base_url,
        description=target.description,
        target_type=target.target_type,
        environment=target.environment,
        is_active=target.is_active,
        created_at=target.created_at.isoformat(),
        updated_at=target.updated_at.isoformat()
    )
    
    return {
        "success": True,
        "data": target_data,
        "message": "获取目标详情成功"
    }


@router.put("/targets/{target_id}")
def update_target(
    target_id: int,
    target_data: SecurityTargetUpdate,
    db: Session = Depends(get_db)
):
    """更新目标"""
    target = SecurityPlatformService.update_target(target_id, target_data, db)
    if not target:
        raise HTTPException(status_code=404, detail="目标不存在")
    
    target_response = TargetResponse(
        id=target.id,
        name=target.name,
        base_url=target.base_url,
        description=target.description,
        target_type=target.target_type,
        environment=target.environment,
        is_active=target.is_active,
        created_at=target.created_at.isoformat(),
        updated_at=target.updated_at.isoformat()
    )
    
    return {
        "success": True,
        "data": target_response,
        "message": "目标更新成功"
    }


@router.delete("/targets/{target_id}")
def delete_target(target_id: int, db: Session = Depends(get_db)):
    """删除目标"""
    success = SecurityPlatformService.delete_target(target_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="目标不存在")
    
    return {"success": True, "message": "目标已删除"}


# ============================================
# 扫描任务 API
# ============================================

@router.post("/scan")
async def create_scan_task(
    task_data: ScanTaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """创建并启动扫描任务"""
    try:
        # 创建任务
        task = SecurityPlatformService.create_scan_task(task_data, db)
        
        # 异步执行扫描
        background_tasks.add_task(
            SecurityPlatformService.execute_scan_task,
            task.id
        )
        
        task_response = ScanTaskResponse(
            id=task.id,
            target_id=task.target_id,
            scan_type=task.scan_type,
            status=task.status,
            progress=task.progress,
            created_at=task.created_at
        )
        
        return {
            "success": True,
            "data": task_response,
            "message": "扫描任务创建成功"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建扫描任务失败: {e}")
        raise HTTPException(status_code=500, detail="创建任务失败")


@router.get("/tasks")
def get_scan_tasks(
    target_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """获取扫描任务列表"""
    tasks = SecurityPlatformService.get_scan_tasks(db, target_id, skip, limit)
    task_list = [
        ScanTaskResponse(
            id=task.id,
            target_id=task.target_id,
            scan_type=task.scan_type,
            status=task.status,
            progress=task.progress,
            start_time=task.start_time,
            end_time=task.end_time,
            duration=task.duration,
            error_message=task.error_message,
            created_at=task.created_at
        )
        for task in tasks
    ]
    
    return {
        "success": True,
        "data": task_list,
        "message": "获取任务列表成功"
    }


@router.get("/tasks/{task_id}")
def get_scan_task(task_id: int, db: Session = Depends(get_db)):
    """获取单个扫描任务"""
    task = SecurityPlatformService.get_scan_task(task_id, db)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task_data = ScanTaskResponse(
        id=task.id,
        target_id=task.target_id,
        scan_type=task.scan_type,
        status=task.status,
        progress=task.progress,
        start_time=task.start_time,
        end_time=task.end_time,
        duration=task.duration,
        error_message=task.error_message,
        created_at=task.created_at
    )
    
    return {
        "success": True,
        "data": task_data,
        "message": "获取任务详情成功"
    }


@router.post("/tasks/{task_id}/stop")
def stop_scan_task(task_id: int, db: Session = Depends(get_db)):
    """停止扫描任务"""
    success = SecurityPlatformService.stop_scan_task(task_id, db)
    if not success:
        raise HTTPException(status_code=400, detail="无法停止任务")
    
    return {"success": True, "message": "任务已停止"}


# ============================================
# 扫描结果 API
# ============================================

@router.get("/tasks/{task_id}/results")
def get_scan_results(task_id: int, db: Session = Depends(get_db)):
    """获取扫描结果"""
    results = SecurityPlatformService.get_scan_results(task_id, db)
    result_list = [
        ScanResultResponse(
            id=result.id,
            task_id=result.task_id,
            tool=result.tool,
            severity=result.severity,
            title=result.title,
            description=result.description,
            url=result.url,
            param=result.param,
            payload=result.payload,
            created_at=result.created_at
        )
        for result in results
    ]
    
    return {
        "success": True,
        "data": result_list,
        "message": "获取扫描结果成功"
    }


@router.get("/results/{result_id}")
def get_scan_result(result_id: int, db: Session = Depends(get_db)):
    """获取单个扫描结果详情"""
    result = SecurityPlatformService.get_scan_result(result_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="结果不存在")
    
    result_data = {
        "id": result.id,
        "task_id": result.task_id,
        "tool": result.tool,
        "severity": result.severity,
        "title": result.title,
        "description": result.description,
        "evidence": result.evidence,
        "url": result.url,
        "param": result.param,
        "payload": result.payload,
        "raw_output": result.raw_output,
        "created_at": result.created_at.isoformat()
    }
    
    return {
        "success": True,
        "data": result_data,
        "message": "获取扫描结果详情成功"
    }


# ============================================
# 漏洞管理 API
# ============================================

@router.get("/vulnerabilities")
def get_vulnerabilities(
    target_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """获取漏洞列表"""
    vulns = SecurityPlatformService.get_vulnerabilities(
        db, target_id, severity, status, skip, limit
    )
    vuln_list = [
        VulnerabilityResponse(
            id=vuln.id,
            target_id=vuln.target_id,
            title=vuln.title,
            severity=vuln.severity,
            vuln_type=vuln.vuln_type,
            description=vuln.description,
            fix_suggestion=vuln.fix_suggestion,
            status=vuln.status,
            risk_score=vuln.risk_score,
            first_found=vuln.first_found,
            last_seen=vuln.last_seen
        )
        for vuln in vulns
    ]
    
    return {
        "success": True,
        "data": vuln_list,
        "message": "获取漏洞列表成功"
    }


@router.get("/vulnerabilities/{vuln_id}")
def get_vulnerability(vuln_id: int, db: Session = Depends(get_db)):
    """获取单个漏洞详情"""
    vuln = SecurityPlatformService.get_vulnerability(vuln_id, db)
    if not vuln:
        raise HTTPException(status_code=404, detail="漏洞不存在")
    
    vuln_data = {
        "id": vuln.id,
        "target_id": vuln.target_id,
        "title": vuln.title,
        "severity": vuln.severity,
        "vuln_type": vuln.vuln_type,
        "description": vuln.description,
        "fix_suggestion": vuln.fix_suggestion,
        "status": vuln.status,
        "risk_score": vuln.risk_score,
        "first_found": vuln.first_found.isoformat(),
        "last_seen": vuln.last_seen.isoformat(),
        "scan_results": vuln.scan_results,
        "created_at": vuln.created_at.isoformat(),
        "updated_at": vuln.updated_at.isoformat()
    }
    
    return {
        "success": True,
        "data": vuln_data,
        "message": "获取漏洞详情成功"
    }


@router.put("/vulnerabilities/{vuln_id}/status")
def update_vulnerability_status(
    vuln_id: int,
    request: UpdateVulnStatusRequest,
    db: Session = Depends(get_db)
):
    """更新漏洞状态"""
    success = SecurityPlatformService.update_vulnerability_status(
        vuln_id, request.status, db
    )
    if not success:
        raise HTTPException(status_code=400, detail="更新失败")
    
    return {"success": True, "message": f"状态已更新为 {request.status}"}


# ============================================
# 扫描日志 API
# ============================================

@router.get("/tasks/{task_id}/logs")
def get_scan_logs(task_id: int, db: Session = Depends(get_db)):
    """获取扫描日志"""
    logs = SecurityPlatformService.get_scan_logs(task_id, db)
    return {
        "success": True,
        "data": [
            {
                "id": log.id,
                "level": log.level,
                "message": log.message,
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ]
    }


# ============================================
# 仪表板 API
# ============================================

@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    """获取仪表板统计信息"""
    stats = SecurityPlatformService.get_dashboard_stats(db)
    return {
        "success": True,
        "data": stats
    }


# ============================================
# 工具状态检查 API
# ============================================

@router.get("/tools/status")
async def check_tools_status():
    """检查扫描工具状态 - 严格按照方案的4个工具"""
    from Security_Test.tools.nuclei_runner import NucleiRunner
    from Security_Test.tools.sqlmap_runner import SqlmapRunner
    from Security_Test.tools.xsstrike_runner import XSStrikeRunner
    from Security_Test.tools.fuzz_runner import FuzzRunner
    
    tools_status = {}
    
    # 检查方案指定的4个工具状态
    nuclei = NucleiRunner()
    tools_status["nuclei"] = await nuclei.check_available()
    
    sqlmap = SqlmapRunner()
    tools_status["sqlmap"] = await sqlmap.check_available()
    
    xsstrike = XSStrikeRunner()
    tools_status["xsstrike"] = await xsstrike.check_available()
    
    fuzz = FuzzRunner()
    tools_status["fuzz"] = await fuzz.check_available()
    
    return {
        "success": True,
        "data": tools_status,
        "message": "按照安全测试方案，支持4个核心工具: nuclei, sqlmap, xsstrike, fuzz"
    }


# ============================================
# 扫描日志查询 API (前端需要的通用日志接口)
# ============================================

@router.get("/logs")
def get_logs(
    task_id: Optional[int] = Query(None),
    level: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """获取扫描日志 (支持筛选)"""
    logs = SecurityPlatformService.get_logs_filtered(db, task_id, level, skip, limit)
    return {
        "success": True,
        "data": [
            {
                "id": log.id,
                "task_id": log.task_id,
                "level": log.level,
                "message": log.message,
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ]
    }


# ============================================
# 报告管理 API
# ============================================

class ReportGenerateRequest(BaseModel):
    """生成报告请求"""
    task_id: int
    format: str  # html/markdown/json


@router.get("/reports")
def get_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """获取报告历史"""
    reports = SecurityPlatformService.get_reports(db, skip, limit)
    return {
        "success": True,
        "data": [
            {
                "id": report.id,
                "task_id": report.task_id,
                "format": report.format,
                "filename": report.filename,
                "file_path": report.file_path,
                "created_at": report.created_at.isoformat()
            }
            for report in reports
        ]
    }


@router.post("/reports")
async def generate_report(
    request: ReportGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """生成报告"""
    try:
        # 异步生成报告
        report = await SecurityPlatformService.generate_report(
            request.task_id, request.format, db
        )
        
        return {
            "success": True,
            "data": {
                "id": report.id,
                "task_id": report.task_id,
                "format": report.format,
                "filename": report.filename,
                "created_at": report.created_at.isoformat()
            },
            "message": "报告生成成功"
        }
        
    except Exception as e:
        logger.error(f"生成报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")


@router.get("/reports/{report_id}/download")
async def download_report(report_id: int, db: Session = Depends(get_db)):
    """下载报告"""
    from fastapi.responses import FileResponse
    import os
    
    report = SecurityPlatformService.get_report(report_id, db)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    if not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="报告文件不存在")
    
    return FileResponse(
        path=report.file_path,
        filename=report.filename,
        media_type='application/octet-stream'
    )


# ============================================
# 统计信息 API
# ============================================

@router.get("/stats")
def get_security_stats(db: Session = Depends(get_db)):
    """获取安全测试统计信息"""
    stats = SecurityPlatformService.get_security_stats(db)
    return {
        "success": True,
        "data": stats
    }


# ============================================
# 任务删除 API
# ============================================

@router.delete("/tasks/{task_id}")
def delete_scan_task(task_id: int, db: Session = Depends(get_db)):
    """删除扫描任务"""
    success = SecurityPlatformService.delete_scan_task(task_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return {"success": True, "message": "任务已删除"}


# ============================================
# 漏洞更新 API (PUT方式)
# ============================================

@router.put("/vulnerabilities/{vuln_id}")
def update_vulnerability(
    vuln_id: int,
    request: UpdateVulnStatusRequest,
    db: Session = Depends(get_db)
):
    """更新漏洞信息"""
    success = SecurityPlatformService.update_vulnerability_status(
        vuln_id, request.status, db
    )
    if not success:
        raise HTTPException(status_code=400, detail="更新失败")
    
    return {"success": True, "message": f"漏洞状态已更新为 {request.status}"}
