"""
扫描引擎 - 统一调度各种扫描工具

作者: Ai_Test_Agent Team
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from database.connection import (
    SecurityTarget, SecurityScanTask, SecurityScanResult, 
    SecurityVulnerability, SecurityScanLog
)

logger = logging.getLogger(__name__)


class ScanEngine:
    """扫描引擎 - 负责调度工具"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def run_scan(self, task_id: int) -> bool:
        """
        执行扫描任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        task = self.db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return False
        
        target = self.db.query(SecurityTarget).filter(SecurityTarget.id == task.target_id).first()
        if not target:
            logger.error(f"目标不存在: {task.target_id}")
            return False
        
        try:
            # 更新任务状态
            task.status = "running"
            task.start_time = datetime.now()
            self.db.commit()
            
            self._log(task_id, "info", f"开始执行 {task.scan_type} 扫描")
            
            # 根据扫描类型调用不同工具 - 严格按照方案
            results = []
            if task.scan_type == "nuclei":
                results = await self._run_nuclei(task, target)
            elif task.scan_type == "sqlmap":
                results = await self._run_sqlmap(task, target)
            elif task.scan_type == "xsstrike":
                results = await self._run_xsstrike(task, target)
            elif task.scan_type == "fuzz":
                results = await self._run_fuzz(task, target)
            elif task.scan_type == "full_scan":
                results = await self._run_full_scan(task, target)
            else:
                raise ValueError(f"不支持的扫描类型: {task.scan_type}")
            
            # 保存扫描结果
            self._save_results(task_id, results)
            
            # 生成漏洞记录
            self._generate_vulnerabilities(task.target_id, results)
            
            # 完成任务
            task.status = "finished"
            task.end_time = datetime.now()
            task.duration = int((task.end_time - task.start_time).total_seconds())
            task.progress = 100
            self.db.commit()
            
            self._log(task_id, "info", f"扫描完成，发现 {len(results)} 个结果")
            return True
            
        except Exception as e:
            logger.error(f"扫描任务 {task_id} 执行失败: {e}")
            task.status = "failed"
            task.error_message = str(e)
            task.end_time = datetime.now()
            if task.start_time:
                task.duration = int((task.end_time - task.start_time).total_seconds())
            self.db.commit()
            
            self._log(task_id, "error", f"扫描失败: {e}")
            return False
    
    async def _run_nuclei(self, task: SecurityScanTask, target: SecurityTarget) -> List[Dict]:
        """运行 Nuclei 扫描"""
        from Security_Test.tools.nuclei_runner import NucleiRunner
        
        runner = NucleiRunner()
        
        # 检查工具是否可用
        if not await runner.check_available():
            logger.warning("Nuclei 工具不可用，跳过扫描")
            self._log_scan_message(task.id, "warning", "Nuclei 工具不可用，跳过扫描")
            return []
        
        config = task.config or {}
        
        # 更新进度
        task.progress = 10
        self.db.commit()
        
        results = await runner.run(target.base_url, config)
        
        task.progress = 90
        self.db.commit()
        
        return results
    
    async def _run_sqlmap(self, task: SecurityScanTask, target: SecurityTarget) -> List[Dict]:
        """运行 SQLMap 扫描"""
        from Security_Test.tools.sqlmap_runner import SqlmapRunner
        
        runner = SqlmapRunner()
        
        # 检查工具是否可用
        if not await runner.check_available():
            logger.warning("SQLMap 工具不可用，跳过扫描")
            self._log_scan_message(task.id, "warning", "SQLMap 工具不可用，跳过扫描")
            return []
        
        config = task.config or {}
        
        task.progress = 10
        self.db.commit()
        
        results = await runner.run(target.base_url, config)
        
        task.progress = 90
        self.db.commit()
        
        return results
    
    async def _run_xsstrike(self, task: SecurityScanTask, target: SecurityTarget) -> List[Dict]:
        """运行 XSStrike 扫描"""
        from Security_Test.tools.xsstrike_runner import XSStrikeRunner
        
        runner = XSStrikeRunner()
        config = task.config or {}
        
        task.progress = 10
        self.db.commit()
        
        results = await runner.run(target.base_url, config)
        
        task.progress = 90
        self.db.commit()
        
        return results
    
    async def _run_fuzz(self, task: SecurityScanTask, target: SecurityTarget) -> List[Dict]:
        """运行 Fuzz 扫描"""
        from Security_Test.tools.fuzz_runner import FuzzRunner
        
        runner = FuzzRunner()
        config = task.config or {}
        
        task.progress = 10
        self.db.commit()
        
        results = await runner.run(target.base_url, config)
        
        task.progress = 90
        self.db.commit()
        
        return results
    
    async def _run_full_scan(self, task: SecurityScanTask, target: SecurityTarget) -> List[Dict]:
        """运行全面扫描 - 按照方案依次执行所有工具"""
        all_results = []
        # 严格按照方案的4个工具
        tools = ["nuclei", "sqlmap", "xsstrike", "fuzz"]
        
        for i, tool in enumerate(tools):
            self._log(task.id, "info", f"开始 {tool} 扫描")
            
            # 创建临时任务配置
            temp_task = SecurityScanTask(
                target_id=task.target_id,
                scan_type=tool,
                config=task.config
            )
            
            if tool == "nuclei":
                results = await self._run_nuclei(temp_task, target)
            elif tool == "sqlmap":
                results = await self._run_sqlmap(temp_task, target)
            elif tool == "xsstrike":
                results = await self._run_xsstrike(temp_task, target)
            elif tool == "fuzz":
                results = await self._run_fuzz(temp_task, target)
            
            all_results.extend(results)
            
            # 更新进度
            task.progress = int((i + 1) / len(tools) * 90)
            self.db.commit()
        
        return all_results
    
    def _save_results(self, task_id: int, results: List[Dict]):
        """保存扫描结果"""
        for result in results:
            scan_result = SecurityScanResult(
                task_id=task_id,
                tool=result.get("tool", "unknown"),
                severity=result.get("severity", "info"),
                title=result.get("title", ""),
                description=result.get("description"),
                evidence=result.get("evidence"),
                url=result.get("url"),
                param=result.get("param"),
                payload=result.get("payload"),
                raw_output=result.get("raw_output")
            )
            self.db.add(scan_result)
        
        self.db.commit()
    
    def _generate_vulnerabilities(self, target_id: int, results: List[Dict]):
        """生成漏洞记录"""
        # 按漏洞类型和URL分组
        vuln_groups = {}
        
        for result in results:
            if result.get("severity") in ["critical", "high", "medium"]:
                key = f"{result.get('title', '')}_{result.get('url', '')}"
                if key not in vuln_groups:
                    vuln_groups[key] = []
                vuln_groups[key].append(result)
        
        # 创建漏洞记录
        for group_results in vuln_groups.values():
            first_result = group_results[0]
            
            # 检查是否已存在相同漏洞
            existing = self.db.query(SecurityVulnerability).filter(
                SecurityVulnerability.target_id == target_id,
                SecurityVulnerability.title == first_result.get("title", "")
            ).first()
            
            if existing:
                # 更新最后发现时间
                existing.last_seen = datetime.now()
                self.db.commit()
            else:
                # 创建新漏洞
                vulnerability = SecurityVulnerability(
                    target_id=target_id,
                    title=first_result.get("title", ""),
                    severity=first_result.get("severity", "info"),
                    vuln_type=first_result.get("vuln_type"),
                    description=first_result.get("description"),
                    fix_suggestion=self._get_fix_suggestion(first_result),
                    risk_score=self._calculate_risk_score(first_result.get("severity", "info"))
                )
                self.db.add(vulnerability)
        
        self.db.commit()
    
    def _get_fix_suggestion(self, result: Dict) -> str:
        """获取修复建议"""
        vuln_type = result.get("vuln_type", "").lower()
        
        suggestions = {
            "sql_injection": "使用参数化查询或预编译语句，避免直接拼接SQL",
            "xss": "对用户输入进行HTML编码，使用CSP策略",
            "csrf": "使用CSRF Token验证请求来源",
            "lfi": "验证文件路径，使用白名单限制访问",
            "rfi": "禁用远程文件包含，验证URL来源"
        }
        
        return suggestions.get(vuln_type, "请根据漏洞类型制定相应的修复方案")
    
    def _calculate_risk_score(self, severity: str) -> int:
        """计算风险评分"""
        scores = {
            "critical": 90,
            "high": 70,
            "medium": 50,
            "low": 30,
            "info": 10
        }
        return scores.get(severity.lower(), 10)
    
    def _log(self, task_id: int, level: str, message: str):
        """记录日志"""
        log = SecurityScanLog(
            task_id=task_id,
            level=level,
            message=message
        )
        self.db.add(log)
        self.db.commit()
        
        logger.info(f"[Task {task_id}] {message}")