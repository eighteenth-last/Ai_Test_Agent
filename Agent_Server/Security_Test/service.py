"""
安全测试平台服务

基于新架构设计的安全测试服务，支持：
1. 资产管理 - 目标管理
2. 扫描任务 - 任务调度
3. 扫描引擎 - 工具统一调度
4. 漏洞管理 - 漏洞记录和跟踪
5. 报告系统 - 报告生成

作者: Ai_Test_Agent Team
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from database.connection import (
    SecurityTarget, SecurityScanTask, SecurityScanResult,
    SecurityVulnerability, SecurityScanLog, SessionLocal
)
from Security_Test.scan_engine import ScanEngine
from Security_Test.models import SecurityTargetCreate, SecurityTargetUpdate, ScanTaskCreate

logger = logging.getLogger(__name__)


class SecurityPlatformService:
    """安全测试平台服务"""
    
    # ============================================
    # 资产管理
    # ============================================
    
    @staticmethod
    def create_target(target_data: SecurityTargetCreate, db: Session) -> SecurityTarget:
        """创建安全目标"""
        target = SecurityTarget(
            name=target_data.name,
            base_url=target_data.base_url,
            description=target_data.description,
            target_type=target_data.target_type,
            environment=target_data.environment,
            auth_config=target_data.auth_config,
            scan_config=target_data.scan_config
        )
        db.add(target)
        db.commit()
        db.refresh(target)
        return target
    
    @staticmethod
    def get_targets(db: Session, skip: int = 0, limit: int = 100) -> List[SecurityTarget]:
        """获取目标列表"""
        return db.query(SecurityTarget).filter(
            SecurityTarget.is_active == 1
        ).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_target(target_id: int, db: Session) -> Optional[SecurityTarget]:
        """获取单个目标"""
        return db.query(SecurityTarget).filter(
            SecurityTarget.id == target_id,
            SecurityTarget.is_active == 1
        ).first()
    
    @staticmethod
    def update_target(target_id: int, target_data: SecurityTargetUpdate, db: Session) -> Optional[SecurityTarget]:
        """更新目标"""
        target = db.query(SecurityTarget).filter(SecurityTarget.id == target_id).first()
        if not target:
            return None
        
        update_data = target_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(target, field, value)
        
        target.updated_at = datetime.now()
        db.commit()
        db.refresh(target)
        return target
    
    @staticmethod
    def delete_target(target_id: int, db: Session) -> bool:
        """删除目标（软删除）"""
        target = db.query(SecurityTarget).filter(SecurityTarget.id == target_id).first()
        if not target:
            return False
        
        target.is_active = 0
        target.updated_at = datetime.now()
        db.commit()
        return True
    
    # ============================================
    # 扫描任务管理
    # ============================================
    
    @staticmethod
    def create_scan_task(task_data: ScanTaskCreate, db: Session) -> SecurityScanTask:
        """创建扫描任务"""
        # 验证目标是否存在
        target = db.query(SecurityTarget).filter(
            SecurityTarget.id == task_data.target_id,
            SecurityTarget.is_active == 1
        ).first()
        
        if not target:
            raise ValueError(f"目标不存在: {task_data.target_id}")
        
        # 验证扫描类型 - 严格按照方案
        valid_types = ["nuclei", "sqlmap", "xsstrike", "fuzz", "full_scan"]
        if task_data.scan_type not in valid_types:
            raise ValueError(f"无效的扫描类型: {task_data.scan_type}，支持的类型: {valid_types}")
        
        task = SecurityScanTask(
            target_id=task_data.target_id,
            scan_type=task_data.scan_type,
            config=task_data.config
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    
    @staticmethod
    async def execute_scan_task(task_id: int) -> bool:
        """执行扫描任务"""
        db = SessionLocal()
        try:
            engine = ScanEngine(db)
            return await engine.run_scan(task_id)
        finally:
            db.close()
    
    @staticmethod
    def get_scan_tasks(db: Session, target_id: Optional[int] = None, 
                      skip: int = 0, limit: int = 100) -> List[SecurityScanTask]:
        """获取扫描任务列表"""
        query = db.query(SecurityScanTask)
        if target_id:
            query = query.filter(SecurityScanTask.target_id == target_id)
        
        return query.order_by(SecurityScanTask.id.desc()).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_scan_task(task_id: int, db: Session) -> Optional[SecurityScanTask]:
        """获取单个扫描任务"""
        return db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
    
    @staticmethod
    def stop_scan_task(task_id: int, db: Session) -> bool:
        """停止扫描任务"""
        task = db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
        if not task or task.status not in ["pending", "running"]:
            return False
        
        task.status = "stopped"
        task.end_time = datetime.now()
        if task.start_time:
            task.duration = int((task.end_time - task.start_time).total_seconds())
        db.commit()
        return True
    
    # ============================================
    # 扫描结果管理
    # ============================================
    
    @staticmethod
    def get_scan_results(task_id: int, db: Session) -> List[SecurityScanResult]:
        """获取扫描结果"""
        return db.query(SecurityScanResult).filter(
            SecurityScanResult.task_id == task_id
        ).all()
    
    @staticmethod
    def get_scan_result(result_id: int, db: Session) -> Optional[SecurityScanResult]:
        """获取单个扫描结果"""
        return db.query(SecurityScanResult).filter(SecurityScanResult.id == result_id).first()
    
    # ============================================
    # 漏洞管理
    # ============================================
    
    @staticmethod
    def get_vulnerabilities(db: Session, target_id: Optional[int] = None,
                          severity: Optional[str] = None, status: Optional[str] = None,
                          skip: int = 0, limit: int = 100) -> List[SecurityVulnerability]:
        """获取漏洞列表"""
        query = db.query(SecurityVulnerability)
        
        if target_id:
            query = query.filter(SecurityVulnerability.target_id == target_id)
        
        if severity:
            query = query.filter(SecurityVulnerability.severity == severity)
        
        if status:
            query = query.filter(SecurityVulnerability.status == status)
        
        return query.order_by(SecurityVulnerability.id.desc()).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_vulnerability(vuln_id: int, db: Session) -> Optional[SecurityVulnerability]:
        """获取单个漏洞"""
        return db.query(SecurityVulnerability).filter(SecurityVulnerability.id == vuln_id).first()
    
    @staticmethod
    def update_vulnerability_status(vuln_id: int, status: str, db: Session) -> bool:
        """更新漏洞状态"""
        valid_statuses = ["open", "fixed", "false_positive", "accepted"]
        if status not in valid_statuses:
            return False
        
        vuln = db.query(SecurityVulnerability).filter(SecurityVulnerability.id == vuln_id).first()
        if not vuln:
            return False
        
        vuln.status = status
        vuln.updated_at = datetime.now()
        db.commit()
        return True
    
    # ============================================
    # 扫描日志
    # ============================================
    
    @staticmethod
    def get_scan_logs(task_id: int, db: Session) -> List[SecurityScanLog]:
        """获取扫描日志"""
        return db.query(SecurityScanLog).filter(
            SecurityScanLog.task_id == task_id
        ).order_by(SecurityScanLog.id.asc()).all()
    
    # ============================================
    # 统计信息
    # ============================================
    
    @staticmethod
    def get_dashboard_stats(db: Session) -> Dict:
        """获取仪表板统计信息"""
        # 目标统计
        total_targets = db.query(SecurityTarget).filter(SecurityTarget.is_active == 1).count()
        
        # 任务统计
        total_tasks = db.query(SecurityScanTask).count()
        running_tasks = db.query(SecurityScanTask).filter(SecurityScanTask.status == "running").count()
        finished_tasks = db.query(SecurityScanTask).filter(SecurityScanTask.status == "finished").count()
        
        # 漏洞统计
        total_vulns = db.query(SecurityVulnerability).count()
        critical_vulns = db.query(SecurityVulnerability).filter(SecurityVulnerability.severity == "critical").count()
        high_vulns = db.query(SecurityVulnerability).filter(SecurityVulnerability.severity == "high").count()
        medium_vulns = db.query(SecurityVulnerability).filter(SecurityVulnerability.severity == "medium").count()
        low_vulns = db.query(SecurityVulnerability).filter(SecurityVulnerability.severity == "low").count()
        
        # 状态统计
        open_vulns = db.query(SecurityVulnerability).filter(SecurityVulnerability.status == "open").count()
        fixed_vulns = db.query(SecurityVulnerability).filter(SecurityVulnerability.status == "fixed").count()
        
        return {
            "targets": {
                "total": total_targets
            },
            "tasks": {
                "total": total_tasks,
                "running": running_tasks,
                "finished": finished_tasks
            },
            "vulnerabilities": {
                "total": total_vulns,
                "by_severity": {
                    "critical": critical_vulns,
                    "high": high_vulns,
                    "medium": medium_vulns,
                    "low": low_vulns
                },
                "by_status": {
                    "open": open_vulns,
                    "fixed": fixed_vulns
                }
            }
        }
    # ============================================
    # 扫描日志管理 (新增方法)
    # ============================================
    
    @staticmethod
    def get_logs_filtered(
        db: Session, 
        task_id: Optional[int] = None,
        level: Optional[str] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[SecurityScanLog]:
        """获取筛选后的扫描日志"""
        query = db.query(SecurityScanLog)
        
        if task_id:
            query = query.filter(SecurityScanLog.task_id == task_id)
        if level:
            query = query.filter(SecurityScanLog.level == level)
            
        return query.order_by(SecurityScanLog.created_at.desc()).offset(skip).limit(limit).all()

    # ============================================
    # 报告管理 (新增方法)
    # ============================================
    
    @staticmethod
    def get_reports(db: Session, skip: int = 0, limit: int = 100):
        """获取报告列表 - 暂时返回空列表，后续实现报告表"""
        # TODO: 实现报告表和报告管理
        return []
    
    @staticmethod
    async def generate_report(task_id: int, format_type: str, db: Session):
        """生成报告 - 暂时返回模拟数据，后续实现"""
        from Security_Test.report_generator import ReportGenerator
        
        # 获取任务信息
        task = db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
        if not task:
            raise ValueError("任务不存在")
        
        # 生成报告
        generator = ReportGenerator()
        report_data = await generator.generate_task_report(task_id, format_type, db)
        
        # 返回模拟报告对象
        class MockReport:
            def __init__(self):
                self.id = task_id
                self.task_id = task_id
                self.format = format_type
                self.filename = f"security_report_{task_id}.{format_type}"
                self.created_at = datetime.now()
        
        return MockReport()
    
    @staticmethod
    def get_report(report_id: int, db: Session):
        """获取报告详情 - 暂时返回模拟数据"""
        # TODO: 实现报告表查询
        class MockReport:
            def __init__(self):
                self.id = report_id
                self.task_id = report_id
                self.format = "html"
                self.filename = f"security_report_{report_id}.html"
                self.file_path = f"/tmp/security_report_{report_id}.html"
        
        return MockReport()

    # ============================================
    # 统计信息 (新增方法)
    # ============================================
    
    @staticmethod
    def get_security_stats(db: Session) -> Dict:
        """获取安全测试统计信息"""
        return SecurityPlatformService.get_dashboard_stats(db)

    # ============================================
    # 任务删除 (新增方法)
    # ============================================
    
    @staticmethod
    def delete_scan_task(task_id: int, db: Session) -> bool:
        """删除扫描任务"""
        try:
            task = db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
            if not task:
                return False
            
            # 删除相关的扫描结果
            db.query(SecurityScanResult).filter(SecurityScanResult.task_id == task_id).delete()
            
            # 删除相关的扫描日志
            db.query(SecurityScanLog).filter(SecurityScanLog.task_id == task_id).delete()
            
            # 删除任务
            db.delete(task)
            db.commit()
            
            return True
        except Exception as e:
            logger.error(f"删除扫描任务失败: {e}")
            db.rollback()
            return False