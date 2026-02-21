"""
安全基线检测

检查目标 Web 应用的安全基线配置:
- HTTP 安全头
- HTTPS 配置
- Cookie 安全属性
- 信息泄露
- 常见敏感路径

作者: Ai_Test_Agent Team
"""
import logging
from typing import List, Dict

import requests

logger = logging.getLogger(__name__)

# 推荐的安全响应头
RECOMMENDED_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY|SAMEORIGIN",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": None,  # 只检查存在性
    "Content-Security-Policy": None,
    "Referrer-Policy": None,
}

# 敏感路径探测
SENSITIVE_PATHS = [
    "/.env", "/.git/config", "/wp-admin", "/phpmyadmin",
    "/server-status", "/server-info", "/.DS_Store",
    "/api/docs", "/swagger.json", "/openapi.json",
    "/actuator", "/actuator/health", "/debug",
    "/admin", "/console", "/trace",
]


def normalize_vuln(source, vuln_type, severity, url="", description="", solution=""):
    """构造统一漏洞结构"""
    from Security_Test.vuln_parser import normalize_vuln as _norm
    return _norm(source=source, vuln_type=vuln_type, severity=severity,
                 url=url, description=description, solution=solution)


async def run_baseline_check(target_url: str) -> List[dict]:
    """
    执行安全基线检测

    Args:
        target_url: 目标 URL

    Returns:
        统一格式的漏洞列表
    """
    vulns = []
    target = target_url.rstrip("/")

    # 1. 检查安全响应头
    vulns.extend(_check_security_headers(target))

    # 2. 检查 Cookie 安全属性
    vulns.extend(_check_cookie_security(target))

    # 3. 检查 HTTPS
    vulns.extend(_check_https(target))

    # 4. 检查信息泄露
    vulns.extend(_check_info_disclosure(target))

    # 5. 敏感路径探测
    vulns.extend(_check_sensitive_paths(target))

    return vulns


def _check_security_headers(target: str) -> List[dict]:
    """检查安全响应头"""
    vulns = []
    try:
        resp = requests.get(target, timeout=10, allow_redirects=True, verify=False)
        headers = resp.headers

        for header_name, expected_value in RECOMMENDED_HEADERS.items():
            value = headers.get(header_name)
            if not value:
                vulns.append(normalize_vuln(
                    source="baseline",
                    vuln_type=f"Missing Security Header: {header_name}",
                    severity="medium" if header_name in ("Content-Security-Policy", "Strict-Transport-Security") else "low",
                    url=target,
                    description=f"响应中缺少安全头 {header_name}",
                    solution=f"在服务器响应中添加 {header_name} 头",
                ))

        # 检查 Server 头信息泄露
        server = headers.get("Server", "")
        if server and any(kw in server.lower() for kw in ["apache", "nginx", "iis", "express"]):
            vulns.append(normalize_vuln(
                source="baseline",
                vuln_type="Server Version Disclosure",
                severity="low",
                url=target,
                description=f"Server 头泄露了服务器信息: {server}",
                solution="移除或混淆 Server 响应头中的版本信息",
            ))

        # 检查 X-Powered-By
        powered_by = headers.get("X-Powered-By", "")
        if powered_by:
            vulns.append(normalize_vuln(
                source="baseline",
                vuln_type="Technology Stack Disclosure",
                severity="low",
                url=target,
                description=f"X-Powered-By 头泄露了技术栈: {powered_by}",
                solution="移除 X-Powered-By 响应头",
            ))

    except Exception as e:
        logger.warning(f"安全头检查失败: {e}")
    return vulns


def _check_cookie_security(target: str) -> List[dict]:
    """检查 Cookie 安全属性"""
    vulns = []
    try:
        resp = requests.get(target, timeout=10, allow_redirects=True, verify=False)
        for cookie in resp.cookies:
            issues = []
            if not cookie.secure:
                issues.append("缺少 Secure 标志")
            if not cookie.has_nonstandard_attr("HttpOnly"):
                # requests 库不直接暴露 HttpOnly，检查 Set-Cookie 头
                pass
            if not cookie.has_nonstandard_attr("SameSite"):
                issues.append("缺少 SameSite 属性")

            if issues:
                vulns.append(normalize_vuln(
                    source="baseline",
                    vuln_type="Insecure Cookie",
                    severity="medium",
                    url=target,
                    description=f"Cookie '{cookie.name}' 存在安全问题: {', '.join(issues)}",
                    solution="为 Cookie 设置 Secure、HttpOnly、SameSite 属性",
                ))
    except Exception as e:
        logger.warning(f"Cookie 检查失败: {e}")
    return vulns


def _check_https(target: str) -> List[dict]:
    """检查 HTTPS 配置"""
    vulns = []
    if target.startswith("http://"):
        vulns.append(normalize_vuln(
            source="baseline",
            vuln_type="No HTTPS",
            severity="high",
            url=target,
            description="目标站点未使用 HTTPS，数据传输未加密",
            solution="配置 SSL/TLS 证书，强制 HTTPS 访问",
        ))
    return vulns


def _check_info_disclosure(target: str) -> List[dict]:
    """检查信息泄露"""
    vulns = []
    try:
        # 检查错误页面是否泄露堆栈信息
        resp = requests.get(f"{target}/nonexistent_path_404_test", timeout=10,
                            allow_redirects=True, verify=False)
        body = resp.text.lower()
        if any(kw in body for kw in ["traceback", "stack trace", "exception",
                                      "debug", "at line", "file \""]):
            vulns.append(normalize_vuln(
                source="baseline",
                vuln_type="Debug Information Disclosure",
                severity="medium",
                url=f"{target}/nonexistent_path_404_test",
                description="错误页面泄露了调试信息或堆栈跟踪",
                solution="在生产环境关闭 DEBUG 模式，自定义错误页面",
            ))
    except Exception:
        pass
    return vulns


def _check_sensitive_paths(target: str) -> List[dict]:
    """探测敏感路径"""
    vulns = []
    for path in SENSITIVE_PATHS:
        try:
            url = f"{target}{path}"
            resp = requests.get(url, timeout=5, allow_redirects=False, verify=False)
            if resp.status_code == 200:
                # 排除通用 SPA 路由（总是返回 200 + HTML）
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type and len(resp.text) > 5000:
                    continue  # 可能是 SPA fallback
                vulns.append(normalize_vuln(
                    source="baseline",
                    vuln_type="Sensitive Path Exposed",
                    severity="high" if path in ("/.env", "/.git/config") else "medium",
                    url=url,
                    description=f"敏感路径 {path} 可被公开访问",
                    solution=f"限制对 {path} 的访问，配置 Web 服务器拒绝该路径",
                ))
        except Exception:
            continue
    return vulns
