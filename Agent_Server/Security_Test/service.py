"""
安全测试核心服务

统一调度 4 种扫描类型:
1. web_scan - ZAP Web 扫描 + sqlmap 二次验证
2. api_attack - LLM 生成攻击 DSL + HTTP Runner 执行
3. dependency_scan - Safety / Bandit / npm audit / Trivy
4. baseline_check - 安全基线检测

作者: Ai_Test_Agent Team
"""
import asyncio
import json
import logging
import re
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from database.connection import SecurityScanTask, SessionLocal
from Security_Test.task_manager import (
    register_task, cleanup_task, update_task_progress,
    finish_task, should_stop,
)
from Security_Test.risk_scoring import calculate_risk_score
from Security_Test.report_builder import (
    build_markdown_report, create_bug_reports_for_critical_vulns,
    send_security_email_notification,
)

logger = logging.getLogger(__name__)

# 扫描目标白名单（私有网段 + localhost）
ALLOWED_HOSTS = re.compile(
    r"^(localhost|127\.\d+\.\d+\.\d+|10\.\d+\.\d+\.\d+|"
    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+|"
    r"\[::1\]|0\.0\.0\.0)$"
)


def _validate_target(target: str) -> bool:
    """验证扫描目标是否在白名单内（防止扫描公网）"""
    try:
        parsed = urlparse(target)
        host = parsed.hostname or ""
        return bool(ALLOWED_HOSTS.match(host))
    except Exception:
        return False


class SecurityTestService:
    """安全测试服务"""

    @staticmethod
    def create_task(scan_type: str, target: str, config: dict, db: Session) -> SecurityScanTask:
        """创建扫描任务"""
        task = SecurityScanTask(
            scan_type=scan_type,
            target=target,
            status="pending",
            progress=0,
            config=config,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    async def run_scan(task_id: int, scan_type: str, target: str, config: dict):
        """
        异步执行扫描（在后台任务中调用）

        每种扫描类型走不同的执行路径，最终统一:
        漏洞列表 → 风险评分 → 报告生成 → Bug 创建 → 邮件通知
        """
        db = SessionLocal()
        try:
            # 更新状态为 running
            task = db.query(SecurityScanTask).filter(SecurityScanTask.id == task_id).first()
            if not task:
                return
            task.status = "running"
            task.start_time = datetime.now()
            db.commit()

            vulnerabilities = []

            if scan_type == "web_scan":
                vulnerabilities = await _run_web_scan(task_id, target, config, db)
            elif scan_type == "api_attack":
                vulnerabilities = await _run_api_attack(task_id, target, config, db)
            elif scan_type == "dependency_scan":
                vulnerabilities = await _run_dependency_scan(task_id, target, config, db)
            elif scan_type == "baseline_check":
                vulnerabilities = await _run_baseline_check(task_id, target, config, db)
            else:
                finish_task(db, task_id, "failed", error_message=f"未知扫描类型: {scan_type}")
                return

            if should_stop(task_id):
                finish_task(db, task_id, "stopped")
                return

            # 风险评分
            risk_result = calculate_risk_score(vulnerabilities)

            # 生成报告
            report = build_markdown_report(
                scan_type=scan_type,
                target=target,
                vulnerabilities=vulnerabilities,
                risk_result=risk_result,
                duration=int((datetime.now() - task.start_time).total_seconds()) if task.start_time else 0,
            )

            # 创建 Bug 单
            bug_ids = create_bug_reports_for_critical_vulns(vulnerabilities, task_id, db)

            # 邮件通知
            send_security_email_notification(vulnerabilities, risk_result, target, db)

            # 完成任务
            finish_task(
                db, task_id, "finished",
                risk_score=risk_result["score"],
                risk_level=risk_result["level"],
                vuln_summary=risk_result["summary"],
                vulnerabilities=json.dumps(vulnerabilities, ensure_ascii=False),
                report_content=report,
            )

            logger.info(f"[Security] 任务 {task_id} 完成: score={risk_result['score']}, "
                        f"vulns={risk_result['summary']['total']}")

        except Exception as e:
            logger.error(f"[Security] 任务 {task_id} 异常: {e}\n{traceback.format_exc()}")
            finish_task(db, task_id, "failed", error_message=str(e))
        finally:
            db.close()
            cleanup_task(task_id)


# ============================================
# 各扫描类型的具体实现
# ============================================

async def _run_web_scan(task_id: int, target: str, config: dict, db: Session) -> List[dict]:
    """Web 扫描: ZAP Spider + Active Scan + 可选 sqlmap 验证"""
    from Security_Test.zap_client import check_zap_running, new_session, run_spider, run_active_scan, get_alerts
    from Security_Test.vuln_parser import parse_zap_alerts
    from Security_Test.sqlmap_runner import verify_sql_injection

    if not check_zap_running():
        raise RuntimeError("ZAP 未运行，请先启动 ZAP (推荐 Docker 方式)")

    new_session()
    update_task_progress(db, task_id, 5, "running")

    # Spider
    def on_spider_progress(p):
        update_task_progress(db, task_id, 5 + int(p * 0.25))

    await run_spider(target, task_id, on_spider_progress)
    if should_stop(task_id):
        return []

    update_task_progress(db, task_id, 30)

    # Active Scan
    def on_active_progress(p):
        update_task_progress(db, task_id, 30 + int(p * 0.50))

    await run_active_scan(target, task_id, on_active_progress)
    if should_stop(task_id):
        return []

    update_task_progress(db, task_id, 80)

    # 获取告警
    alerts = get_alerts()
    vulnerabilities = parse_zap_alerts(alerts)

    # sqlmap 二次验证
    if config.get("sqlmap_verify", False):
        update_task_progress(db, task_id, 85)
        sql_vulns = [v for v in vulnerabilities if "sql" in v.get("vuln_type", "").lower()]
        for vuln in sql_vulns[:3]:  # 最多验证 3 个
            if should_stop(task_id):
                break
            result = await verify_sql_injection(vuln.get("url", target), vuln.get("param"))
            if result["injectable"]:
                from Security_Test.vuln_parser import parse_sqlmap_output
                vulnerabilities.extend(parse_sqlmap_output(result["raw_output"], vuln.get("url", target)))

    update_task_progress(db, task_id, 95)
    return vulnerabilities


async def _run_api_attack(task_id: int, target: str, config: dict, db: Session) -> List[dict]:
    """API 攻击测试: LLM 生成攻击 DSL + HTTP Runner 执行"""
    from Security_Test.api_attack_generator import generate_attack_cases, execute_attack_cases
    from Security_Test.vuln_parser import parse_llm_attack_results

    update_task_progress(db, task_id, 10)

    # 获取接口列表
    endpoints = config.get("endpoints", [])
    if not endpoints:
        # 尝试从数据库获取
        from database.connection import ApiEndpoint, ApiSpecVersion
        spec_version_id = config.get("spec_version_id")
        if spec_version_id:
            eps = db.query(ApiEndpoint).filter(ApiEndpoint.spec_version_id == spec_version_id).all()
            endpoints = [{"method": ep.method, "path": ep.path, "summary": ep.summary or "",
                          "params": ep.params} for ep in eps]

    if not endpoints:
        raise ValueError("未提供接口列表，请在 config 中指定 endpoints 或 spec_version_id")

    auth_info = config.get("auth_info")
    base_url = target.rstrip("/")
    default_headers = config.get("headers", {})

    # LLM 生成攻击用例
    update_task_progress(db, task_id, 20)
    attacks = await generate_attack_cases(endpoints, auth_info)
    if should_stop(task_id):
        return []

    if not attacks:
        logger.warning("[Security] LLM 未生成攻击用例")
        return []

    # 执行攻击
    update_task_progress(db, task_id, 40)
    results = await execute_attack_cases(attacks, base_url, default_headers)
    if should_stop(task_id):
        return []

    update_task_progress(db, task_id, 90)
    return parse_llm_attack_results(results)


async def _run_dependency_scan(task_id: int, target: str, config: dict, db: Session) -> List[dict]:
    """依赖扫描"""
    from Security_Test.dependency_scan import run_full_dependency_scan

    update_task_progress(db, task_id, 10)

    vulns = await run_full_dependency_scan(
        python_requirements=config.get("python_requirements"),
        python_code_dir=config.get("python_code_dir"),
        node_project_dir=config.get("node_project_dir"),
        trivy_target=config.get("trivy_target"),
    )

    update_task_progress(db, task_id, 90)
    return vulns


async def _run_baseline_check(task_id: int, target: str, config: dict, db: Session) -> List[dict]:
    """安全基线检测"""
    from Security_Test.baseline_scan import run_baseline_check

    update_task_progress(db, task_id, 10)
    vulns = await run_baseline_check(target)
    update_task_progress(db, task_id, 90)
    return vulns
