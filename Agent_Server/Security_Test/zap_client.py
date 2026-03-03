"""
OWASP ZAP 客户端

通过 ZAP API 执行 Web 安全扫描（Spider + Active Scan）

前置条件: ZAP 以 daemon 模式运行（推荐 Docker）
docker run -d -p 19090:8080 --name zap ghcr.io/zaproxy/zaproxy:weekly zap.sh -daemon -host 0.0.0.0 -port 8080 -config api.key=123456 -config api.addrs.addr.name=127.0.0.1 -config api.addrs.addr.regex=false -config api.disablekey=false
作者: Ai_Test_Agent Team
"""
import asyncio
import logging
import os
import time
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)

_ZAP_HTTP = requests.Session()
# Avoid inheriting HTTP(S)_PROXY for local ZAP calls
_ZAP_HTTP.trust_env = False


def get_zap_config() -> Dict[str, Any]:
    """Read ZAP settings from environment at runtime."""
    base_url = os.getenv("ZAP_API_URL", "http://localhost:8080").rstrip("/")
    api_key = os.getenv("ZAP_API_KEY", "changeme")
    try:
        max_scan_minutes = int(os.getenv("ZAP_MAX_SCAN_MINUTES", "30"))
    except ValueError:
        max_scan_minutes = 30

    return {
        "base_url": base_url,
        "api_key": api_key,
        "max_scan_minutes": max_scan_minutes,
    }


def _mask_api_key(api_key: str) -> str:
    if not api_key:
        return "(empty)"
    if len(api_key) <= 4:
        return "*" * len(api_key)
    return f"{api_key[:2]}***{api_key[-2:]}"


def _zap_get(path: str, params: dict = None) -> dict:
    """ZAP API GET request."""
    config = get_zap_config()
    payload = dict(params or {})
    payload["apikey"] = config["api_key"]
    url = f"{config['base_url']}{path}"
    headers = {"X-ZAP-API-Key": config["api_key"]} if config["api_key"] else {}
    resp = _ZAP_HTTP.get(url, params=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def check_zap_running_detail() -> tuple[bool, str]:
    """Return detailed connectivity status for ZAP."""
    config = get_zap_config()
    try:
        result = _zap_get("/JSON/core/view/version/")
        version = result.get("version", "")
        if version:
            return True, f"connected (version={version})"
        return False, f"unexpected response from {config['base_url']}: {result}"
    except Exception as e:
        masked_key = _mask_api_key(config["api_key"])
        proxy_keys = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]
        has_proxy_env = any(os.getenv(k) for k in proxy_keys)
        proxy_hint = " Potential proxy env detected; ensure local calls bypass proxy (NO_PROXY=127.0.0.1,localhost)." if has_proxy_env else ""
        return False, (
            f"failed to connect {config['base_url']} "
            f"(api_key={masked_key}): {e}.{proxy_hint}"
        )


def check_zap_running() -> bool:
    """Check whether ZAP is reachable."""
    ok, reason = check_zap_running_detail()
    if not ok:
        logger.warning(f"[ZAP] check_zap_running failed: {reason}")
        return False
    return True


def new_session() -> bool:
    """Create new ZAP session."""
    try:
        _zap_get("/JSON/core/action/newSession/", {"override": "true"})
        return True
    except Exception as e:
        logger.warning(f"Create ZAP session failed: {e}")
        return False


async def run_spider(target: str, task_id: int, on_progress=None) -> bool:
    """Run ZAP spider crawl."""
    from Security_Test.task_manager import should_stop

    try:
        result = _zap_get("/JSON/spider/action/scan/", {"url": target, "recurse": "true"})
        scan_id = result.get("scan")
        if not scan_id:
            logger.error(f"Spider start failed: {result}")
            return False

        logger.info(f"[ZAP] Spider started: scan_id={scan_id}")

        deadline = time.time() + get_zap_config()["max_scan_minutes"] * 60
        while True:
            if should_stop(task_id):
                _zap_get("/JSON/spider/action/stop/", {"scanId": scan_id})
                return False
            if time.time() > deadline:
                _zap_get("/JSON/spider/action/stop/", {"scanId": scan_id})
                logger.warning("[ZAP] Spider timeout, stopped")
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
        logger.error(f"[ZAP] Spider exception: {e}")
        return False


async def run_active_scan(target: str, task_id: int, on_progress=None) -> bool:
    """Run ZAP active scan."""
    from Security_Test.task_manager import should_stop

    try:
        result = _zap_get("/JSON/ascan/action/scan/", {"url": target, "recurse": "true"})
        scan_id = result.get("scan")
        if not scan_id:
            logger.error(f"Active scan start failed: {result}")
            return False

        logger.info(f"[ZAP] Active scan started: scan_id={scan_id}")

        deadline = time.time() + get_zap_config()["max_scan_minutes"] * 60
        while True:
            if should_stop(task_id):
                _zap_get("/JSON/ascan/action/stop/", {"scanId": scan_id})
                return False
            if time.time() > deadline:
                _zap_get("/JSON/ascan/action/stop/", {"scanId": scan_id})
                logger.warning("[ZAP] Active scan timeout, stopped")
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
        logger.error(f"[ZAP] Active scan exception: {e}")
        return False


def get_alerts() -> List[dict]:
    """Get all scan alerts."""
    try:
        result = _zap_get("/JSON/core/view/alerts/", {"start": "0", "count": "500"})
        return result.get("alerts", [])
    except Exception as e:
        logger.error(f"[ZAP] Get alerts failed: {e}")
        return []
