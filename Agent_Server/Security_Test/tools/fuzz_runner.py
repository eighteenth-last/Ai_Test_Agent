"""
自定义 Fuzz 测试工具

简单的模糊测试工具，用于快速检测常见漏洞

作者: 程序员Eighteen
"""
import asyncio
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import aiohttp

from .base_runner import BaseScanRunner

logger = logging.getLogger(__name__)


class FuzzRunner(BaseScanRunner):
    """自定义 Fuzz 扫描器"""
    
    def __init__(self):
        super().__init__()
        self.tool_name = "fuzz"
        self.version = "1.0.0"
        
        # Payload 库
        self.payloads = {
            "sql_injection": [
                "' OR '1'='1",
                "' OR '1'='1'--",
                "' OR '1'='1'/*",
                "admin'--",
                "1' UNION SELECT NULL--",
            ],
            "xss": [
                "<script>alert(1)</script>",
                "<img src=x onerror=alert(1)>",
                "<svg onload=alert(1)>",
                "javascript:alert(1)",
            ],
            "path_traversal": [
                "../../etc/passwd",
                "..\\..\\windows\\system32\\config\\sam",
                "....//....//etc/passwd",
            ],
            "command_injection": [
                "; ls -la",
                "| whoami",
                "& dir",
                "`id`",
            ],
        }
    
    async def check_available(self) -> Dict:
        """检查工具是否可用（内置工具，始终可用）"""
        return {
            "available": True,
            "version": self.version,
            "message": "自定义 Fuzz 工具已就绪"
        }
    
    async def run_scan(
        self, 
        target: str, 
        config: Optional[Dict] = None
    ) -> List[Dict]:
        """
        执行 Fuzz 扫描
        
        Args:
            target: 目标URL
            config: 配置参数
                - attack_types: 攻击类型列表 (sql_injection, xss, path_traversal, command_injection)
                - timeout: 超时时间
        
        Returns:
            漏洞列表
        """
        config = config or {}
        
        # 攻击类型
        attack_types = config.get("attack_types", list(self.payloads.keys()))
        
        # 超时时间
        timeout = config.get("timeout", 300)
        
        logger.info(f"[Fuzz] 开始扫描: {target}")
        logger.info(f"[Fuzz] 攻击类型: {', '.join(attack_types)}")
        
        results = []
        
        # 对每种攻击类型进行测试
        for attack_type in attack_types:
            if attack_type not in self.payloads:
                logger.warning(f"[Fuzz] 未知攻击类型: {attack_type}")
                continue
            
            payloads = self.payloads[attack_type]
            attack_results = await self._test_payloads(
                target, 
                attack_type, 
                payloads,
                timeout
            )
            results.extend(attack_results)
        
        logger.info(f"[Fuzz] 扫描完成，发现 {len(results)} 个潜在漏洞")
        
        return results
    
    async def _test_payloads(
        self,
        target: str,
        attack_type: str,
        payloads: List[str],
        timeout: int
    ) -> List[Dict]:
        """
        测试一组 payloads
        
        Args:
            target: 目标URL
            attack_type: 攻击类型
            payloads: payload 列表
            timeout: 超时时间
            
        Returns:
            漏洞列表
        """
        results = []
        
        # 解析 URL
        parsed = urlparse(target)
        params = parse_qs(parsed.query)
        
        if not params:
            logger.info(f"[Fuzz] URL 无参数，跳过: {target}")
            return results
        
        # 对每个参数测试每个 payload
        async with aiohttp.ClientSession() as session:
            for param_name in params.keys():
                for payload in payloads:
                    try:
                        # 构造测试 URL
                        test_params = params.copy()
                        test_params[param_name] = [payload]
                        
                        test_query = urlencode(test_params, doseq=True)
                        test_url = urlunparse((
                            parsed.scheme,
                            parsed.netloc,
                            parsed.path,
                            parsed.params,
                            test_query,
                            parsed.fragment
                        ))
                        
                        # 发送请求
                        async with session.get(
                            test_url,
                            timeout=aiohttp.ClientTimeout(total=10),
                            allow_redirects=False
                        ) as response:
                            content = await response.text()
                            
                            # 检测漏洞特征
                            if self._detect_vulnerability(
                                attack_type,
                                payload,
                                response.status,
                                content
                            ):
                                result = {
                                    "severity": self._get_severity(attack_type),
                                    "title": self._get_title(attack_type),
                                    "description": f"在参数 {param_name} 发现潜在的 {attack_type} 漏洞",
                                    "url": test_url,
                                    "param": param_name,
                                    "payload": payload,
                                    "evidence": f"HTTP {response.status}, Content: {content[:200]}",
                                    "raw_output": content[:500]
                                }
                                results.append(result)
                                logger.info(f"[Fuzz] 发现漏洞: {attack_type} in {param_name}")
                    
                    except asyncio.TimeoutError:
                        logger.debug(f"[Fuzz] 请求超时: {param_name} = {payload}")
                    except Exception as e:
                        logger.debug(f"[Fuzz] 请求失败: {e}")
        
        return results
    
    def _detect_vulnerability(
        self,
        attack_type: str,
        payload: str,
        status_code: int,
        content: str
    ) -> bool:
        """
        检测是否存在漏洞
        
        Args:
            attack_type: 攻击类型
            payload: 使用的 payload
            status_code: HTTP 状态码
            content: 响应内容
            
        Returns:
            是否检测到漏洞
        """
        content_lower = content.lower()
        
        if attack_type == "sql_injection":
            # SQL 错误特征
            sql_errors = [
                "sql syntax",
                "mysql_fetch",
                "ora-",
                "postgresql",
                "sqlite",
                "syntax error",
                "unclosed quotation",
            ]
            return any(error in content_lower for error in sql_errors)
        
        elif attack_type == "xss":
            # XSS 特征（payload 被反射）
            return payload.lower() in content_lower
        
        elif attack_type == "path_traversal":
            # 路径遍历特征
            path_indicators = [
                "root:",
                "[boot loader]",
                "etc/passwd",
                "system32",
            ]
            return any(indicator in content_lower for indicator in path_indicators)
        
        elif attack_type == "command_injection":
            # 命令注入特征
            cmd_indicators = [
                "uid=",
                "gid=",
                "volume in drive",
                "directory of",
            ]
            return any(indicator in content_lower for indicator in cmd_indicators)
        
        return False
    
    def _get_severity(self, attack_type: str) -> str:
        """获取攻击类型对应的严重程度"""
        severity_map = {
            "sql_injection": "high",
            "xss": "medium",
            "path_traversal": "high",
            "command_injection": "critical",
        }
        return severity_map.get(attack_type, "medium")
    
    def _get_title(self, attack_type: str) -> str:
        """获取攻击类型对应的标题"""
        title_map = {
            "sql_injection": "SQL 注入漏洞",
            "xss": "跨站脚本攻击 (XSS)",
            "path_traversal": "路径遍历漏洞",
            "command_injection": "命令注入漏洞",
        }
        return title_map.get(attack_type, "安全漏洞")
