"""
OWASP ZAP 客户端

通过 ZAP API 执行 Web 安全扫描（Spider + Active Scan）

前置条件: ZAP 以 daemon 模式运行（推荐 Docker）
  docker run -d -p 8090:8080 -e ZAP_API_KEY=changeme ghcr.io/zaproxy/zaproxy:stable zap.sh -daemon -host 0.0.0.0 -port 8080 -config api.key=changeme

作者: Ai_Test_Agent Team
"""
import asyncio
import logging
import os
import time
from typing import List, Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)

ZAP_BASE_URL = os.getenv("ZAP_API_URL", "http://localhost:8090")
ZAP_API_KEY = os.getenv("ZAP_API_KEY", "changeme")
ZAP_MAX_SCAN_MINUTES = int(os.getenv("ZAP_MAX_SCAN_MINUTES", "30"))


def _zap_get(path: str, params: dict = None) -> dict:
    """ZAP API GET 请求"""
    params = params or {}
    params["apikey"] = ZAP_API_KEY
    url = f"{ZAP_BASE_URL}{path}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def check_zap_running() -> bool:
    """检查 ZAP 是否在运行"""
    try:
        result = _zap_get("/JSON/core/view/version/")
        return "version" in result
    except Exception:
        return False


def new_session() -> bool:
    """创建新的 ZAP 扫描会话"""
    try:
        _zap_get("/JSON/core/action/newSession/", {"override": "true"})
        return True
    except Exception as e:
        logger.warning(f"创建 ZAP session 失败: {e}")
        return False


async def run_spider(target: str, task_id: int, on_progress=None) -> bool:
    """
    执行 ZAP Spider 爬虫

    Args:
        target: 目标 URL
        task_id: 任务 ID（用于检查停止信号）
        on_progress: 进度回调 (progress_pct)
    """
    from Security_Test.task_manager import should_stop

    try:
        result = _zap_get("/JSON/spider/action/scan/", {"url": target, "recurse": "true"})
        scan_id = result.get("scan")
        if not scan_id:
            logger.error(f"Spider 启动失败: {result}")
            return False

        logger.info(f"[ZAP] Spider 已启动: scan_id={scan_id}")

        deadline = time.time() + ZAP_MAX_SCAN_MINUTES * 60
        while True:
            if should_stop(task_id):
                _zap_get("/JSON/spider/action/stop/", {"scanId": scan_id})
                return False
            if time.time() > deadline:
                _zap_get("/JSON/spider/action/stop/", {"scanId": scan_id})
                logger.warning("[ZAP] Spider 超时，已停止")
                break

            status = _zap_get("/JSON/spider/view/status/", {"scanId": scan_id})
            progress = int(status.get("status", "0"))
            if on_progress:
                on_progress(progress)
            if progress >= 100:
                break
            await asyncio.sleep(2)

        return True
    except Exception as e:
        logger.error(f"[ZAP] Spider 异常: {e}")
        return False


async def run_active_scan(target: str, task_id: int, on_progress=None) -> bool:
    """
    执行 ZAP Active Scan

    Args:
        target: 目标 URL
        task_id: 任务 ID
        on_progress: 进度回调
    """
    from Security_Test.task_manager import should_stop

    try:
        result = _zap_get("/JSON/ascan/action/scan/", {"url": target, "recurse": "true"})
        scan_id = result.get("scan")
        if not scan_id:
            logger.error(f"Active Scan 启动失败: {result}")
            return False

        logger.info(f"[ZAP] Active Scan 已启动: scan_id={scan_id}")

        deadline = time.time() + ZAP_MAX_SCAN_MINUTES * 60
        while True:
            if should_stop(task_id):
                _zap_get("/JSON/ascan/action/stop/", {"scanId": scan_id})
                return False
            if time.time() > deadline:
                _zap_get("/JSON/ascan/action/stop/", {"scanId": scan_id})
                logger.warning("[ZAP] Active Scan 超时，已停止")
                break

            status = _zap_get("/JSON/ascan/view/status/", {"scanId": scan_id})
            progress = int(status.get("status", "0"))
            if on_progress:
                on_progress(progress)
            if progress >= 100:
                break
            await asyncio.sleep(3)

        return True
    except Exception as e:
        logger.error(f"[ZAP] Active Scan 异常: {e}")
        return False


def get_alerts() -> List[dict]:
    """获取所有扫描告警"""
    try:
        result = _zap_get("/JSON/core/view/alerts/", {"start": "0", "count": "500"})
        return result.get("alerts", [])
    except Exception as e:
        logger.error(f"[ZAP] 获取告警失败: {e}")
        return []
