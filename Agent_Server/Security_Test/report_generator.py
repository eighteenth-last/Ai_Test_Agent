"""
安全测试报告生成器

基于工业级方案设计的报告生成系统

支持格式:
- HTML: 网页格式报告
- Markdown: Markdown 格式报告
- JSON: 结构化数据报告

支持 LLM 增强的智能报告生成

作者: 程序员Eighteen
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from database.connection import (
    SecurityTarget, SecurityScanTask, SecurityScanResult,
    SecurityVulnerability, SecurityScanLog, BugReport
)
from Security_Test.risk_scoring import RiskScoringEngine

# 导入 LLM 相关
from llm.client import LLMClient
from Api_request.prompts import (
    SECURITY_REPORT_LLM_ENHANCEMENT_SYSTEM,
    SECURITY_REPORT_LLM_ENHANCEMENT_USER_TEMPLATE,
    VULNERABILITY_ANALYSIS_SYSTEM,
    VULNERABILITY_ANALYSIS_USER_TEMPLATE,
    VULNERABILITY_FIX_SYSTEM,
    VULNERABILITY_FIX_USER_TEMPLATE,
    SECURITY_EXECUTIVE_SUMMARY_SYSTEM,
    SECURITY_EXECUTIVE_SUMMARY_USER_TEMPLATE,
    ATTACK_SURFACE_ANALYSIS_SYSTEM,
    ATTACK_SURFACE_ANALYSIS_USER_TEMPLATE
)

logger = logging.getLogger(__name__)


class SecurityReportGenerator:
    """安全测试报告生成器（支持 LLM 增强）"""
    
    def __init__(self, db: Session, enable_llm: bool = True):
        """
        初始化报告生成器
        
        Args:
            db: 数据库会话
            enable_llm: 是否启用 LLM 增强（默认启用）
        """
        self.db = db
        self.enable_llm = enable_llm
        
        # 初始化 LLM 客户端
        if enable_llm:
            try:
                self.llm_client = LLMClient()
                logger.info("[SecurityReportGenerator] LLM 增强已启用")
            except Exception as e:
                logger.warning(f"[SecurityReportGenerator] LLM 初始化失败，将使用基础报告: {e}")
                self.enable_llm = False
                self.llm_client = None
        else:
            self.llm_client = None
    
    def generate_task_report(self, task_id: int, format_type: str = "markdown") -> str:
        """
        生成单个任务的扫描报告（支持 LLM 增强）
        
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
        
        # 如果启用 LLM，生成增强报告
        llm_insights = None
        if self.enable_llm and self.llm_client and results:
            try:
                llm_insights = self._generate_llm_insights(task, target, results, stats)
                logger.info("[SecurityReportGenerator] LLM 分析完成")
            except Exception as e:
                logger.warning(f"[SecurityReportGenerator] LLM 分析失败: {e}")
        
        # 生成报告
        if format_type == "markdown":
            return self._generate_markdown_report(task, target, results, stats, llm_insights)
        elif format_type == "html":
            return self._generate_html_report(task, target, results, stats, llm_insights)
        elif format_type == "json":
            return self._generate_json_report(task, target, results, stats, llm_insights)
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
    
    
    def _generate_llm_insights(
        self,
        task: SecurityScanTask,
        target: SecurityTarget,
        results: List[SecurityScanResult],
        stats: Dict
    ) -> Dict:
        """
        使用 LLM 生成智能分析和建议
        
        Args:
            task: 扫描任务
            target: 扫描目标
            results: 扫描结果
            stats: 统计信息
            
        Returns:
            LLM 分析结果
        """
        # 构建漏洞详情文本
        vulnerabilities_detail = ""
        for i, result in enumerate(results[:20], 1):  # 限制前20个漏洞
            vulnerabilities_detail += f"""
### 漏洞 {i}: {result.title}
- 严重程度: {result.severity}
- 工具: {result.tool}
- URL: {result.url or 'N/A'}
- 参数: {result.param or 'N/A'}
- 描述: {result.description or '无描述'}
- Payload: {result.payload or 'N/A'}

"""
        
        # 准备 LLM 提示词参数
        prompt_params = {
            "target_name": target.name if target else "未知目标",
            "target_url": target.base_url if target else "N/A",
            "scan_type": task.scan_type,
            "environment": target.environment if target else "N/A",
            "total_vulns": stats["total"],
            "critical_count": stats["by_severity"]["critical"],
            "high_count": stats["by_severity"]["high"],
            "medium_count": stats["by_severity"]["medium"],
            "low_count": stats["by_severity"]["low"],
            "vulnerabilities_detail": vulnerabilities_detail,
            "risk_score": "N/A",  # 将在后续计算
            "risk_grade": "N/A"
        }
        
        # 调用 LLM 生成分析
        user_prompt = SECURITY_REPORT_LLM_ENHANCEMENT_USER_TEMPLATE.format(**prompt_params)
        
        try:
            response = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": SECURITY_REPORT_LLM_ENHANCEMENT_SYSTEM},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format="json"
            )
            
            # 解析 JSON 响应
            insights = json.loads(response)
            return insights
            
        except Exception as e:
            logger.error(f"[SecurityReportGenerator] LLM 分析失败: {e}")
            return {
                "executive_summary": "LLM 分析暂时不可用",
                "risk_analysis": {},
                "vulnerability_insights": [],
                "remediation_plan": {},
                "security_recommendations": []
            }
    
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
    
    def _generate_markdown_report(self, task, target, results, stats, llm_insights=None) -> str:
        """生成Markdown格式报告（支持 LLM 增强）"""
        
        # 基础报告内容
        md = f"""# 🛡️ 安全扫描报告

## 基本信息

- **目标名称**: {target.name if target else 'N/A'}
- **目标URL**: {target.base_url if target else 'N/A'}
- **扫描类型**: {task.scan_type}
- **扫描状态**: {task.status}
- **开始时间**: {task.start_time.strftime('%Y-%m-%d %H:%M:%S') if task.start_time else 'N/A'}
- **结束时间**: {task.end_time.strftime('%Y-%m-%d %H:%M:%S') if task.end_time else 'N/A'}
- **扫描耗时**: {task.duration}秒

## 扫描统计

- **总发现数**: {stats['total']}
- **严重**: {stats['by_severity']['critical']}
- **高危**: {stats['by_severity']['high']}
- **中危**: {stats['by_severity']['medium']}
- **低危**: {stats['by_severity']['low']}
- **信息**: {stats['by_severity']['info']}

## 工具统计

"""
        
        for tool, count in stats['by_tool'].items():
            md += f"- **{tool}**: {count}\n"
        
        # 如果有 LLM 分析，添加执行摘要
        if llm_insights:
            md += f"""

---

## 🤖 AI 智能分析

### 执行摘要

{llm_insights.get('executive_summary', '暂无分析')}

### 风险分析

"""
            risk_analysis = llm_insights.get('risk_analysis', {})
            if risk_analysis:
                md += f"""- **整体风险**: {risk_analysis.get('overall_risk', 'N/A')}
- **业务影响**: {risk_analysis.get('business_impact', 'N/A')}
- **攻击面**: {risk_analysis.get('attack_surface', 'N/A')}
- **可利用性**: {risk_analysis.get('exploitability', 'N/A')}

"""
            
            # 漏洞洞察
            vuln_insights = llm_insights.get('vulnerability_insights', [])
            if vuln_insights:
                md += "### 关键漏洞洞察\n\n"
                for insight in vuln_insights[:5]:  # 显示前5个
                    md += f"""#### {insight.get('vuln_title', '未知漏洞')}

- **深入分析**: {insight.get('insight', 'N/A')}
- **业务风险**: {insight.get('business_risk', 'N/A')}
- **攻击场景**: {insight.get('attack_scenario', 'N/A')}

"""
            
            # 修复计划
            remediation = llm_insights.get('remediation_plan', {})
            if remediation:
                md += "### 修复计划\n\n"
                
                immediate = remediation.get('immediate_actions', [])
                if immediate:
                    md += "**立即行动**:\n"
                    for action in immediate:
                        md += f"- {action}\n"
                    md += "\n"
                
                short_term = remediation.get('short_term', [])
                if short_term:
                    md += "**短期计划**:\n"
                    for action in short_term:
                        md += f"- {action}\n"
                    md += "\n"
                
                long_term = remediation.get('long_term', [])
                if long_term:
                    md += "**长期改进**:\n"
                    for action in long_term:
                        md += f"- {action}\n"
                    md += "\n"
            
            # 安全建议
            recommendations = llm_insights.get('security_recommendations', [])
            if recommendations:
                md += "### 安全建议\n\n"
                for rec in recommendations:
                    category = rec.get('category', '通用')
                    recommendation = rec.get('recommendation', '')
                    priority = rec.get('priority', 'medium')
                    md += f"- **[{priority.upper()}] {category}**: {recommendation}\n"
                md += "\n"
        
        md += """

---

## 🔍 扫描结果详情

"""
        
        # 漏洞详情
        for i, result in enumerate(results, 1):
            md += f"""### {i}. {result.title}

- **严重程度**: {result.severity}
- **工具**: {result.tool}
- **URL**: {result.url or 'N/A'}
- **参数**: {result.param or 'N/A'}
- **描述**: {result.description or 'N/A'}

"""
            if result.payload:
                md += f"""**攻击载荷**:
```
{result.payload}
```

"""
            md += "---\n\n"
        
        # 修复建议（基础版本）
        if not llm_insights:
            md += """## 💡 修复建议

根据扫描结果，建议采取以下修复措施：

"""
            if stats['by_severity']['critical'] > 0:
                md += """### 严重漏洞修复
- 立即修复所有严重漏洞
- 暂停相关功能直到修复完成

"""
            
            if stats['by_severity']['high'] > 0:
                md += """### 高危漏洞修复
- 在24小时内修复高危漏洞
- 加强输入验证和输出编码

"""
            
            if stats['by_severity']['medium'] > 0:
                md += """### 中危漏洞修复
- 在一周内修复中危漏洞
- 完善安全配置

"""
        
        md += f"""

---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*御策天检 - 智能自动化测试平台*
"""
        
        return md
    
    def _generate_html_report(self, task, target, results, stats, llm_insights=None) -> str:
        """生成HTML格式报告（支持 LLM 增强）"""
        
        # LLM 分析部分的 HTML
        llm_section = ""
        if llm_insights:
            llm_section = f"""
    <div class="section llm-insights">
        <h2>🤖 AI 智能分析</h2>
        
        <div class="executive-summary">
            <h3>执行摘要</h3>
            <p>{llm_insights.get('executive_summary', '暂无分析')}</p>
        </div>
"""
            
            risk_analysis = llm_insights.get('risk_analysis', {})
            if risk_analysis:
                llm_section += f"""
        <div class="risk-analysis">
            <h3>风险分析</h3>
            <ul>
                <li><strong>整体风险</strong>: {risk_analysis.get('overall_risk', 'N/A')}</li>
                <li><strong>业务影响</strong>: {risk_analysis.get('business_impact', 'N/A')}</li>
                <li><strong>攻击面</strong>: {risk_analysis.get('attack_surface', 'N/A')}</li>
                <li><strong>可利用性</strong>: {risk_analysis.get('exploitability', 'N/A')}</li>
            </ul>
        </div>
"""
            
            vuln_insights = llm_insights.get('vulnerability_insights', [])
            if vuln_insights:
                llm_section += """
        <div class="vuln-insights">
            <h3>关键漏洞洞察</h3>
"""
                for insight in vuln_insights[:5]:
                    llm_section += f"""
            <div class="insight-card">
                <h4>{insight.get('vuln_title', '未知漏洞')}</h4>
                <p><strong>深入分析</strong>: {insight.get('insight', 'N/A')}</p>
                <p><strong>业务风险</strong>: {insight.get('business_risk', 'N/A')}</p>
                <p><strong>攻击场景</strong>: {insight.get('attack_scenario', 'N/A')}</p>
            </div>
"""
                llm_section += """
        </div>
"""
            
            remediation = llm_insights.get('remediation_plan', {})
            if remediation:
                llm_section += """
        <div class="remediation-plan">
            <h3>修复计划</h3>
"""
                immediate = remediation.get('immediate_actions', [])
                if immediate:
                    llm_section += """
            <div class="plan-section">
                <h4>立即行动</h4>
                <ul>
"""
                    for action in immediate:
                        llm_section += f"                    <li>{action}</li>\n"
                    llm_section += """
                </ul>
            </div>
"""
                
                short_term = remediation.get('short_term', [])
                if short_term:
                    llm_section += """
            <div class="plan-section">
                <h4>短期计划</h4>
                <ul>
"""
                    for action in short_term:
                        llm_section += f"                    <li>{action}</li>\n"
                    llm_section += """
                </ul>
            </div>
"""
                
                long_term = remediation.get('long_term', [])
                if long_term:
                    llm_section += """
            <div class="plan-section">
                <h4>长期改进</h4>
                <ul>
"""
                    for action in long_term:
                        llm_section += f"                    <li>{action}</li>\n"
                    llm_section += """
                </ul>
            </div>
"""
                llm_section += """
        </div>
"""
            
            recommendations = llm_insights.get('security_recommendations', [])
            if recommendations:
                llm_section += """
        <div class="security-recommendations">
            <h3>安全建议</h3>
            <ul>
"""
                for rec in recommendations:
                    category = rec.get('category', '通用')
                    recommendation = rec.get('recommendation', '')
                    priority = rec.get('priority', 'medium')
                    llm_section += f"""                <li><span class="badge {priority}">{priority.upper()}</span> <strong>{category}</strong>: {recommendation}</li>\n"""
                llm_section += """
            </ul>
        </div>
"""
            
            llm_section += """
    </div>
"""
        
        # 构建完整的 HTML
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>安全扫描报告 - Task #{task.id}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
        }}
        .section {{
            background: white;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            margin-top: 0;
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .llm-insights {{
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-left: 5px solid #667eea;
        }}
        .executive-summary {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }}
        .insight-card {{
            background: white;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            border-left: 3px solid #667eea;
        }}
        .plan-section {{
            margin: 15px 0;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-card.critical {{ background-color: #dc3545; color: white; }}
        .stat-card.high {{ background-color: #fd7e14; color: white; }}
        .stat-card.medium {{ background-color: #ffc107; color: #333; }}
        .stat-card.low {{ background-color: #17a2b8; color: white; }}
        .stat-card .number {{
            font-size: 36px;
            font-weight: bold;
        }}
        .stat-card .label {{
            font-size: 14px;
            margin-top: 5px;
        }}
        .vuln-item {{
            border-left: 4px solid #ddd;
            padding: 15px;
            margin: 10px 0;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        .vuln-item.critical {{ border-left-color: #dc3545; }}
        .vuln-item.high {{ border-left-color: #fd7e14; }}
        .vuln-item.medium {{ border-left-color: #ffc107; }}
        .vuln-item.low {{ border-left-color: #17a2b8; }}
        .vuln-title {{
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 8px;
        }}
        .vuln-meta {{
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            color: white;
            margin-right: 5px;
        }}
        .badge.critical {{ background-color: #dc3545; }}
        .badge.high {{ background-color: #fd7e14; }}
        .badge.medium {{ background-color: #ffc107; color: #333; }}
        .badge.low {{ background-color: #17a2b8; }}
        .badge.info {{ background-color: #6c757d; }}
        .footer {{
            text-align: center;
            color: #666;
            margin-top: 30px;
            padding: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ 安全扫描报告</h1>
        <p>任务 ID: #{task.id} | 扫描类型: {task.scan_type} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="section">
        <h2>📊 扫描统计</h2>
        <div class="stats">
            <div class="stat-card critical">
                <div class="number">{stats['by_severity']['critical']}</div>
                <div class="label">严重漏洞</div>
            </div>
            <div class="stat-card high">
                <div class="number">{stats['by_severity']['high']}</div>
                <div class="label">高危漏洞</div>
            </div>
            <div class="stat-card medium">
                <div class="number">{stats['by_severity']['medium']}</div>
                <div class="label">中危漏洞</div>
            </div>
            <div class="stat-card low">
                <div class="number">{stats['by_severity']['low']}</div>
                <div class="label">低危漏洞</div>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>🎯 扫描目标</h2>
        <p><strong>名称:</strong> {target.name if target else 'N/A'}</p>
        <p><strong>URL:</strong> {target.base_url if target else 'N/A'}</p>
        <p><strong>环境:</strong> {target.environment if target else 'N/A'}</p>
    </div>
    
    <div class="section">
        <h2>⏱️ 扫描信息</h2>
        <p><strong>开始时间:</strong> {task.start_time.strftime('%Y-%m-%d %H:%M:%S') if task.start_time else 'N/A'}</p>
        <p><strong>结束时间:</strong> {task.end_time.strftime('%Y-%m-%d %H:%M:%S') if task.end_time else 'N/A'}</p>
        <p><strong>耗时:</strong> {task.duration} 秒</p>
        <p><strong>状态:</strong> {task.status}</p>
    </div>
    
    {llm_section}
    
    <div class="section">
        <h2>🔍 漏洞详情</h2>
"""
        
        if results:
            for result in results:
                severity = result.severity
                html += f"""
        <div class="vuln-item {severity}">
            <div class="vuln-title">
                <span class="badge {severity}">{severity.upper()}</span>
                {result.title}
            </div>
            <div class="vuln-meta">
                <strong>URL:</strong> {result.url or 'N/A'}<br>
                <strong>参数:</strong> {result.param or 'N/A'}
            </div>
            <div class="vuln-description">
                {result.description or '无描述'}
            </div>
        </div>
"""
        else:
            html += "        <p>未发现漏洞</p>\n"
        
        html += """
    </div>
    
    <div class="footer">
        <p>御策天检 - 智能自动化测试平台</p>
        <p>Security Testing Platform © 2024</p>
    </div>
</body>
</html>
"""
        
        return html
    
    def _generate_json_report(self, task, target, results, stats, llm_insights=None) -> str:
        """生成JSON格式报告（支持 LLM 增强）"""
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
        
        # 添加 LLM 分析结果
        if llm_insights:
            report_data["llm_analysis"] = llm_insights
        
        return json.dumps(report_data, ensure_ascii=False, indent=2)
    
    def _generate_target_markdown_report(self, target, tasks, vulnerabilities, stats, llm_insights=None) -> str:
        """生成目标综合报告（Markdown，支持 LLM 增强）"""
        
        md = f"""# {target.name} 安全评估报告

## 目标信息

- **目标名称**: {target.name}
- **目标URL**: {target.base_url}
- **目标类型**: {target.target_type}
- **环境**: {target.environment}
- **描述**: {target.description or 'N/A'}

## 扫描历史

总共执行了 {len(tasks)} 次扫描：

"""
        
        for task in tasks:
            md += f"- **{task.created_at.strftime('%Y-%m-%d %H:%M')}**: {task.scan_type} ({task.status})\n"
        
        md += f"""

## 漏洞统计

- **总漏洞数**: {stats['total']}
- **严重**: {stats['by_severity']['critical']}
- **高危**: {stats['by_severity']['high']}
- **中危**: {stats['by_severity']['medium']}
- **低危**: {stats['by_severity']['low']}
- **信息**: {stats['by_severity']['info']}

## 漏洞状态

- **未修复**: {stats['by_status']['open']}
- **已修复**: {stats['by_status']['fixed']}
- **误报**: {stats['by_status']['false_positive']}
- **已接受**: {stats['by_status']['accepted']}

"""
        
        # 如果有 LLM 分析，添加智能分析部分
        if llm_insights:
            md += """

---

## 🤖 AI 智能分析

"""
            if 'executive_summary' in llm_insights:
                md += f"""### 执行摘要

{llm_insights['executive_summary']}

"""
            
            if 'attack_surface' in llm_insights:
                md += """### 攻击面分析

"""
                attack_surface = llm_insights['attack_surface']
                md += f"{attack_surface.get('attack_surface_summary', 'N/A')}\n\n"
            
            if 'security_recommendations' in llm_insights:
                md += """### 安全建议

"""
                for rec in llm_insights['security_recommendations']:
                    md += f"- **{rec.get('category', '通用')}**: {rec.get('recommendation', '')}\n"
                md += "\n"
        
        md += """

---

## 漏洞详情

"""
        
        for i, vuln in enumerate(vulnerabilities, 1):
            md += f"""### {i}. {vuln.title}

- **严重程度**: {vuln.severity}
- **漏洞类型**: {vuln.vuln_type or 'N/A'}
- **状态**: {vuln.status}
- **风险评分**: {vuln.risk_score or 'N/A'}
- **首次发现**: {vuln.first_found.strftime('%Y-%m-%d %H:%M:%S')}
- **最后发现**: {vuln.last_seen.strftime('%Y-%m-%d %H:%M:%S')}

**描述**: {vuln.description or 'N/A'}

**修复建议**: {vuln.fix_suggestion or 'N/A'}

---

"""
        
        md += """

## 安全建议

### 立即处理

"""
        
        critical_high_open = [v for v in vulnerabilities if v.severity in ['critical', 'high'] and v.status == 'open']
        if critical_high_open:
            for vuln in critical_high_open:
                md += f"- {vuln.title}\n"
        else:
            md += "无\n"
        
        md += """

### 计划修复

"""
        
        medium_open = [v for v in vulnerabilities if v.severity == 'medium' and v.status == 'open']
        if medium_open:
            for vuln in medium_open:
                md += f"- {vuln.title}\n"
        else:
            md += "无\n"
        
        md += f"""

---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*御策天检 - 智能自动化测试平台*
"""
        
        return md
    
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



class ReportGenerator:
    """安全测试报告生成器"""
    
    def __init__(self):
        self.risk_engine = RiskScoringEngine()
        self.report_dir = "save_floder/security_reports"
        
        # 确保报告目录存在
        os.makedirs(self.report_dir, exist_ok=True)
    
    async def generate_task_report(
        self,
        task_id: int,
        format_type: str,
        db: Session
    ) -> Dict:
        """
        生成扫描任务报告
        
        Args:
            task_id: 任务ID
            format_type: 报告格式 (html/markdown/json)
            db: 数据库会话
            
        Returns:
            报告信息
        """
        # 获取任务信息
        task = db.query(SecurityScanTask).filter(
            SecurityScanTask.id == task_id
        ).first()
        
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        # 获取目标信息
        target = db.query(SecurityTarget).filter(
            SecurityTarget.id == task.target_id
        ).first()
        
        # 获取扫描结果
        results = db.query(SecurityScanResult).filter(
            SecurityScanResult.task_id == task_id
        ).all()
        
        # 获取漏洞信息
        vulnerabilities = db.query(SecurityVulnerability).filter(
            SecurityVulnerability.target_id == task.target_id
        ).all()
        
        # 生成风险报告
        risk_report = self.risk_engine.generate_risk_report(task.target_id, db)
        
        # 构建报告数据
        report_data = {
            "task": {
                "id": task.id,
                "scan_type": task.scan_type,
                "status": task.status,
                "start_time": task.start_time.isoformat() if task.start_time else None,
                "end_time": task.end_time.isoformat() if task.end_time else None,
                "duration": task.duration
            },
            "target": {
                "id": target.id,
                "name": target.name,
                "base_url": target.base_url,
                "environment": target.environment
            },
            "results": [
                {
                    "severity": r.severity,
                    "title": r.title,
                    "description": r.description,
                    "url": r.url,
                    "param": r.param,
                    "payload": r.payload
                }
                for r in results
            ],
            "risk_report": risk_report,
            "generated_at": datetime.now().isoformat()
        }
        
        # 根据格式生成报告
        if format_type == "html":
            report_path = await self._generate_html_report(task_id, report_data)
        elif format_type == "markdown":
            report_path = await self._generate_markdown_report(task_id, report_data)
        elif format_type == "json":
            report_path = await self._generate_json_report(task_id, report_data)
        else:
            raise ValueError(f"不支持的报告格式: {format_type}")
        
        return {
            "task_id": task_id,
            "format": format_type,
            "file_path": report_path,
            "filename": os.path.basename(report_path)
        }
    
    async def _generate_html_report(
        self,
        task_id: int,
        data: Dict
    ) -> str:
        """生成 HTML 格式报告"""
        filename = f"security_report_{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join(self.report_dir, filename)
        
        html_content = self._build_html_content(data)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"[ReportGenerator] HTML 报告已生成: {filepath}")
        
        return filepath
    
    async def _generate_markdown_report(
        self,
        task_id: int,
        data: Dict
    ) -> str:
        """生成 Markdown 格式报告"""
        filename = f"security_report_{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(self.report_dir, filename)
        
        md_content = self._build_markdown_content(data)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"[ReportGenerator] Markdown 报告已生成: {filepath}")
        
        return filepath
    
    async def _generate_json_report(
        self,
        task_id: int,
        data: Dict
    ) -> str:
        """生成 JSON 格式报告"""
        filename = f"security_report_{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.report_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[ReportGenerator] JSON 报告已生成: {filepath}")
        
        return filepath
    
    def _build_html_content(self, data: Dict) -> str:
        """构建 HTML 报告内容"""
        task = data["task"]
        target = data["target"]
        results = data["results"]
        risk_report = data["risk_report"]
        risk_score = risk_report["risk_score"]
        
        # 严重程度颜色映射
        severity_colors = {
            "critical": "#dc3545",
            "high": "#fd7e14",
            "medium": "#ffc107",
            "low": "#17a2b8",
            "info": "#6c757d"
        }
        
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>安全测试报告 - Task #{task['id']}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
        }}
        .section {{
            background: white;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            margin-top: 0;
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .risk-score {{
            text-align: center;
            padding: 30px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .risk-score .grade {{
            font-size: 72px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .risk-score .score {{
            font-size: 24px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-card.critical {{ background-color: #dc3545; color: white; }}
        .stat-card.high {{ background-color: #fd7e14; color: white; }}
        .stat-card.medium {{ background-color: #ffc107; color: #333; }}
        .stat-card.low {{ background-color: #17a2b8; color: white; }}
        .stat-card .number {{
            font-size: 36px;
            font-weight: bold;
        }}
        .stat-card .label {{
            font-size: 14px;
            margin-top: 5px;
        }}
        .vuln-item {{
            border-left: 4px solid #ddd;
            padding: 15px;
            margin: 10px 0;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        .vuln-item.critical {{ border-left-color: #dc3545; }}
        .vuln-item.high {{ border-left-color: #fd7e14; }}
        .vuln-item.medium {{ border-left-color: #ffc107; }}
        .vuln-item.low {{ border-left-color: #17a2b8; }}
        .vuln-title {{
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 8px;
        }}
        .vuln-meta {{
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            color: white;
        }}
        .badge.critical {{ background-color: #dc3545; }}
        .badge.high {{ background-color: #fd7e14; }}
        .badge.medium {{ background-color: #ffc107; color: #333; }}
        .badge.low {{ background-color: #17a2b8; }}
        .badge.info {{ background-color: #6c757d; }}
        .recommendations {{
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin: 15px 0;
        }}
        .recommendations ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .footer {{
            text-align: center;
            color: #666;
            margin-top: 30px;
            padding: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ 安全测试报告</h1>
        <p>任务 ID: #{task['id']} | 扫描类型: {task['scan_type']} | 生成时间: {data['generated_at']}</p>
    </div>
    
    <div class="risk-score">
        <div class="grade">{risk_score['grade']}</div>
        <div class="score">{risk_score['total_score']} 分</div>
        <div>{risk_score['risk_level']}</div>
    </div>
    
    <div class="section">
        <h2>📊 漏洞统计</h2>
        <div class="stats">
            <div class="stat-card critical">
                <div class="number">{risk_score['severity_breakdown']['critical']}</div>
                <div class="label">严重漏洞</div>
            </div>
            <div class="stat-card high">
                <div class="number">{risk_score['severity_breakdown']['high']}</div>
                <div class="label">高危漏洞</div>
            </div>
            <div class="stat-card medium">
                <div class="number">{risk_score['severity_breakdown']['medium']}</div>
                <div class="label">中危漏洞</div>
            </div>
            <div class="stat-card low">
                <div class="number">{risk_score['severity_breakdown']['low']}</div>
                <div class="label">低危漏洞</div>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>🎯 扫描目标</h2>
        <p><strong>名称:</strong> {target['name']}</p>
        <p><strong>URL:</strong> {target['base_url']}</p>
        <p><strong>环境:</strong> {target['environment']}</p>
    </div>
    
    <div class="section">
        <h2>⏱️ 扫描信息</h2>
        <p><strong>开始时间:</strong> {task['start_time']}</p>
        <p><strong>结束时间:</strong> {task['end_time']}</p>
        <p><strong>耗时:</strong> {task['duration']} 秒</p>
        <p><strong>状态:</strong> {task['status']}</p>
    </div>
    
    <div class="section">
        <h2>💡 修复建议</h2>
        <div class="recommendations">
            <ul>
"""
        
        for rec in risk_report['recommendations']:
            html += f"                <li>{rec}</li>\n"
        
        html += """
            </ul>
        </div>
    </div>
    
    <div class="section">
        <h2>🔍 漏洞详情</h2>
"""
        
        if results:
            for result in results:
                severity = result['severity']
                html += f"""
        <div class="vuln-item {severity}">
            <div class="vuln-title">
                <span class="badge {severity}">{severity.upper()}</span>
                {result['title']}
            </div>
            <div class="vuln-meta">
                <strong>URL:</strong> {result.get('url', 'N/A')}<br>
                <strong>参数:</strong> {result.get('param', 'N/A')}
            </div>
            <div class="vuln-description">
                {result.get('description', '无描述')}
            </div>
        </div>
"""
        else:
            html += "        <p>未发现漏洞</p>\n"
        
        html += """
    </div>
    
    <div class="footer">
        <p>御策天检 - 智能自动化测试平台</p>
        <p>Security Testing Platform © 2024</p>
    </div>
</body>
</html>
"""
        
        return html
    
    def _build_markdown_content(self, data: Dict) -> str:
        """构建 Markdown 报告内容"""
        task = data["task"]
        target = data["target"]
        results = data["results"]
        risk_report = data["risk_report"]
        risk_score = risk_report["risk_score"]
        
        md = f"""# 🛡️ 安全测试报告

**任务 ID:** #{task['id']}  
**扫描类型:** {task['scan_type']}  
**生成时间:** {data['generated_at']}

---

## 📊 风险评估

**安全评级:** {risk_score['grade']} ({risk_score['total_score']}分)  
**风险级别:** {risk_score['risk_level']}  
**漏洞总数:** {risk_score['total_vulns']} 个  
**未修复漏洞:** {risk_score['open_vulns']} 个

### 漏洞分布

| 严重程度 | 数量 |
|---------|------|
| 严重 (Critical) | {risk_score['severity_breakdown']['critical']} |
| 高危 (High) | {risk_score['severity_breakdown']['high']} |
| 中危 (Medium) | {risk_score['severity_breakdown']['medium']} |
| 低危 (Low) | {risk_score['severity_breakdown']['low']} |
| 信息 (Info) | {risk_score['severity_breakdown']['info']} |

---

## 🎯 扫描目标

**名称:** {target['name']}  
**URL:** {target['base_url']}  
**环境:** {target['environment']}

---

## ⏱️ 扫描信息

**开始时间:** {task['start_time']}  
**结束时间:** {task['end_time']}  
**耗时:** {task['duration']} 秒  
**状态:** {task['status']}

---

## 💡 修复建议

"""
        
        for i, rec in enumerate(risk_report['recommendations'], 1):
            md += f"{i}. {rec}\n"
        
        md += "\n---\n\n## 🔍 漏洞详情\n\n"
        
        if results:
            for i, result in enumerate(results, 1):
                md += f"""### {i}. {result['title']}

**严重程度:** {result['severity'].upper()}  
**URL:** {result.get('url', 'N/A')}  
**参数:** {result.get('param', 'N/A')}  
**Payload:** {result.get('payload', 'N/A')}

**描述:**  
{result.get('description', '无描述')}

---

"""
        else:
            md += "未发现漏洞\n\n"
        
        md += """---

## 📝 报告说明

本报告由御策天检 - 智能自动化测试平台自动生成。

**Security Testing Platform © 2024**
"""
        
        return md
