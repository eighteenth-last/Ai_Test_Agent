"""
XSStrike 扫描工具封装

XSStrike 是一个高级 XSS 检测工具

作者: 程序员Eighteen
"""
import json
import logging
import re
import shutil
from typing import Dict, List, Optional

from .base_runner import BaseScanRunner

logger = logging.getLogger(__name__)


class XSStrikeRunner(BaseScanRunner):
    """XSStrike 扫描器"""
    
    def __init__(self):
        super().__init__()
        self.tool_name = "xsstrike"
    
    async def check_available(self) -> Dict:
        """检查 xsstrike 是否安装"""
        # XSStrike 通常通过 python 脚本运行
        xsstrike_path = shutil.which("xsstrike")
        
        if not xsstrike_path:
            # 尝试查找 xsstrike.py
            import os
            possible_paths = [
                "/usr/local/bin/xsstrike.py",
                "/opt/XSStrike/xsstrike.py",
                os.path.expanduser("~/XSStrike/xsstrike.py")
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    xsstrike_path = path
                    break
        
        if not xsstrike_path:
            return {
                "available": False,
                "version": None,
                "message": "XSStrike 未安装，请从 https://github.com/s0md3v/XSStrike 克隆并安装"
            }
        
        return {
            "available": True,
            "version": "3.1.5",  # XSStrike 版本
            "message": f"XSStrike 已安装: {xsstrike_path}"
        }
    
    async def run_scan(
        self, 
        target: str, 
        config: Optional[Dict] = None
    ) -> List[Dict]:
        """
        执行 XSStrike 扫描
        
        Args:
            target: 目标URL
            config: 配置参数
                - crawl: 是否爬取 (True/False)
                - timeout: 超时时间
        
        Returns:
            漏洞列表
        """
        config = config or {}
        
        # 查找 xsstrike.py
        xsstrike_path = self._find_xsstrike()
        
        if not xsstrike_path:
            logger.error("[XSStrike] 未找到 xsstrike.py")
            return []
        
        # 构建命令
        cmd = [
            "python3",
            xsstrike_path,
            "-u", target,
            "--skip-dom",  # 跳过 DOM XSS（加快速度）
        ]
        
        # 是否爬取
        if config.get("crawl", False):
            cmd.append("--crawl")
        
        # 超时时间
        timeout = config.get("timeout", 300)
        
        logger.info(f"[XSStrike] 开始扫描: {target}")
        logger.debug(f"[XSStrike] 命令: {' '.join(cmd)}")
        
        # 执行扫描
        returncode, stdout, stderr = await self._execute_command(
            cmd,
            timeout=timeout + 60
        )
        
        # 解析结果
        results = self._parse_output(stdout, stderr, target)
        
        logger.info(f"[XSStrike] 扫描完成，发现 {len(results)} 个漏洞")
        
        return results
    
    def _find_xsstrike(self) -> Optional[str]:
        """查找 xsstrike.py 路径"""
        import os
        
        possible_paths = [
            "/usr/local/bin/xsstrike.py",
            "/opt/XSStrike/xsstrike.py",
            os.path.expanduser("~/XSStrike/xsstrike.py"),
            "./XSStrike/xsstrike.py"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def _parse_output(
        self, 
        stdout: str, 
        stderr: str, 
        target: str
    ) -> List[Dict]:
        """
        解析 XSStrike 输出
        
        Args:
            stdout: 标准输出
            stderr: 标准错误
            target: 目标URL
            
        Returns:
            标准化的漏洞列表
        """
        results = []
        output = stdout + stderr
        
        # XSStrike 输出特征
        xss_patterns = [
            r"XSS.*?detected",
            r"Payload.*?worked",
            r"Vulnerable.*?parameter",
        ]
        
        for pattern in xss_patterns:
            matches = re.finditer(pattern, output, re.IGNORECASE)
            for match in matches:
                # 提取上下文
                start = max(0, match.start() - 200)
                end = min(len(output), match.end() + 200)
                context = output[start:end]
                
                # 提取参数和 payload
                param = self._extract_param(context)
                payload = self._extract_payload(context)
                
                result = {
                    "severity": "medium",  # XSS 默认为中危
                    "title": "跨站脚本攻击 (XSS)",
                    "description": f"在参数 {param} 发现 XSS 漏洞",
                    "url": target,
                    "param": param,
                    "payload": payload,
                    "evidence": context,
                    "raw_output": output[:1000]
                }
                results.append(result)
                break  # 避免重复
        
        return results
    
    def _extract_param(self, text: str) -> str:
        """从文本中提取参数名"""
        param_match = re.search(r"parameter[:\s]+([a-zA-Z0-9_]+)", text, re.IGNORECASE)
        if param_match:
            return param_match.group(1)
        return "unknown"
    
    def _extract_payload(self, text: str) -> str:
        """从文本中提取 payload"""
        payload_match = re.search(r"payload[:\s]+(.+?)[\n\r]", text, re.IGNORECASE)
        if payload_match:
            return payload_match.group(1).strip()
        return ""
