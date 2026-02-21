"""
风险评分系统

根据漏洞严重程度计算风险评分和等级

作者: Ai_Test_Agent Team
"""

# 各严重级别的权重
SEVERITY_WEIGHTS = {
    "critical": 20,
    "high": 10,
    "medium": 5,
    "low": 1,
    "info": 0,
}


def calculate_risk_score(vulnerabilities: list) -> dict:
    """
    计算风险评分

    Args:
        vulnerabilities: 统一格式的漏洞列表

    Returns:
        {
            "score": 0-100,
            "level": "A/B/C/D",
            "summary": { "critical": n, "high": n, "medium": n, "low": n, "info": n, "total": n }
        }
    """
    summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "total": 0}

    for vuln in vulnerabilities:
        severity = vuln.get("severity", "info").lower()
        if severity in summary:
            summary[severity] += 1
        summary["total"] += 1

    total_penalty = sum(
        summary[sev] * weight for sev, weight in SEVERITY_WEIGHTS.items()
    )

    score = max(0, 100 - total_penalty)

    if score >= 90:
        level = "A"
    elif score >= 75:
        level = "B"
    elif score >= 60:
        level = "C"
    else:
        level = "D"

    return {"score": score, "level": level, "summary": summary}
