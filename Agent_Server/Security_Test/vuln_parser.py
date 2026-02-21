"""
漏洞解析层 - 统一格式

将不同来源（ZAP / sqlmap / Safety / Bandit / npm audit / Trivy / LLM）的漏洞
统一转换为标准格式

作者: Ai_Test_Agent Team
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ZAP 风险级别映射
ZAP_RISK_MAP = {
    "0": "info",
    "1": "low",
    "2": "medium",
    "3": "high",
}


def normalize_vuln(source: str, vuln_type: str, severity: str, url: str = "",
                   param: str = "", description: str = "", solution: str = "",
                   evidence: str = "", cve: str = "", extra: dict = None) -> dict:
    """构造统一漏洞结构"""
    return {
        "source": source,
        "vuln_type": vuln_type,
        "severity": severity.lower(),
        "url": url,
        "param": param,
        "description": description,
        "solution": solution,
        "evidence": evidence,
        "cve": cve,
        "extra": extra or {},
    }


def parse_zap_alerts(alerts: list) -> List[dict]:
    """解析 ZAP 扫描结果"""
    vulns = []
    for alert in alerts:
        severity = ZAP_RISK_MAP.get(str(alert.get("risk", "0")), "info")
        vulns.append(normalize_vuln(
            source="zap",
            vuln_type=alert.get("name", alert.get("alert", "Unknown")),
            severity=severity,
            url=alert.get("url", ""),
            param=alert.get("param", ""),
            description=alert.get("description", ""),
            solution=alert.get("solution", ""),
            evidence=alert.get("evidence", ""),
            cve=alert.get("cweid", ""),
        ))
    return vulns


def parse_sqlmap_output(output: str, target_url: str) -> List[dict]:
    """解析 sqlmap 输出"""
    vulns = []
    if "injectable" in output.lower() or "parameter" in output.lower():
        # 提取注入类型
        inject_types = []
        for line in output.split("\n"):
            line_lower = line.strip().lower()
            if "type:" in line_lower and ("blind" in line_lower or "union" in line_lower
                                          or "error" in line_lower or "time" in line_lower
                                          or "stacked" in line_lower):
                inject_types.append(line.strip())

        vulns.append(normalize_vuln(
            source="sqlmap",
            vuln_type="SQL Injection (Verified)",
            severity="critical",
            url=target_url,
            description=f"sqlmap 确认存在 SQL 注入漏洞。\n检测到的注入类型:\n" + "\n".join(inject_types[:5]),
            solution="使用参数化查询/预编译语句，避免拼接 SQL",
            evidence=output[:2000],
        ))
    return vulns


def parse_safety_output(output: str) -> List[dict]:
    """解析 Safety 依赖扫描输出"""
    vulns = []
    # Safety JSON 格式或文本格式
    try:
        import json
        data = json.loads(output)
        for item in (data if isinstance(data, list) else data.get("vulnerabilities", [])):
            vulns.append(normalize_vuln(
                source="safety",
                vuln_type="Vulnerable Dependency",
                severity=_map_safety_severity(item),
                description=item.get("advisory", item.get("vulnerability_id", "")),
                solution=f"升级 {item.get('package_name', '')} 到安全版本",
                cve=item.get("cve", item.get("vulnerability_id", "")),
                extra={"package": item.get("package_name", ""), "version": item.get("analyzed_version", "")},
            ))
    except Exception:
        # 文本格式 fallback
        for line in output.split("\n"):
            if "vulnerability" in line.lower() or "CVE" in line:
                vulns.append(normalize_vuln(
                    source="safety",
                    vuln_type="Vulnerable Dependency",
                    severity="medium",
                    description=line.strip(),
                    solution="请检查并升级相关依赖",
                ))
    return vulns


def parse_bandit_output(output: str) -> List[dict]:
    """解析 Bandit 代码安全扫描输出"""
    vulns = []
    try:
        import json
        data = json.loads(output)
        for result in data.get("results", []):
            severity = result.get("issue_severity", "MEDIUM").lower()
            vulns.append(normalize_vuln(
                source="bandit",
                vuln_type=result.get("test_name", "Code Security Issue"),
                severity=severity,
                url=result.get("filename", ""),
                description=result.get("issue_text", ""),
                solution=f"参考 Bandit {result.get('test_id', '')} 修复建议",
                extra={"line": result.get("line_number", 0), "confidence": result.get("issue_confidence", "")},
            ))
    except Exception:
        logger.warning("Bandit 输出解析失败，尝试文本解析")
    return vulns


def parse_npm_audit_output(output: str) -> List[dict]:
    """解析 npm audit 输出"""
    vulns = []
    try:
        import json
        data = json.loads(output)
        advisories = data.get("advisories", data.get("vulnerabilities", {}))
        if isinstance(advisories, dict):
            for key, adv in advisories.items():
                severity = adv.get("severity", "moderate").lower()
                if severity == "moderate":
                    severity = "medium"
                vulns.append(normalize_vuln(
                    source="npm_audit",
                    vuln_type="Vulnerable Dependency",
                    severity=severity,
                    description=adv.get("title", adv.get("name", "")),
                    solution=adv.get("recommendation", adv.get("fixAvailable", "")),
                    extra={"package": adv.get("module_name", adv.get("name", "")),
                           "range": adv.get("vulnerable_versions", adv.get("range", ""))},
                ))
    except Exception:
        logger.warning("npm audit 输出解析失败")
    return vulns


def parse_trivy_output(output: str) -> List[dict]:
    """解析 Trivy 扫描输出"""
    vulns = []
    try:
        import json
        data = json.loads(output)
        for result in data.get("Results", []):
            for v in result.get("Vulnerabilities", []):
                severity = v.get("Severity", "UNKNOWN").lower()
                if severity == "unknown":
                    severity = "info"
                vulns.append(normalize_vuln(
                    source="trivy",
                    vuln_type="Container/Dependency Vulnerability",
                    severity=severity,
                    description=v.get("Title", v.get("Description", "")),
                    solution=f"升级到 {v.get('FixedVersion', '最新版本')}",
                    cve=v.get("VulnerabilityID", ""),
                    extra={"package": v.get("PkgName", ""), "installed": v.get("InstalledVersion", "")},
                ))
    except Exception:
        logger.warning("Trivy 输出解析失败")
    return vulns


def parse_llm_attack_results(results: list) -> List[dict]:
    """解析 LLM 生成的 API 攻击测试结果"""
    vulns = []
    for r in results:
        if r.get("is_vulnerable"):
            vulns.append(normalize_vuln(
                source="llm_api_attack",
                vuln_type=r.get("attack_type", "API Security Issue"),
                severity=r.get("severity", "medium"),
                url=r.get("url", ""),
                param=r.get("param", ""),
                description=r.get("description", ""),
                solution=r.get("solution", ""),
                evidence=r.get("evidence", ""),
            ))
    return vulns


def _map_safety_severity(item: dict) -> str:
    """映射 Safety 的严重级别"""
    # Safety v3 有 severity 字段
    sev = item.get("severity", "").lower()
    if sev in ("critical", "high", "medium", "low"):
        return sev
    # 根据 CVSS 分数推断
    cvss = item.get("cvss_score", 0)
    if cvss >= 9:
        return "critical"
    elif cvss >= 7:
        return "high"
    elif cvss >= 4:
        return "medium"
    return "low"
