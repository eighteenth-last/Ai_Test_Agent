"""
风险评分系统

基于工业级方案设计的风险评分算法

评分模型:
Risk Score = CVSS × Impact × Exploitability

风险等级:
- A (90-100): 优秀，风险极低
- B (70-89): 良好，风险较低
- C (50-69): 一般，存在中等风险
- D (0-49): 较差，存在高风险

作者: 程序员Eighteen
"""
import logging
from typing import Dict, List
from sqlalchemy.orm import Session
from database.connection import SecurityVulnerability

logger = logging.getLogger(__name__)


class RiskScoringEngine:
    """风险评分引擎"""
    
    # 严重程度权重
    SEVERITY_WEIGHTS = {
        "critical": 20,
        "high": 10,
        "medium": 5,
        "low": 1,
        "info": 0
    }
    
    def __init__(self):
        pass
    
    def calculate_target_risk_score(
        self,
        vulnerabilities: List[SecurityVulnerability]
    ) -> Dict:
        """
        计算目标的总体风险评分
        
        Args:
            vulnerabilities: 漏洞列表
            
        Returns:
            {
                "total_score": int,  # 总分 (0-100)
                "grade": str,  # 等级 (A/B/C/D)
                "risk_level": str,  # 风险级别
                "severity_breakdown": dict,  # 严重程度分布
                "total_vulns": int,  # 漏洞总数
                "open_vulns": int,  # 未修复漏洞数
            }
        """
        # 统计各严重程度的漏洞数量
        severity_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0
        }
        
        open_vulns = 0
        
        for vuln in vulnerabilities:
            severity = vuln.severity.lower()
            if severity in severity_counts:
                severity_counts[severity] += 1
            
            if vuln.status == "open":
                open_vulns += 1
        
        # 计算风险分数
        risk_points = sum(
            count * self.SEVERITY_WEIGHTS[severity]
            for severity, count in severity_counts.items()
        )
        
        # 转换为 0-100 分数（分数越高越安全）
        # 假设 100 分为基准，每个风险点扣分
        total_score = max(0, 100 - risk_points)
        
        # 确定等级
        grade = self._get_grade(total_score)
        risk_level = self._get_risk_level(grade)
        
        return {
            "total_score": total_score,
            "grade": grade,
            "risk_level": risk_level,
            "severity_breakdown": severity_counts,
            "total_vulns": len(vulnerabilities),
            "open_vulns": open_vulns,
            "risk_points": risk_points
        }
    
    def calculate_vulnerability_risk_score(
        self,
        severity: str,
        exploitability: float = 1.0,
        impact: float = 1.0
    ) -> int:
        """
        计算单个漏洞的风险评分
        
        Args:
            severity: 严重程度 (critical/high/medium/low/info)
            exploitability: 可利用性 (0.0-1.0)
            impact: 影响程度 (0.0-1.0)
            
        Returns:
            风险评分 (0-100)
        """
        # 基础分数
        base_scores = {
            "critical": 95,
            "high": 75,
            "medium": 50,
            "low": 25,
            "info": 10
        }
        
        base_score = base_scores.get(severity.lower(), 10)
        
        # 应用可利用性和影响程度
        final_score = int(base_score * exploitability * impact)
        
        return min(100, max(0, final_score))
    
    def _get_grade(self, score: int) -> str:
        """
        根据分数获取等级
        
        Args:
            score: 分数 (0-100)
            
        Returns:
            等级 (A/B/C/D)
        """
        if score >= 90:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 50:
            return "C"
        else:
            return "D"
    
    def _get_risk_level(self, grade: str) -> str:
        """
        根据等级获取风险级别描述
        
        Args:
            grade: 等级 (A/B/C/D)
            
        Returns:
            风险级别描述
        """
        risk_levels = {
            "A": "风险极低",
            "B": "风险较低",
            "C": "中等风险",
            "D": "高风险"
        }
        
        return risk_levels.get(grade, "未知风险")
    
    def get_recommendations(
        self,
        severity_counts: Dict[str, int]
    ) -> List[str]:
        """
        根据漏洞分布生成修复建议
        
        Args:
            severity_counts: 严重程度统计
            
        Returns:
            建议列表
        """
        recommendations = []
        
        if severity_counts.get("critical", 0) > 0:
            recommendations.append(
                f"发现 {severity_counts['critical']} 个严重漏洞，建议立即修复！"
            )
        
        if severity_counts.get("high", 0) > 0:
            recommendations.append(
                f"发现 {severity_counts['high']} 个高危漏洞，建议优先修复。"
            )
        
        if severity_counts.get("medium", 0) > 0:
            recommendations.append(
                f"发现 {severity_counts['medium']} 个中危漏洞，建议在下个版本修复。"
            )
        
        if severity_counts.get("low", 0) > 0:
            recommendations.append(
                f"发现 {severity_counts['low']} 个低危漏洞，可在后续版本中修复。"
            )
        
        if not any(severity_counts.values()):
            recommendations.append("未发现安全漏洞，系统安全状况良好。")
        
        return recommendations
    
    def generate_risk_report(
        self,
        target_id: int,
        db: Session
    ) -> Dict:
        """
        生成目标的风险报告
        
        Args:
            target_id: 目标ID
            db: 数据库会话
            
        Returns:
            风险报告
        """
        # 获取所有漏洞
        vulnerabilities = db.query(SecurityVulnerability).filter(
            SecurityVulnerability.target_id == target_id
        ).all()
        
        # 计算风险评分
        risk_score = self.calculate_target_risk_score(vulnerabilities)
        
        # 生成建议
        recommendations = self.get_recommendations(risk_score["severity_breakdown"])
        
        # 获取最严重的漏洞
        critical_vulns = [
            {
                "title": v.title,
                "severity": v.severity,
                "status": v.status,
                "risk_score": v.risk_score
            }
            for v in vulnerabilities
            if v.severity in ["critical", "high"]
        ]
        
        return {
            "risk_score": risk_score,
            "recommendations": recommendations,
            "critical_vulnerabilities": critical_vulns[:10],  # 最多显示10个
            "summary": self._generate_summary(risk_score)
        }
    
    def _generate_summary(self, risk_score: Dict) -> str:
        """
        生成风险摘要
        
        Args:
            risk_score: 风险评分结果
            
        Returns:
            摘要文本
        """
        grade = risk_score["grade"]
        total_score = risk_score["total_score"]
        total_vulns = risk_score["total_vulns"]
        open_vulns = risk_score["open_vulns"]
        
        summary = f"安全评级: {grade} ({total_score}分)\n"
        summary += f"风险级别: {risk_score['risk_level']}\n"
        summary += f"漏洞总数: {total_vulns} 个\n"
        summary += f"未修复漏洞: {open_vulns} 个\n"
        
        severity_breakdown = risk_score["severity_breakdown"]
        if severity_breakdown.get("critical", 0) > 0:
            summary += f"⚠️ 严重漏洞: {severity_breakdown['critical']} 个\n"
        if severity_breakdown.get("high", 0) > 0:
            summary += f"⚠️ 高危漏洞: {severity_breakdown['high']} 个\n"
        if severity_breakdown.get("medium", 0) > 0:
            summary += f"⚠️ 中危漏洞: {severity_breakdown['medium']} 个\n"
        
        return summary
