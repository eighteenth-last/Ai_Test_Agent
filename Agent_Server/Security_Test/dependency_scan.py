"""
依赖扫描

执行 Safety / Bandit / npm audit / Trivy 等工具扫描项目依赖安全

作者: Ai_Test_Agent Team
"""
import asyncio
import logging
import os
from typing import List, Dict

from Security_Test.vuln_parser import (
    parse_safety_output, parse_bandit_output,
    parse_npm_audit_output, parse_trivy_output,
)

logger = logging.getLogger(__name__)

SCAN_TIMEOUT = int(os.getenv("DEP_SCAN_TIMEOUT", "120"))


async def _run_cmd(cmd: List[str], timeout: int = SCAN_TIMEOUT) -> str:
    """执行命令并返回 stdout"""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode("utf-8", errors="replace")
    except FileNotFoundError:
        return f"[未安装] {cmd[0]} 未找到"
    except asyncio.TimeoutError:
        return f"[超时] {cmd[0]} 执行超时"
    except Exception as e:
        return f"[错误] {str(e)}"


async def run_safety_scan(requirements_path: str = None) -> List[dict]:
    """运行 Safety 扫描 Python 依赖"""
    if requirements_path and os.path.exists(requirements_path):
        output = await _run_cmd(["safety", "check", "-r", requirements_path, "--json"])
    else:
        output = await _run_cmd(["safety", "check", "--json"])

    if output.startswith("[未安装]") or output.startswith("[超时]") or output.startswith("[错误]"):
        logger.warning(f"Safety: {output}")
        return []
    return parse_safety_output(output)


async def run_bandit_scan(target_dir: str = ".") -> List[dict]:
    """运行 Bandit 扫描 Python 代码安全"""
    output = await _run_cmd([
        "bandit", "-r", target_dir, "-f", "json",
        "--exclude", ".venv,node_modules,__pycache__,.git",
        "-ll",  # 只报告 medium 及以上
    ])

    if output.startswith("[未安装]") or output.startswith("[超时]") or output.startswith("[错误]"):
        logger.warning(f"Bandit: {output}")
        return []
    return parse_bandit_output(output)


async def run_npm_audit(project_dir: str = None) -> List[dict]:
    """运行 npm audit 扫描 Node.js 依赖"""
    cmd = ["npm", "audit", "--json"]
    if project_dir:
        cmd.extend(["--prefix", project_dir])

    output = await _run_cmd(cmd)
    if output.startswith("[未安装]") or output.startswith("[超时]") or output.startswith("[错误]"):
        logger.warning(f"npm audit: {output}")
        return []
    return parse_npm_audit_output(output)


async def run_trivy_scan(target: str = ".") -> List[dict]:
    """运行 Trivy 扫描（支持 Dockerfile / 镜像 / 文件系统）"""
    # 判断是镜像还是文件系统
    if target.startswith("docker:") or ":" in target and "/" not in target:
        cmd = ["trivy", "image", "--format", "json", target]
    else:
        cmd = ["trivy", "fs", "--format", "json", target]

    output = await _run_cmd(cmd, timeout=180)
    if output.startswith("[未安装]") or output.startswith("[超时]") or output.startswith("[错误]"):
        logger.warning(f"Trivy: {output}")
        return []
    return parse_trivy_output(output)


async def run_full_dependency_scan(
    python_requirements: str = None,
    python_code_dir: str = None,
    node_project_dir: str = None,
    trivy_target: str = None,
) -> List[dict]:
    """
    执行完整的依赖扫描（并行执行所有可用工具）

    Returns:
        统一格式的漏洞列表
    """
    tasks = []

    if python_requirements or True:  # 默认尝试
        tasks.append(run_safety_scan(python_requirements))

    if python_code_dir:
        tasks.append(run_bandit_scan(python_code_dir))

    if node_project_dir:
        tasks.append(run_npm_audit(node_project_dir))

    if trivy_target:
        tasks.append(run_trivy_scan(trivy_target))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_vulns = []
    for r in results:
        if isinstance(r, list):
            all_vulns.extend(r)
        elif isinstance(r, Exception):
            logger.warning(f"依赖扫描子任务异常: {r}")

    return all_vulns
