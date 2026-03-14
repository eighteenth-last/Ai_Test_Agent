"""
安全测试平台扫描引擎

基于工业级方案设计的扫描引擎，负责统一调度所有扫描工具

支持的扫描类型:
- nuclei: Web 漏洞扫描
- sqlmap: SQL 注入验证
- xsstrike: XSS 漏洞检测
- fuzz: 自定义模糊测试
- full_scan: 全面扫描（组合所有工具）

作者: 程序员Eighteen
"""
import asyncio
import json
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from database.connection import (
    SecurityTarget, SecurityScanTask, SecurityScanResult,
    SecurityVulnerability, SecurityScanLog
)

# 导入扫描工具
from Security_Test.tools.nuclei_runner import NucleiRunner
from Security_Test.tools.sqlmap_runner import SqlmapRunner
from Security_Test.tools.xsstrike_runner import XSStrikeRunner
from Security_Test.tools.fuzz_runner import FuzzRunner

logger = logging.getLogger(__name__)


class ScanEngine:
    """扫描引擎 - 统一调度所有扫描工具"""
    
    def __init__(self, db: Session):
        self.db = db
        
        # 初始化扫描工具
        self.runners = {
            "nuclei": NucleiRunner(),
            "sqlmap": SqlmapRunner(),
            "xsstrike": XSStrikeRunner(),
            "fuzz": FuzzRunner(),
        }
    
    async def run_scan(self, task_id: int) -> bool:
        """
        执行扫描任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功
        """
        task = self.db.query(SecurityScanTask).filter(
            SecurityScanTask.id == task_id
        ).first()
        
        if not task:
            logger.error(f"[ScanEngine] 任务不存在: {task_id}")
            return False
        
        target = self.db.query(SecurityTarget).filter(
            SecurityTarget.id == task.target_id
        ).first()
        
        if not target:
            logger.error(f"[ScanEngine] 目标不存在: {task.target_id}")
            return False
        
        try:
            # 更新任务状态
            task.status = "running"
            task.start_time = datetime.now()
            task.progress = 0
            self.db.commit()
            
            self._log(task_id, "info", f"开始执行 {task.scan_type} 扫描: {target.base_url}")
            
            # 根据扫描类型调用不同工具
            results = []
            
            if task.scan_type == "full_scan":
                results = await self._run_full_scan(task, target)
            elif task.scan_type in self.runners:
                results = await self._run_single_tool(task, target, task.scan_type)
            else:
                raise ValueError(f"不支持的扫描类型: {task.scan_type}")
            
            # 保存扫描结果
            self._save_results(task_id, task.scan_type, results)
            
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
            logger.error(f"[ScanEngine] 扫描任务 {task_id} 执行失败: {e}")
            logger.error(traceback.format_exc())
            
            task.status = "failed"
            task.error_message = str(e)
            task.end_time = datetime.now()
            
            if task.start_time:
                task.duration = int((task.end_time - task.start_time).total_seconds())
            
            self.db.commit()
            self._log(task_id, "error", f"扫描失败: {e}")
            
            return False
    
    async def _run_single_tool(
        self,
        task: SecurityScanTask,
        target: SecurityTarget,
        tool_name: str
    ) -> List[Dict]:
        """
        运行单个扫描工具
        
        Args:
            task: 扫描任务
            target: 扫描目标
            tool_name: 工具名称
            
        Returns:
            扫描结果列表
        """
        runner = self.runners.get(tool_name)
        
        if not runner:
            raise ValueError(f"未知的扫描工具: {tool_name}")
        
        # 检查工具是否可用
        availability = await runner.check_available()
        
        if not availability.get("available"):
            logger.warning(f"[ScanEngine] {tool_name} 不可用: {availability.get('message')}")
            self._log(task.id, "warning", f"{tool_name} 不可用，跳过扫描")
            return []
        
        self._log(task.id, "info", f"使用 {tool_name} 扫描 ({availability.get('version')})")
        
        # 更新进度
        task.progress = 10
        self.db.commit()
        
        # 执行扫描
        config = task.config or {}
        results = await runner.run_scan(target.base_url, config)
        
        # 更新进度
        task.progress = 90
        self.db.commit()
        
        return results
    
    async def _run_full_scan(
        self,
        task: SecurityScanTask,
        target: SecurityTarget
    ) -> List[Dict]:
        """
        运行全面扫描 - 按照方案依次执行所有工具
        
        Args:
            task: 扫描任务
            target: 扫描目标
            
        Returns:
            所有工具的扫描结果
        """
        all_results = []
        tools = ["nuclei", "sqlmap", "xsstrike", "fuzz"]
        
        self._log(task.id, "info", "开始全面扫描，将依次执行: " + ", ".join(tools))
        
        for i, tool_name in enumerate(tools):
            try:
                self._log(task.id, "info", f"[{i+1}/{len(tools)}] 开始 {tool_name} 扫描")
                
                # 执行单个工具
                results = await self._run_single_tool(task, target, tool_name)
                
                all_results.extend(results)
                
                self._log(
                    task.id,
                    "info",
                    f"[{i+1}/{len(tools)}] {tool_name} 扫描完成，发现 {len(results)} 个结果"
                )
                
                # 更新进度
                task.progress = int((i + 1) / len(tools) * 90)
                self.db.commit()
                
            except Exception as e:
                logger.error(f"[ScanEngine] {tool_name} 扫描失败: {e}")
                self._log(task.id, "error", f"{tool_name} 扫描失败: {e}")
                # 继续执行其他工具
                continue
        
        return all_results
    
    def _save_results(
        self,
        task_id: int,
        scan_type: str,
        results: List[Dict]
    ):
        """
        保存扫描结果到数据库
        
        Args:
            task_id: 任务ID
            scan_type: 扫描类型
            results: 扫描结果列表
        """
        for result in results:
            scan_result = SecurityScanResult(
                task_id=task_id,
                tool=result.get("tool", scan_type),
                severity=result.get("severity", "info"),
                title=result.get("title", "未知漏洞"),
                description=result.get("description"),
                evidence=result.get("evidence"),
                url=result.get("url"),
                param=result.get("param"),
                payload=result.get("payload"),
                raw_output=result.get("raw_output")
            )
            self.db.add(scan_result)
        
        self.db.commit()
        logger.info(f"[ScanEngine] 已保存 {len(results)} 条扫描结果")
    
    def _generate_vulnerabilities(
        self,
        target_id: int,
        results: List[Dict]
    ):
        """
        从扫描结果生成漏洞记录
        
        Args:
            target_id: 目标ID
            results: 扫描结果列表
        """
        # 只处理中危及以上的漏洞
        high_severity_results = [
            r for r in results
            if r.get("severity") in ["critical", "high", "medium"]
        ]
        
        if not high_severity_results:
            logger.info("[ScanEngine] 未发现中危及以上漏洞")
            return
        
        # 按标题和URL分组去重
        vuln_groups = {}
        
        for result in high_severity_results:
            title = result.get("title", "未知漏洞")
            url = result.get("url", "")
            key = f"{title}_{url}"
            
            if key not in vuln_groups:
                vuln_groups[key] = []
            
            vuln_groups[key].append(result)
        
        # 创建或更新漏洞记录
        for group_results in vuln_groups.values():
            first_result = group_results[0]
            title = first_result.get("title", "未知漏洞")
            
            # 检查是否已存在相同漏洞
            existing = self.db.query(SecurityVulnerability).filter(
                SecurityVulnerability.target_id == target_id,
                SecurityVulnerability.title == title,
                SecurityVulnerability.status == "open"
            ).first()
            
            if existing:
                # 更新最后发现时间
                existing.last_seen = datetime.now()
                self.db.commit()
                logger.info(f"[ScanEngine] 更新已存在漏洞: {title}")
            else:
                # 创建新漏洞
                severity = first_result.get("severity", "info")
                vuln_type = self._extract_vuln_type(title)
                
                vulnerability = SecurityVulnerability(
                    target_id=target_id,
                    title=title,
                    severity=severity,
                    vuln_type=vuln_type,
                    description=first_result.get("description", ""),
                    fix_suggestion=self._get_fix_suggestion(vuln_type),
                    risk_score=self._calculate_risk_score(severity),
                    status="open"
                )
                
                self.db.add(vulnerability)
                logger.info(f"[ScanEngine] 创建新漏洞记录: {title}")
        
        self.db.commit()
    
    def _extract_vuln_type(self, title: str) -> str:
        """
        从标题中提取漏洞类型
        
        Args:
            title: 漏洞标题
            
        Returns:
            漏洞类型
        """
        title_lower = title.lower()
        
        type_keywords = {
            "sql": "sql_injection",
            "xss": "xss",
            "csrf": "csrf",
            "lfi": "lfi",
            "rfi": "rfi",
            "xxe": "xxe",
            "ssrf": "ssrf",
            "command": "command_injection",
            "path": "path_traversal",
        }
        
        for keyword, vuln_type in type_keywords.items():
            if keyword in title_lower:
                return vuln_type
        
        return "other"
    
    def _get_fix_suggestion(self, vuln_type: str) -> str:
        """
        获取修复建议
        
        Args:
            vuln_type: 漏洞类型
            
        Returns:
            修复建议
        """
        suggestions = {
            "sql_injection": "使用参数化查询或预编译语句，避免直接拼接SQL语句。对用户输入进行严格验证和过滤。",
            "xss": "对所有用户输入进行HTML编码，使用Content Security Policy (CSP)策略，避免使用innerHTML等危险API。",
            "csrf": "使用CSRF Token验证请求来源，检查Referer头，使用SameSite Cookie属性。",
            "lfi": "验证文件路径，使用白名单限制可访问文件，避免使用用户输入直接构造文件路径。",
            "rfi": "禁用远程文件包含功能，验证URL来源，使用白名单限制可包含的文件。",
            "xxe": "禁用XML外部实体解析，使用安全的XML解析器配置。",
            "ssrf": "验证URL格式和协议，使用白名单限制可访问的域名和IP，禁止访问内网地址。",
            "command_injection": "避免使用shell命令执行用户输入，使用安全的API替代，对输入进行严格过滤。",
            "path_traversal": "验证文件路径，使用白名单限制可访问目录，规范化路径后再使用。",
        }
        
        return suggestions.get(vuln_type, "请根据漏洞类型和具体情况制定相应的修复方案，建议咨询安全专家。")
    
    def _calculate_risk_score(self, severity: str) -> int:
        """
        计算风险评分 (0-100)
        
        Args:
            severity: 严重程度
            
        Returns:
            风险评分
        """
        scores = {
            "critical": 95,
            "high": 75,
            "medium": 50,
            "low": 25,
            "info": 10
        }
        
        return scores.get(severity.lower(), 10)
    
    def _log(self, task_id: int, level: str, message: str):
        """
        记录扫描日志
        
        Args:
            task_id: 任务ID
            level: 日志级别 (debug/info/warning/error)
            message: 日志消息
        """
        log = SecurityScanLog(
            task_id=task_id,
            level=level,
            message=message
        )
        
        self.db.add(log)
        self.db.commit()
        
        # 同时输出到日志文件
        log_func = getattr(logger, level, logger.info)
        log_func(f"[Task {task_id}] {message}")
