"""
sqlmap SQL 注入二次验证

对 ZAP 或 API 攻击中发现的疑似 SQL 注入进行 sqlmap 验证

安全限制:
- 单接口单次验证
- 限制执行时间
- 不做全站扫描

作者: Ai_Test_Agent Team
"""
import asyncio
import logging
import os
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

SQLMAP_TIMEOUT = int(os.getenv("SQLMAP_TIMEOUT", "120"))  # 秒


async def verify_sql_injection(target_url: str, param: str = None,
                               method: str = "GET", data: str = None) -> dict:
    """
    使用 sqlmap 验证 SQL 注入

    Args:
        target_url: 目标 URL（含参数）
        param: 指定测试的参数名
        method: HTTP 方法
        data: POST 数据

    Returns:
        {
            "injectable": bool,
            "dbms": str or None,
            "payload": str or None,
            "raw_output": str
        }
    """
    cmd = [
        "sqlmap", "-u", target_url,
        "--batch",
        "--risk=2",
        "--level=2",
        "--timeout=10",
        "--retries=1",
        "--threads=1",
        "--disable-coloring",
    ]

    if param:
        cmd.extend(["-p", param])
    if method.upper() == "POST" and data:
        cmd.extend(["--method=POST", f"--data={data}"])

    logger.info(f"[sqlmap] 执行: {' '.join(cmd[:6])}...")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=SQLMAP_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "injectable": False,
                "dbms": None,
                "payload": None,
                "raw_output": "sqlmap 执行超时",
            }

        output = stdout.decode("utf-8", errors="replace")
        injectable = "is vulnerable" in output.lower() or "injectable" in output.lower()

        dbms = None
        payload = None
        for line in output.split("\n"):
            if "back-end DBMS:" in line:
                dbms = line.split("back-end DBMS:")[-1].strip()
            if "Payload:" in line:
                payload = line.split("Payload:")[-1].strip()

        return {
            "injectable": injectable,
            "dbms": dbms,
            "payload": payload,
            "raw_output": output[-3000:],  # 截断保留尾部
        }

    except FileNotFoundError:
        logger.warning("[sqlmap] sqlmap 未安装，跳过 SQL 注入验证")
        return {
            "injectable": False,
            "dbms": None,
            "payload": None,
            "raw_output": "sqlmap 未安装，请运行: pip install sqlmap",
        }
    except Exception as e:
        logger.error(f"[sqlmap] 执行异常: {e}")
        return {
            "injectable": False,
            "dbms": None,
            "payload": None,
            "raw_output": str(e),
        }
