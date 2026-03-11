"""
SQLMap 扫描工具封装

作者: Ai_Test_Agent Team
"""
import asyncio
import json
import logging
import os
import re
import subprocess
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class SqlmapRunner:
    """SQLMap 扫描器"""
    
    def __init__(self):
        self.tool_name = "sqlmap"
        self.python_path = None  # 动态检测Python路径
        self.sqlmap_script = None  # 动态检测SQLMap脚本路径
    
    async def run(self, target: str, config: Dict = None) -> List[Dict]:
        """
        运行 SQLMap 扫描
        
        Args:
            target: 扫描目标URL
            config: 扫描配置
            
        Returns:
            List[Dict]: 扫描结果列表
        """
        config = config or {}
        
        # 构建基础命令 - 使用检测到的路径
        if not self.python_path or not self.sqlmap_script:
            # 如果路径未检测，先检测一次
            await self.check_available()
        
        if self.sqlmap_script == "-m sqlmap":
            # 模块方式调用
            cmd = [
                self.python_path or "python", "-m", "sqlmap",
                "-u", target,
                "--batch",  # 非交互模式
                "--random-agent",  # 随机User-Agent
                "--level", str(config.get("level", 1)),
                "--risk", str(config.get("risk", 1))
            ]
        else:
            # 脚本方式调用
            cmd = [
                self.python_path or "python", 
                self.sqlmap_script or "sqlmap",
                "-u", target,
                "--batch",  # 非交互模式
                "--random-agent",  # 随机User-Agent
                "--level", str(config.get("level", 1)),
                "--risk", str(config.get("risk", 1))
            ]
        
        # 添加输出格式
        output_dir = "/tmp/sqlmap_output"
        os.makedirs(output_dir, exist_ok=True)
        cmd.extend(["--output-dir", output_dir])
        
        # 添加其他参数
        if config.get("cookie"):
            cmd.extend(["--cookie", config["cookie"]])
        
        if config.get("headers"):
            for header in config["headers"]:
                cmd.extend(["--header", header])
        
        if config.get("data"):
            cmd.extend(["--data", config["data"]])
        
        if config.get("method"):
            cmd.extend(["--method", config["method"]])
        
        # 设置超时
        timeout = config.get("timeout", 300)  # 默认5分钟
        
        logger.info(f"执行 SQLMap 命令: {' '.join(cmd)}")
        
        try:
            # 异步执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                logger.warning(f"SQLMap 扫描超时 ({timeout}s)")
                return []
            
            output = stdout.decode() + stderr.decode()
            
            # 解析结果
            results = self._parse_sqlmap_output(output, target)
            
            logger.info(f"SQLMap 扫描完成，发现 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"SQLMap 扫描异常: {e}")
            return []
    
    def _parse_sqlmap_output(self, output: str, target: str) -> List[Dict]:
        """解析 SQLMap 输出"""
        results = []
        
        # 检查是否发现注入
        if "is vulnerable" in output.lower() or "injectable" in output.lower():
            # 提取注入类型
            injection_types = self._extract_injection_types(output)
            
            # 提取参数
            vulnerable_params = self._extract_vulnerable_params(output)
            
            # 提取数据库信息
            db_info = self._extract_database_info(output)
            
            for param in vulnerable_params or ["unknown"]:
                result = {
                    "tool": "sqlmap",
                    "severity": "high",  # SQL注入通常是高危
                    "title": f"SQL Injection in parameter '{param}'",
                    "description": f"Parameter '{param}' is vulnerable to SQL injection",
                    "vuln_type": "sql_injection",
                    "url": target,
                    "param": param,
                    "payload": self._extract_payload(output, param),
                    "evidence": self._extract_evidence(output),
                    "raw_output": output,
                    "injection_types": injection_types,
                    "database_info": db_info
                }
                results.append(result)
        
        # 检查其他发现
        if "WAF" in output:
            results.append({
                "tool": "sqlmap",
                "severity": "info",
                "title": "WAF Detection",
                "description": "Web Application Firewall detected",
                "vuln_type": "waf_detection",
                "url": target,
                "evidence": self._extract_waf_info(output),
                "raw_output": output
            })
        
        return results
    
    def _extract_injection_types(self, output: str) -> List[str]:
        """提取注入类型"""
        types = []
        
        patterns = [
            r"boolean-based blind",
            r"time-based blind", 
            r"error-based",
            r"UNION query",
            r"stacked queries"
        ]
        
        for pattern in patterns:
            if re.search(pattern, output, re.IGNORECASE):
                types.append(pattern)
        
        return types
    
    def _extract_vulnerable_params(self, output: str) -> List[str]:
        """提取易受攻击的参数"""
        params = []
        
        # 查找参数模式
        param_patterns = [
            r"Parameter: (\w+)",
            r"GET parameter '(\w+)'",
            r"POST parameter '(\w+)'"
        ]
        
        for pattern in param_patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            params.extend(matches)
        
        return list(set(params))  # 去重
    
    def _extract_database_info(self, output: str) -> Dict:
        """提取数据库信息"""
        info = {}
        
        # 数据库类型
        db_patterns = [
            (r"back-end DBMS: (\w+)", "type"),
            (r"web server operating system: ([^\n]+)", "os"),
            (r"web application technology: ([^\n]+)", "technology")
        ]
        
        for pattern, key in db_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                info[key] = match.group(1).strip()
        
        return info
    
    def _extract_payload(self, output: str, param: str) -> Optional[str]:
        """提取攻击载荷"""
        # 查找载荷模式
        payload_patterns = [
            rf"{param}=([^&\s]+)",
            r"Payload: ([^\n]+)"
        ]
        
        for pattern in payload_patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_evidence(self, output: str) -> str:
        """提取证据信息"""
        evidence_lines = []
        
        # 提取关键行
        lines = output.split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in [
                "vulnerable", "injectable", "payload", "parameter"
            ]):
                evidence_lines.append(line.strip())
        
        return '\n'.join(evidence_lines[:10])  # 限制行数
    
    def _extract_waf_info(self, output: str) -> str:
        """提取WAF信息"""
        waf_lines = []
        
        lines = output.split('\n')
        for line in lines:
            if "WAF" in line or "firewall" in line.lower():
                waf_lines.append(line.strip())
        
        return '\n'.join(waf_lines)
    
    async def check_available(self) -> bool:
        """检查 SQLMap 是否可用"""
        try:
            import sys
            import site
            
            # 动态检测Python路径
            python_paths = [
                sys.executable,  # 当前Python解释器
                "python",
                "python3"
            ]
            
            # 添加常见虚拟环境路径
            common_python_paths = [
                "E:\\Interpreter\\Python_Conda\\envs\\Ai_Test_Agent\\python.exe",
                "E:\\Interpreter\\Python_Conda\\envs\\Ai_Test_Agent\\Scripts\\python.exe"
            ]
            python_paths.extend(common_python_paths)
            
            # 动态检测SQLMap脚本路径
            possible_sqlmap_paths = []
            
            # 检查当前Python环境的site-packages
            for site_dir in site.getsitepackages():
                sqlmap_path = os.path.join(site_dir, "sqlmap", "sqlmap.py")
                if os.path.exists(sqlmap_path):
                    possible_sqlmap_paths.append(sqlmap_path)
            
            # 添加常见SQLMap路径
            common_sqlmap_paths = [
                "E:\\Interpreter\\Python_Conda\\envs\\Ai_Test_Agent\\Lib\\site-packages\\sqlmap\\sqlmap.py"
            ]
            possible_sqlmap_paths.extend(common_sqlmap_paths)
            
            # 测试Python和SQLMap组合
            for python_path in python_paths:
                for sqlmap_script in possible_sqlmap_paths:
                    if os.path.exists(sqlmap_script):
                        try:
                            process = await asyncio.create_subprocess_exec(
                                python_path, sqlmap_script, "--version",
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            stdout, stderr = await process.communicate()
                            
                            if process.returncode == 0:
                                version_info = stdout.decode().strip()
                                logger.info(f"找到 SQLMap: {python_path} + {sqlmap_script}, 版本: {version_info}")
                                self.python_path = python_path
                                self.sqlmap_script = sqlmap_script
                                return True
                        except Exception:
                            continue
            
            # 尝试模块方式调用
            for python_path in python_paths:
                try:
                    process = await asyncio.create_subprocess_exec(
                        python_path, "-m", "sqlmap", "--version",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        version_info = stdout.decode().strip()
                        logger.info(f"找到 SQLMap (模块方式): {python_path}, 版本: {version_info}")
                        self.python_path = python_path
                        self.sqlmap_script = "-m sqlmap"  # 特殊标记
                        return True
                except Exception:
                    continue
            
            logger.warning("未找到 SQLMap 工具")
            return False
        except Exception as e:
            logger.error(f"检查 SQLMap 可用性失败: {e}")
            return False
    
    async def verify_injection(self, url: str, param: str = None) -> Dict:
        """验证SQL注入漏洞"""
        config = {
            "level": 2,
            "risk": 2,
            "timeout": 120
        }
        
        if param:
            # 只测试指定参数
            config["testparameter"] = param
        
        results = await self.run(url, config)
        
        return {
            "injectable": len(results) > 0,
            "results": results,
            "raw_output": results[0].get("raw_output", "") if results else ""
        }