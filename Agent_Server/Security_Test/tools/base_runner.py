"""
扫描工具基类

定义统一的扫描工具接口

作者: 程序员Eighteen
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseScanRunner(ABC):
    """扫描工具基类"""
    
    def __init__(self):
        self.tool_name = "base"
        self.version = "unknown"
    
    @abstractmethod
    async def check_available(self) -> Dict:
        """
        检查工具是否可用
        
        Returns:
            {
                "available": bool,
                "version": str,
                "message": str
            }
        """
        pass
    
    @abstractmethod
    async def run_scan(
        self, 
        target: str, 
        config: Optional[Dict] = None
    ) -> List[Dict]:
        """
        执行扫描
        
        Args:
            target: 扫描目标URL
            config: 扫描配置参数
            
        Returns:
            List[{
                "severity": str,  # critical/high/medium/low/info
                "title": str,
                "description": str,
                "url": str,
                "param": str,
                "payload": str,
                "evidence": str,
                "raw_output": str
            }]
        """
        pass
    
    async def _execute_command(
        self, 
        cmd: List[str], 
        timeout: int = 300
    ) -> tuple[int, str, str]:
        """
        执行命令行工具
        
        Args:
            cmd: 命令列表
            timeout: 超时时间(秒)
            
        Returns:
            (returncode, stdout, stderr)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return (
                process.returncode,
                stdout.decode('utf-8', errors='ignore'),
                stderr.decode('utf-8', errors='ignore')
            )
            
        except asyncio.TimeoutError:
            logger.error(f"命令执行超时: {' '.join(cmd)}")
            try:
                process.kill()
            except:
                pass
            return (-1, "", "执行超时")
            
        except Exception as e:
            logger.error(f"命令执行失败: {e}")
            return (-1, "", str(e))
    
    def _normalize_severity(self, severity: str) -> str:
        """
        标准化严重程度
        
        Args:
            severity: 原始严重程度
            
        Returns:
            标准化后的严重程度: critical/high/medium/low/info
        """
        severity_lower = severity.lower()
        
        # 映射表
        severity_map = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "info": "info",
            "informational": "info",
            # nuclei 映射
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "info": "info",
            # sqlmap 映射
            "error": "high",
            "warning": "medium",
            "note": "low",
            # 其他常见映射
            "severe": "critical",
            "important": "high",
            "moderate": "medium",
            "minor": "low",
        }
        
        return severity_map.get(severity_lower, "info")
