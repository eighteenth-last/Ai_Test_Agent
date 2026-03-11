"""
安全测试报告生成器

作者: Ai_Test_Agent Team
"""
import json
from datetime import datetime
from typing import Dict, List, Optional
from jinja2 import Template

from sqlalchemy.orm import Session
from database.connection import (
    SecurityTarget, SecurityScanTask, SecurityScanResult,
    SecurityVulnerability, BugReport
)


class SecurityReportGenerator:
    """安全测试报告生成器"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_task_report(self, task_id: int, format_type: str = "markdown") -> str:
        """
        生成单个任务的扫描报告
        
        Args:
            task_id: 任务ID
            format_type: 报告格式 (markdown/html/json)
            
        Returns:
            str: 报告内容
        """
        # 获取任务信息
        task = self.db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        # 获取目标信息
        target = self.db.query(SecurityTarget).filter(SecurityTarget.id == task.target_id).first()
        
        # 获取扫描结果
        results = self.db.query(SecurityScanResult).filter(
            SecurityScanResult.task_id == task_id
        ).all()
        
        # 统计信息
        stats = self._calculate_stats(results)
        
        # 生成报告
        if format_type == "markdown":
            return self._generate_markdown_report(task, target, results, stats)
        elif format_type == "html":
            return self._generate_html_report(task, target, results, stats)
        elif format_type == "json":
            return self._generate_json_report(task, target, results, stats)
        else:
            raise ValueError(f"不支持的报告格式: {format_type}")
    
    def generate_target_report(self, target_id: int, format_type: str = "markdown") -> str:
        """
        生成目标的综合安全报告
        
        Args:
            target_id: 目标ID
            format_type: 报告格式
            
        Returns:
            str: 报告内容
        """
        # 获取目标信息
        target = self.db.query(SecurityTarget).filter(SecurityTarget.id == target_id).first()
        if not target:
            raise ValueError(f"目标不存在: {target_id}")
        
        # 获取所有相关任务
        tasks = self.db.query(SecurityScanTask).filter(
            SecurityScanTask.target_id == target_id
        ).order_by(SecurityScanTask.created_at.desc()).all()
        
        # 获取漏洞信息
        vulnerabilities = self.db.query(SecurityVulnerability).filter(
            SecurityVulnerability.target_id == target_id
        ).all()
        
        # 统计信息
        vuln_stats = self._calculate_vuln_stats(vulnerabilities)
        
        if format_type == "markdown":
            return self._generate_target_markdown_report(target, tasks, vulnerabilities, vuln_stats)
        elif format_type == "html":
            return self._generate_target_html_report(target, tasks, vulnerabilities, vuln_stats)
        else:
            raise ValueError(f"不支持的报告格式: {format_type}")
    
    def _calculate_stats(self, results: List[SecurityScanResult]) -> Dict:
        """计算扫描结果统计信息"""
        stats = {
            "total": len(results),
            "by_severity": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0
            },
            "by_tool": {}
        }
        
        for result in results:
            # 按严重程度统计
            severity = result.severity.lower()
            if severity in stats["by_severity"]:
                stats["by_severity"][severity] += 1
            
            # 按工具统计
            tool = result.tool
            if tool not in stats["by_tool"]:
                stats["by_tool"][tool] = 0
            stats["by_tool"][tool] += 1
        
        return stats
    
    def _calculate_vuln_stats(self, vulnerabilities: List[SecurityVulnerability]) -> Dict:
        """计算漏洞统计信息"""
        stats = {
            "total": len(vulnerabilities),
            "by_severity": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0
            },
            "by_status": {
                "open": 0,
                "fixed": 0,
                "false_positive": 0,
                "accepted": 0
            },
            "by_type": {}
        }
        
        for vuln in vulnerabilities:
            # 按严重程度统计
            severity = vuln.severity.lower()
            if severity in stats["by_severity"]:
                stats["by_severity"][severity] += 1
            
            # 按状态统计
            status = vuln.status
            if status in stats["by_status"]:
                stats["by_status"][status] += 1
            
            # 按类型统计
            vuln_type = vuln.vuln_type or "unknown"
            if vuln_type not in stats["by_type"]:
                stats["by_type"][vuln_type] = 0
            stats["by_type"][vuln_type] += 1
        
        return stats
    
    def _generate_markdown_report(self, task, target, results, stats) -> str:
        """生成Markdown格式报告"""
        template = Template("""
# 安全扫描报告

## 基本信息

- **目标名称**: {{ target.name if target else 'N/A' }}
- **目标URL**: {{ target.base_url if target else 'N/A' }}
- **扫描类型**: {{ task.scan_type }}
- **扫描状态**: {{ task.status }}
- **开始时间**: {{ task.start_time.strftime('%Y-%m-%d %H:%M:%S') if task.start_time else 'N/A' }}
- **结束时间**: {{ task.end_time.strftime('%Y-%m-%d %H:%M:%S') if task.end_time else 'N/A' }}
- **扫描耗时**: {{ task.duration }}秒

## 扫描统计

- **总发现数**: {{ stats.total }}
- **严重**: {{ stats.by_severity.critical }}
- **高危**: {{ stats.by_severity.high }}
- **中危**: {{ stats.by_severity.medium }}
- **低危**: {{ stats.by_severity.low }}
- **信息**: {{ stats.by_severity.info }}

## 工具统计

{% for tool, count in stats.by_tool.items() %}
- **{{ tool }}**: {{ count }}
{% endfor %}

## 扫描结果详情

{% for result in results %}
### {{ loop.index }}. {{ result.title }}

- **严重程度**: {{ result.severity }}
- **工具**: {{ result.tool }}
- **URL**: {{ result.url or 'N/A' }}
- **参数**: {{ result.param or 'N/A' }}
- **描述**: {{ result.description or 'N/A' }}

{% if result.payload %}
**攻击载荷**:
```
{{ result.payload }}
```
{% endif %}

---
{% endfor %}

## 修复建议

根据扫描结果，建议采取以下修复措施：

{% if stats.by_severity.critical > 0 %}
### 严重漏洞修复
- 立即修复所有严重漏洞
- 暂停相关功能直到修复完成
{% endif %}

{% if stats.by_severity.high > 0 %}
### 高危漏洞修复
- 在24小时内修复高危漏洞
- 加强输入验证和输出编码
{% endif %}

{% if stats.by_severity.medium > 0 %}
### 中危漏洞修复
- 在一周内修复中危漏洞
- 完善安全配置
{% endif %}

---
*报告生成时间: {{ now.strftime('%Y-%m-%d %H:%M:%S') }}*
        """)
        
        return template.render(
            task=task,
            target=target,
            results=results,
            stats=stats,
            now=datetime.now()
        )
    
    def _generate_html_report(self, task, target, results, stats) -> str:
        """生成HTML格式报告"""
        template = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>安全扫描报告</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f5f5f5; padding: 20px; border-radius: 5px; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat-card { background: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 5px; flex: 1; }
        .severity-critical { color: #d32f2f; }
        .severity-high { color: #f57c00; }
        .severity-medium { color: #fbc02d; }
        .severity-low { color: #388e3c; }
        .severity-info { color: #1976d2; }
        .result-item { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }
        .payload { background: #f5f5f5; padding: 10px; border-radius: 3px; font-family: monospace; }
    </style>
</head>
<body>
    <div class="header">
        <h1>安全扫描报告</h1>
        <p><strong>目标</strong>: {{ target.name if target else 'N/A' }} ({{ target.base_url if target else 'N/A' }})</p>
        <p><strong>扫描类型</strong>: {{ task.scan_type }}</p>
        <p><strong>扫描时间</strong>: {{ task.start_time.strftime('%Y-%m-%d %H:%M:%S') if task.start_time else 'N/A' }} - {{ task.end_time.strftime('%Y-%m-%d %H:%M:%S') if task.end_time else 'N/A' }}</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <h3>总发现数</h3>
            <h2>{{ stats.total }}</h2>
        </div>
        <div class="stat-card">
            <h3>严重程度分布</h3>
            <p class="severity-critical">严重: {{ stats.by_severity.critical }}</p>
            <p class="severity-high">高危: {{ stats.by_severity.high }}</p>
            <p class="severity-medium">中危: {{ stats.by_severity.medium }}</p>
            <p class="severity-low">低危: {{ stats.by_severity.low }}</p>
            <p class="severity-info">信息: {{ stats.by_severity.info }}</p>
        </div>
    </div>
    
    <h2>扫描结果详情</h2>
    {% for result in results %}
    <div class="result-item">
        <h3 class="severity-{{ result.severity }}">{{ result.title }}</h3>
        <p><strong>严重程度</strong>: {{ result.severity }}</p>
        <p><strong>工具</strong>: {{ result.tool }}</p>
        <p><strong>URL</strong>: {{ result.url or 'N/A' }}</p>
        <p><strong>参数</strong>: {{ result.param or 'N/A' }}</p>
        <p><strong>描述</strong>: {{ result.description or 'N/A' }}</p>
        {% if result.payload %}
        <p><strong>攻击载荷</strong>:</p>
        <div class="payload">{{ result.payload }}</div>
        {% endif %}
    </div>
    {% endfor %}
    
    <hr>
    <p><em>报告生成时间: {{ now.strftime('%Y-%m-%d %H:%M:%S') }}</em></p>
</body>
</html>
        """)
        
        return template.render(
            task=task,
            target=target,
            results=results,
            stats=stats,
            now=datetime.now()
        )
    
    def _generate_json_report(self, task, target, results, stats) -> str:
        """生成JSON格式报告"""
        report_data = {
            "report_info": {
                "generated_at": datetime.now().isoformat(),
                "task_id": task.id,
                "scan_type": task.scan_type,
                "status": task.status
            },
            "target_info": {
                "id": target.id if target else None,
                "name": target.name if target else None,
                "base_url": target.base_url if target else None,
                "target_type": target.target_type if target else None,
                "environment": target.environment if target else None
            } if target else None,
            "scan_info": {
                "start_time": task.start_time.isoformat() if task.start_time else None,
                "end_time": task.end_time.isoformat() if task.end_time else None,
                "duration": task.duration,
                "progress": task.progress
            },
            "statistics": stats,
            "results": [
                {
                    "id": result.id,
                    "tool": result.tool,
                    "severity": result.severity,
                    "title": result.title,
                    "description": result.description,
                    "url": result.url,
                    "param": result.param,
                    "payload": result.payload,
                    "created_at": result.created_at.isoformat()
                }
                for result in results
            ]
        }
        
        return json.dumps(report_data, ensure_ascii=False, indent=2)
    
    def _generate_target_markdown_report(self, target, tasks, vulnerabilities, stats) -> str:
        """生成目标综合报告（Markdown）"""
        template = Template("""
# {{ target.name }} 安全评估报告

## 目标信息

- **目标名称**: {{ target.name }}
- **目标URL**: {{ target.base_url }}
- **目标类型**: {{ target.target_type }}
- **环境**: {{ target.environment }}
- **描述**: {{ target.description or 'N/A' }}

## 扫描历史

总共执行了 {{ tasks|length }} 次扫描：

{% for task in tasks %}
- **{{ task.created_at.strftime('%Y-%m-%d %H:%M') }}**: {{ task.scan_type }} ({{ task.status }})
{% endfor %}

## 漏洞统计

- **总漏洞数**: {{ stats.total }}
- **严重**: {{ stats.by_severity.critical }}
- **高危**: {{ stats.by_severity.high }}
- **中危**: {{ stats.by_severity.medium }}
- **低危**: {{ stats.by_severity.low }}
- **信息**: {{ stats.by_severity.info }}

## 漏洞状态

- **未修复**: {{ stats.by_status.open }}
- **已修复**: {{ stats.by_status.fixed }}
- **误报**: {{ stats.by_status.false_positive }}
- **已接受**: {{ stats.by_status.accepted }}

## 漏洞详情

{% for vuln in vulnerabilities %}
### {{ loop.index }}. {{ vuln.title }}

- **严重程度**: {{ vuln.severity }}
- **漏洞类型**: {{ vuln.vuln_type or 'N/A' }}
- **状态**: {{ vuln.status }}
- **风险评分**: {{ vuln.risk_score or 'N/A' }}
- **首次发现**: {{ vuln.first_found.strftime('%Y-%m-%d %H:%M:%S') }}
- **最后发现**: {{ vuln.last_seen.strftime('%Y-%m-%d %H:%M:%S') }}

**描述**: {{ vuln.description or 'N/A' }}

**修复建议**: {{ vuln.fix_suggestion or 'N/A' }}

---
{% endfor %}

## 安全建议

### 立即处理
{% for vuln in vulnerabilities if vuln.severity in ['critical', 'high'] and vuln.status == 'open' %}
- {{ vuln.title }}
{% endfor %}

### 计划修复
{% for vuln in vulnerabilities if vuln.severity == 'medium' and vuln.status == 'open' %}
- {{ vuln.title }}
{% endfor %}

---
*报告生成时间: {{ now.strftime('%Y-%m-%d %H:%M:%S') }}*
        """)
        
        return template.render(
            target=target,
            tasks=tasks,
            vulnerabilities=vulnerabilities,
            stats=stats,
            now=datetime.now()
        )
    
    def _generate_target_html_report(self, target, tasks, vulnerabilities, stats) -> str:
        """生成目标综合报告（HTML）"""
        # 类似HTML报告的实现
        pass
    
    def create_bug_reports(self, task_id: int) -> List[int]:
        """为严重和高危漏洞创建Bug报告"""
        results = self.db.query(SecurityScanResult).filter(
            SecurityScanResult.task_id == task_id,
            SecurityScanResult.severity.in_(["critical", "high"])
        ).all()
        
        bug_ids = []
        
        for result in results:
            # 检查是否已存在相同Bug
            existing_bug = self.db.query(BugReport).filter(
                BugReport.bug_name == result.title,
                BugReport.location_url == result.url
            ).first()
            
            if not existing_bug:
                bug = BugReport(
                    bug_name=result.title,
                    location_url=result.url or "",
                    error_type="安全漏洞",
                    severity_level=result.severity,
                    reproduce_steps=f"使用{result.tool}工具扫描发现",
                    description=result.description or "",
                    expected_result="无安全漏洞",
                    actual_result=f"发现{result.severity}级别安全漏洞",
                    case_type="安全测试",
                    execution_mode="自动扫描"
                )
                self.db.add(bug)
                self.db.commit()
                self.db.refresh(bug)
                bug_ids.append(bug.id)
        
        return bug_ids