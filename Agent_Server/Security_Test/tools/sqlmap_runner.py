"""
SQLMap 扫描工具封装

SQLMap 是一个自动化 SQL 注入检测和利用工具

作者: 程序员Eighteen
"""
import json
import logging
import os
import shutil
import tempfile
from typing import Dict, List, Optional

from .base_runner import BaseScanRunner

logger = logging.getLogger(__name__)


class SqlmapRunner(BaseScanRunner):
    """SQLMap 扫描器"""
    
    def __init__(self):
        super().__init__()
        self.tool_name = "sqlmap"
    
    async def check_available(self) -> Dict:
        """检查 sqlmap 是否安装"""
        sqlmap_path = shutil.which("sqlmap")
        
        if not sqlmap_path:
            return {
                "available": False,
                "version": None,
                "message": "sqlmap 未安装，请运行: pip install sqlmap 或从 https://sqlmap.org/ 下载"
            }
        
        # 获取版本
        returncode, stdout, stderr = await self._execute_command(
            ["sqlmap", "--version"],
            timeout=10
        )
        
        version = "unknown"
        if returncode == 0 and stdout:
            version = stdout.strip()
        
        return {
            "available": True,
            "version": version,
            "message": f"sqlmap 已安装: {sqlmap_path}"
        }
    
    async def run_scan(
        self, 
        target: str, 
        config: Optional[Dict] = None
    ) -> List[Dict]:
        """
        执行 sqlmap 扫描
        
        Args:
            target: 目标URL
            config: 配置参数
                - level: 测试级别 (1-5)
                - risk: 风险级别 (1-3)
                - technique: 注入技术 (B,E,U,S,T,Q)
                - timeout: 超时时间
        
        Returns:
            漏洞列表
        """
        config = config or {}
        
        # 创建临时输出目录
        output_dir = tempfile.mkdtemp(prefix="sqlmap_")
        
        try:
            # 构建命令
            cmd = [
                "sqlmap",
                "-u", target,
                "--batch",  # 非交互模式
                "--output-dir", output_dir,
                "--flush-session",  # 清除会话
            ]
            
            # 测试级别
            level = config.get("level", 2)
            cmd.extend(["--level", str(level)])
            
            # 风险级别
            risk = config.get("risk", 1)
            cmd.extend(["--risk", str(risk)])
            
            # 注入技术
            if config.get("technique"):
                cmd.extend(["--technique", config["technique"]])
            
            # 超时时间
            timeout = config.get("timeout", 300)
            
            logger.info(f"[SQLMap] 开始扫描: {target}")
            logger.debug(f"[SQLMap] 命令: {' '.join(cmd)}")
            
            # 执行扫描
            returncode, stdout, stderr = await self._execute_command(
                cmd,
                timeout=timeout + 60
            )
            
            # 解析结果
            results = self._parse_output(stdout, stderr, target)
            
            logger.info(f"[SQLMap] 扫描完成，发现 {len(results)} 个漏洞")
            
            return results
            
        finally:
            # 清理临时目录
            try:
                shutil.rmtree(output_dir, ignore_errors=True)
            except:
                pass
    
    def _parse_output(
        self, 
        stdout: str, 
        stderr: str, 
        target: str
    ) -> List[Dict]:
        """
        解析 sqlmap 输出
        
        Args:
            stdout: 标准输出
            stderr: 标准错误
            target: 目标URL
            
        Returns:
            标准化的漏洞列表
        """
        results = []
        output = stdout + stderr
        
        # 检查是否发现注入
        if "sqlmap identified the following injection point" in output.lower():
            # 提取注入点信息
            injection_info = self._extract_injection_info(output)
            
            for info in injection_info:
                result = {
                    "severity": "high",  # SQL 注入默认为高危
                    "title": f"SQL 注入漏洞 - {info.get('type', 'Unknown')}",
                    "description": f"在参数 {info.get('param', 'unknown')} 发现 SQL 注入漏洞",
                    "url": target,
                    "param": info.get("param", ""),
                    "payload": info.get("payload", ""),
                    "evidence": info.get("evidence", ""),
                    "raw_output": output[:1000]  # 限制长度
                }
                results.append(result)
        
        elif "all tested parameters do not appear to be injectable" in output.lower():
            logger.info(f"[SQLMap] 未发现 SQL 注入: {target}")
        
        return results
    
    def _extract_injection_info(self, output: str) -> List[Dict]:
        """
        从输出中提取注入点信息
        
        Args:
            output: sqlmap 输出
            
        Returns:
            注入点信息列表
        """
        injections = []
        
        lines = output.split('\n')
        current_injection = {}
        
        for line in lines:
            line = line.strip()
            
            # 提取参数名
            if "Parameter:" in line:
                param = line.split("Parameter:")[-1].strip()
                current_injection["param"] = param
            
            # 提取注入类型
            if "Type:" in line:
                inj_type = line.split("Type:")[-1].strip()
                current_injection["type"] = inj_type
            
            # 提取 Payload
            if "Payload:" in line:
                payload = line.split("Payload:")[-1].strip()
                current_injection["payload"] = payload
            
            # 提取证据
            if "---" in line and current_injection:
                current_injection["evidence"] = output
                injections.append(current_injection.copy())
                current_injection = {}
        
        # 添加最后一个
        if current_injection:
            current_injection["evidence"] = output
            injections.append(current_injection)
        
        return injections
