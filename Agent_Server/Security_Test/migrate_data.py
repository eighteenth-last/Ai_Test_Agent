"""
数据迁移脚本 - 从旧安全测试架构迁移到新架构

作者: 程序员Eighteen
"""
import json
import logging
from datetime import datetime
from typing import Dict, List

from sqlalchemy.orm import Session
from database.connection import (
    SessionLocal, SecurityTarget, SecurityScanTask as NewSecurityScanTask,
    SecurityScanResult, SecurityVulnerability
)

logger = logging.getLogger(__name__)


def migrate_security_data():
    """迁移安全测试数据"""
    db = SessionLocal()
    try:
        # 检查是否存在旧的 security_scan_tasks 表数据
        from sqlalchemy import text
        
        # 查询旧表结构的数据
        old_tasks_query = text("""
            SELECT id, scan_type, target, status, progress, config, 
                   risk_score, risk_level, vuln_summary, vulnerabilities,
                   report_content, error_message, start_time, end_time, 
                   duration, created_at, updated_at
            FROM security_scan_tasks 
            WHERE target IS NOT NULL
        """)
        
        result = db.execute(old_tasks_query)
        old_tasks = result.fetchall()
        
        if not old_tasks:
            logger.info("没有找到需要迁移的旧数据")
            return
        
        logger.info(f"找到 {len(old_tasks)} 条旧任务数据，开始迁移...")
        
        # 创建默认目标
        default_targets = {}
        
        for old_task in old_tasks:
            target_url = old_task.target
            
            # 为每个唯一的目标URL创建目标记录
            if target_url not in default_targets:
                target = SecurityTarget(
                    name=f"迁移目标 - {target_url}",
                    base_url=target_url,
                    description="从旧架构迁移的目标",
                    target_type="web",
                    environment="unknown"
                )
                db.add(target)
                db.flush()  # 获取ID但不提交
                default_targets[target_url] = target.id
                logger.info(f"创建目标: {target.name} (ID: {target.id})")
            
            target_id = default_targets[target_url]
            
            # 迁移任务数据（保持原有ID）
            # 注意：这里我们不创建新的任务记录，因为表结构已经更新
            # 只需要确保有对应的目标记录即可
            
            # 如果有漏洞数据，解析并创建漏洞记录
            if old_task.vulnerabilities:
                try:
                    vulns_data = json.loads(old_task.vulnerabilities) if isinstance(old_task.vulnerabilities, str) else old_task.vulnerabilities
                    
                    if isinstance(vulns_data, list):
                        for vuln_data in vulns_data:
                            if isinstance(vuln_data, dict):
                                # 检查是否已存在相同漏洞
                                existing_vuln = db.query(SecurityVulnerability).filter(
                                    SecurityVulnerability.target_id == target_id,
                                    SecurityVulnerability.title == vuln_data.get("title", "Unknown")
                                ).first()
                                
                                if not existing_vuln:
                                    vulnerability = SecurityVulnerability(
                                        target_id=target_id,
                                        title=vuln_data.get("title", "Unknown Vulnerability"),
                                        severity=vuln_data.get("severity", "info"),
                                        vuln_type=vuln_data.get("vuln_type", "unknown"),
                                        description=vuln_data.get("description", ""),
                                        fix_suggestion=_get_fix_suggestion(vuln_data.get("vuln_type", "")),
                                        status="open",
                                        risk_score=_calculate_risk_score(vuln_data.get("severity", "info")),
                                        first_found=old_task.created_at or datetime.now(),
                                        last_seen=old_task.updated_at or datetime.now()
                                    )
                                    db.add(vulnerability)
                
                except Exception as e:
                    logger.warning(f"解析任务 {old_task.id} 的漏洞数据失败: {e}")
        
        # 提交所有更改
        db.commit()
        logger.info("数据迁移完成！")
        
        # 更新任务记录的 target_id
        update_query = text("""
            UPDATE security_scan_tasks 
            SET target_id = (
                SELECT id FROM security_targets 
                WHERE base_url = security_scan_tasks.target 
                LIMIT 1
            )
            WHERE target_id IS NULL OR target_id = 0
        """)
        
        db.execute(update_query)
        db.commit()
        logger.info("更新任务的 target_id 完成！")
        
    except Exception as e:
        logger.error(f"数据迁移失败: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def _get_fix_suggestion(vuln_type: str) -> str:
    """获取修复建议"""
    suggestions = {
        "sql_injection": "使用参数化查询或预编译语句，避免直接拼接SQL",
        "xss": "对用户输入进行HTML编码，使用CSP策略",
        "csrf": "使用CSRF Token验证请求来源",
        "lfi": "验证文件路径，使用白名单限制访问",
        "rfi": "禁用远程文件包含，验证URL来源",
        "command_injection": "验证和过滤用户输入，使用白名单限制命令执行",
        "path_traversal": "规范化路径，限制访问范围",
        "information_disclosure": "移除敏感信息，配置适当的错误页面"
    }
    
    return suggestions.get(vuln_type.lower(), "请根据漏洞类型制定相应的修复方案")


def _calculate_risk_score(severity: str) -> int:
    """计算风险评分"""
    scores = {
        "critical": 90,
        "high": 70,
        "medium": 50,
        "low": 30,
        "info": 10
    }
    return scores.get(severity.lower(), 10)


def cleanup_old_data():
    """清理旧数据（可选）"""
    db = SessionLocal()
    try:
        # 这里可以添加清理旧数据的逻辑
        # 例如删除已迁移的旧记录等
        logger.info("数据清理完成")
    except Exception as e:
        logger.error(f"数据清理失败: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("开始安全测试数据迁移...")
    migrate_security_data()
    
    print("\n迁移完成！")
    print("请检查数据库中的 security_targets 和 security_vulnerabilities 表")