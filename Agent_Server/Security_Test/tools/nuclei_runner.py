"""
Nuclei 扫描工具封装

Nuclei 是一个基于模板的快速漏洞扫描器

作者: 程序员Eighteen
"""
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from .base_runner import BaseScanRunner

logger = logging.getLogger(__name__)


class NucleiRunner(BaseScanRunner):
    """Nuclei 扫描器"""
    
    def __init__(self):
        super().__init__()
        self.tool_name = "nuclei"
        self.nuclei_path = self._get_nuclei_path()
        self.templates_path = self._get_templates_path()
    
    def _get_nuclei_path(self) -> Optional[str]:
        """获取 nuclei 可执行文件路径"""
        # 1. 从环境变量获取
        env_path = os.getenv("NUCLEI_PATH")
        if env_path and os.path.exists(env_path):
            logger.info(f"[Nuclei] 使用环境变量配置的路径: {env_path}")
            return env_path
        
        # 2. 从 PATH 查找
        nuclei_path = shutil.which("nuclei")
        if nuclei_path:
            logger.info(f"[Nuclei] 从 PATH 找到: {nuclei_path}")
            return nuclei_path
        
        # 3. 尝试常见路径
        common_paths = [
            # Windows Go modules cache
            Path(os.path.expandvars(r"%USERPROFILE%\go\bin\nuclei.exe")),
            Path(os.path.expandvars(r"E:\GoLang\GoModulesCache\bin\nuclei.exe")),
            # Linux/Mac
            Path("/usr/local/bin/nuclei"),
            Path(os.path.expanduser("~/go/bin/nuclei")),
        ]
        
        for path in common_paths:
            if path.exists():
                logger.info(f"[Nuclei] 从常见路径找到: {path}")
                return str(path)
        
        logger.warning("[Nuclei] 未找到 nuclei 可执行文件")
        return None
    
    def _get_templates_path(self) -> Optional[str]:
        """获取 nuclei 模板路径"""
        # 1. 从环境变量获取
        env_path = os.getenv("NUCLEI_TEMPLATES_PATH")
        if env_path and os.path.exists(env_path):
            logger.info(f"[Nuclei] 使用环境变量配置的模板路径: {env_path}")
            return env_path
        
        # 2. 尝试常见路径
        common_paths = [
            # 项目源代码目录
            Path(r"r:\Code\Python\Python_selenium_test_Agent\Ai_Test_Agent\安全测试源代码\nuclei-templates-main\nuclei-templates-main"),
            # 默认模板路径
            Path(os.path.expanduser("~/.nuclei-templates")),
            Path(os.path.expanduser("~/nuclei-templates")),
        ]
        
        for path in common_paths:
            if path.exists() and path.is_dir():
                logger.info(f"[Nuclei] 从常见路径找到模板: {path}")
                return str(path)
        
        logger.info("[Nuclei] 未配置模板路径，将使用默认模板")
        return None
    
    async def check_available(self) -> Dict:
        """检查 nuclei 是否安装"""
        if not self.nuclei_path:
            return {
                "available": False,
                "version": None,
                "message": "nuclei 未安装，请配置 NUCLEI_PATH 环境变量或运行: go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
            }
        
        # 获取版本
        returncode, stdout, stderr = await self._execute_command(
            [self.nuclei_path, "-version"],
            timeout=10
        )
        
        version = "unknown"
        if returncode == 0 and stdout:
            # 解析版本号
            for line in stdout.split('\n'):
                if 'nuclei' in line.lower():
                    version = line.strip()
                    break
        
        message = f"nuclei 已安装: {self.nuclei_path}"
        if self.templates_path:
            message += f"\n模板路径: {self.templates_path}"
        
        return {
            "available": True,
            "version": version,
            "message": message
        }
    
    async def run_scan(
        self, 
        target: str, 
        config: Optional[Dict] = None
    ) -> List[Dict]:
        """
        执行 nuclei 扫描
        
        Args:
            target: 目标URL
            config: 配置参数
                - severity: 严重程度过滤 (critical,high,medium,low,info)
                - templates: 模板路径
                - rate_limit: 速率限制
                - timeout: 超时时间
        
        Returns:
            漏洞列表
        """
        if not self.nuclei_path:
            logger.error("[Nuclei] nuclei 不可用")
            return []
        
        config = config or {}
        
        # 构建命令
        cmd = [
            self.nuclei_path,
            "-u", target,
            "-json",  # JSON 输出
            "-silent",  # 静默模式
        ]
        
        # 严重程度过滤
        severity = config.get("severity", "critical,high,medium,low")
        cmd.extend(["-severity", severity])
        
        # 模板路径（优先使用配置的，其次使用环境变量的）
        templates = config.get("templates") or self.templates_path
        if templates:
            cmd.extend(["-t", templates])
        
        # 速率限制
        rate_limit = config.get("rate_limit", 150)
        cmd.extend(["-rate-limit", str(rate_limit)])
        
        # 超时时间
        timeout = config.get("timeout", 300)
        cmd.extend(["-timeout", str(timeout)])
        
        logger.info(f"[Nuclei] 开始扫描: {target}")
        logger.debug(f"[Nuclei] 命令: {' '.join(cmd)}")
        
        # 执行扫描
        returncode, stdout, stderr = await self._execute_command(
            cmd,
            timeout=timeout + 60
        )
        
        if returncode != 0 and not stdout:
            logger.error(f"[Nuclei] 扫描失败: {stderr}")
            return []
        
        # 解析结果
        results = self._parse_output(stdout, target)
        
        logger.info(f"[Nuclei] 扫描完成，发现 {len(results)} 个漏洞")
        
        return results
    
    def _parse_output(self, output: str, target: str) -> List[Dict]:
        """
        解析 nuclei JSON 输出
        
        Args:
            output: nuclei 输出
            target: 目标URL
            
        Returns:
            标准化的漏洞列表
        """
        results = []
        
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
            
            try:
                data = json.loads(line)
                
                # 提取信息
                template_id = data.get("template-id", "unknown")
                info = data.get("info", {})
                matched_at = data.get("matched-at", target)
                
                # 提取参数
                extracted_results = data.get("extracted-results", [])
                param = ", ".join(extracted_results) if extracted_results else ""
                
                # 构建标准化结果
                result = {
                    "severity": self._normalize_severity(info.get("severity", "info")),
                    "title": info.get("name", template_id),
                    "description": info.get("description", ""),
                    "url": matched_at,
                    "param": param,
                    "payload": "",
                    "evidence": json.dumps(data, ensure_ascii=False, indent=2),
                    "raw_output": line
                }
                
                results.append(result)
                
            except json.JSONDecodeError as e:
                logger.warning(f"[Nuclei] JSON 解析失败: {e}, line: {line[:100]}")
                continue
            except Exception as e:
                logger.error(f"[Nuclei] 解析结果失败: {e}")
                continue
        
        return results
