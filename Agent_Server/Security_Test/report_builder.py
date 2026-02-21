"""
安全测试报告构建器

整合漏洞列表、风险评分、修复建议，生成 Markdown 报告
严重漏洞自动创建 Bug 单并邮件通知

作者: Ai_Test_Agent Team
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def build_markdown_report(scan_type: str, target: str, vulnerabilities: List[dict],
                          risk_result: dict, duration: int = 0) -> str:
    """
    生成 Markdown 格式的安全测试报告

    Args:
        scan_type: 扫描类型
        target: 扫描目标
        vulnerabilities: 统一格式漏洞列表
        risk_result: 风险评分结果
        duration: 扫描耗时(秒)
    """
    summary = risk_result.get("summary", {})
    score = risk_result.get("score", 0)
    level = risk_result.get("level", "N/A")

    type_labels = {
        "web_scan": "Web 安全扫描",
        "api_attack": "API 攻击测试",
        "dependency_scan": "依赖安全扫描",
        "baseline_check": "安全基线检测",
    }

    lines = [
        f"# 🔒 安全测试报告 - {type_labels.get(scan_type, scan_type)}",
        "",
        f"**扫描目标**: {target}",
        f"**扫描时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**扫描耗时**: {duration} 秒",
        "",
        "## 📊 风险评估",
        "",
        f"| 指标 | 值 |",
        f"|------|------|",
        f"| 安全评分 | **{score}** / 100 |",
        f"| 风险等级 | **{level}** |",
        f"| 漏洞总数 | {summary.get('total', 0)} |",
        f"| 严重 (Critical) | {summary.get('critical', 0)} |",
        f"| 高危 (High) | {summary.get('high', 0)} |",
        f"| 中危 (Medium) | {summary.get('medium', 0)} |",
        f"| 低危 (Low) | {summary.get('low', 0)} |",
        f"| 信息 (Info) | {summary.get('info', 0)} |",
        "",
    ]

    if not vulnerabilities:
        lines.append("## ✅ 未发现安全漏洞")
        lines.append("")
        lines.append("本次扫描未检测到安全问题，请继续保持良好的安全实践。")
    else:
        lines.append("## 🐛 漏洞详情")
        lines.append("")

        # 按严重级别排序
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        sorted_vulns = sorted(vulnerabilities, key=lambda v: severity_order.get(v.get("severity", "info"), 5))

        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}

        for i, vuln in enumerate(sorted_vulns, 1):
            sev = vuln.get("severity", "info")
            emoji = severity_emoji.get(sev, "⚪")
            lines.append(f"### {emoji} {i}. {vuln.get('vuln_type', 'Unknown')}")
            lines.append("")
            lines.append(f"- **严重级别**: {sev.upper()}")
            lines.append(f"- **来源**: {vuln.get('source', 'N/A')}")
            if vuln.get("url"):
                lines.append(f"- **URL**: `{vuln['url']}`")
            if vuln.get("param"):
                lines.append(f"- **参数**: `{vuln['param']}`")
            if vuln.get("cve"):
                lines.append(f"- **CVE**: {vuln['cve']}")
            if vuln.get("description"):
                lines.append(f"- **描述**: {vuln['description'][:500]}")
            if vuln.get("solution"):
                lines.append(f"- **修复建议**: {vuln['solution']}")
            if vuln.get("evidence"):
                lines.append(f"- **证据**: `{vuln['evidence'][:300]}`")
            lines.append("")

    lines.append("---")
    lines.append(f"*报告由 AI Test Agent 安全测试模块自动生成*")

    return "\n".join(lines)


def create_bug_reports_for_critical_vulns(vulnerabilities: List[dict], task_id: int,
                                          db: Session) -> List[int]:
    """
    为严重/高危漏洞自动创建 Bug 单

    Returns:
        创建的 bug_report IDs
    """
    from database.connection import BugReport

    bug_ids = []
    for vuln in vulnerabilities:
        severity = vuln.get("severity", "info")
        if severity not in ("critical", "high"):
            continue

        severity_map = {"critical": "一级", "high": "二级"}

        bug = BugReport(
            bug_name=f"[安全] {vuln.get('vuln_type', 'Unknown')}",
            location_url=vuln.get("url", ""),
            error_type="安全漏洞",
            severity_level=severity_map.get(severity, "二级"),
            reproduce_steps=vuln.get("description", ""),
            expected_result="不应存在该安全漏洞",
            actual_result=vuln.get("evidence", vuln.get("description", "")),
            description=f"来源: {vuln.get('source', 'N/A')}\n修复建议: {vuln.get('solution', '')}",
            status="待处理",
            case_type="安全测试",
            execution_mode="安全扫描",
        )
        db.add(bug)
        db.flush()
        bug_ids.append(bug.id)

    if bug_ids:
        db.commit()
        logger.info(f"[Security] 已创建 {len(bug_ids)} 个安全 Bug 单")

    return bug_ids


def send_security_email_notification(vulnerabilities: List[dict], risk_result: dict,
                                     target: str, db: Session):
    """为严重漏洞发送邮件通知"""
    critical_count = risk_result.get("summary", {}).get("critical", 0)
    high_count = risk_result.get("summary", {}).get("high", 0)

    if critical_count == 0 and high_count == 0:
        return

    try:
        from database.connection import Contact, EmailConfig
        from Email_manage.router import _send_email_via_config

        contacts = db.query(Contact).filter(Contact.auto_receive_bug == 1).all()
        if not contacts:
            return

        config = db.query(EmailConfig).filter(EmailConfig.is_active == 1).first()
        if not config:
            return

        score = risk_result.get("score", 0)
        level = risk_result.get("level", "N/A")

        subject = f"[安全告警] {target} 发现 {critical_count} 个严重 / {high_count} 个高危漏洞"

        html = f"""
        <h2>🔒 安全扫描告警</h2>
        <p><b>扫描目标</b>: {target}</p>
        <p><b>安全评分</b>: {score}/100 (等级: {level})</p>
        <p><b>严重漏洞</b>: {critical_count} 个</p>
        <p><b>高危漏洞</b>: {high_count} 个</p>
        <hr/>
        <h3>严重/高危漏洞列表:</h3>
        <ul>
        """
        for vuln in vulnerabilities:
            if vuln.get("severity") in ("critical", "high"):
                html += f"<li><b>[{vuln['severity'].upper()}]</b> {vuln.get('vuln_type', '')} - {vuln.get('url', '')}</li>"
        html += "</ul><p>请尽快处理。</p>"

        for contact in contacts:
            try:
                _send_email_via_config(config, contact.email, subject, html)
            except Exception as e:
                logger.warning(f"发送安全告警邮件失败 ({contact.email}): {e}")

    except Exception as e:
        logger.warning(f"安全邮件通知失败: {e}")
