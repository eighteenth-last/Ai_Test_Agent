"""
Nuclei 扫描工具封装 - 使用最新版本

支持 Nuclei v3.x 的最新功能和模板

作者: Ai_Test_Agent Team
"""
import asyncio
import json
import logging
import subprocess
import tempfile
import os
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class NucleiRunner:
    """Nuclei 扫描器 - 最新版本"""
    
    def __init__(self):
        self.tool_name = "nuclei"
        self.version = "v3.x"
        self.nuclei_path = None  # 动态检测路径
    
    async def run(self, target: str, config: Dict = None) -> List[Dict]:
        """
        运行 Nuclei 扫描
        
        Args:
            target: 扫描目标URL
            config: 扫描配置
            
        Returns:
            List[Dict]: 扫描结果列表
        """
        config = config or {}
        
        # 创建临时输出文件
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
            output_file = temp_file.name
        
        try:
            # 构建命令
            cmd = [
                self.nuclei_path or "nuclei",  # 使用检测到的路径或默认
                "-u", target,
                "-json",
                "-silent",
                "-o", output_file
            ]
            
            # 添加模板配置
            templates = config.get("templates", ["cves/", "vulnerabilities/", "exposures/", "misconfiguration/"])
            if isinstance(templates, str):
                templates = [templates]
            
            for template in templates:
                cmd.extend(["-t", template])
            
            # 添加严重程度过滤
            severity = config.get("severity", ["critical", "high", "medium"])
            if severity:
                cmd.extend(["-s", ",".join(severity)])
            
            # 添加其他参数
            if config.get("rate_limit"):
                cmd.extend(["-rl", str(config["rate_limit"])])
            else:
                cmd.extend(["-rl", "150"])  # 默认限速
            
            if config.get("timeout"):
                cmd.extend(["-timeout", str(config["timeout"])])
            else:
                cmd.extend(["-timeout", "10"])  # 默认超时
            
            if config.get("retries"):
                cmd.extend(["-retries", str(config["retries"])])
            
            if config.get("concurrency"):
                cmd.extend(["-c", str(config["concurrency"])])
            else:
                cmd.extend(["-c", "25"])  # 默认并发
            
            # 添加用户代理
            cmd.extend(["-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"])
            
            # 跳过SSL验证
            if config.get("skip_ssl_verify", True):
                cmd.append("-verify-ssl=false")
            
            # 添加代理支持
            if config.get("proxy"):
                cmd.extend(["-proxy", config["proxy"]])
            
            logger.info(f"执行 Nuclei 命令: {' '.join(cmd)}")
            
            # 异步执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Nuclei 执行失败: {stderr.decode()}")
                return []
            
            # 读取输出文件
            results = []
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                result = json.loads(line)
                                parsed_result = self._parse_nuclei_result(result)
                                if parsed_result:
                                    results.append(parsed_result)
                            except json.JSONDecodeError as e:
                                logger.warning(f"无法解析 Nuclei 输出: {line}, 错误: {e}")
            
            logger.info(f"Nuclei 扫描完成，发现 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"Nuclei 扫描异常: {e}")
            return []
        finally:
            # 清理临时文件
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def _parse_nuclei_result(self, result: Dict) -> Optional[Dict]:
        """解析 Nuclei v3.x 扫描结果"""
        try:
            info = result.get("info", {})
            
            # 映射严重程度
            severity_map = {
                "critical": "critical",
                "high": "high", 
                "medium": "medium",
                "low": "low",
                "info": "info",
                "unknown": "info"
            }
            
            severity = severity_map.get(info.get("severity", "info").lower(), "info")
            
            # 确定漏洞类型
            vuln_type = self._get_vuln_type(info.get("tags", []), info.get("name", ""))
            
            # 提取匹配信息
            matched_at = result.get("matched-at", "")
            template_id = result.get("template-id", "")
            
            # 提取请求响应信息
            curl_command = result.get("curl-command", "")
            
            return {
                "tool": "nuclei",
                "severity": severity,
                "title": info.get("name", "Unknown Vulnerability"),
                "description": info.get("description", ""),
                "vuln_type": vuln_type,
                "url": matched_at,
                "template_id": template_id,
                "evidence": json.dumps(result, ensure_ascii=False),
                "raw_output": json.dumps(result, ensure_ascii=False),
                "cve_id": self._extract_cve_id(info.get("tags", [])),
                "reference": info.get("reference", []),
                "curl_command": curl_command,
                "classification": info.get("classification", {}),
                "metadata": info.get("metadata", {})
            }
            
        except Exception as e:
            logger.error(f"解析 Nuclei 结果失败: {e}")
            return None
    
    def _get_vuln_type(self, tags: List[str], name: str) -> str:
        """根据标签和名称确定漏洞类型"""
        name_lower = name.lower()
        tags_str = " ".join(tags).lower()
        
        # 更精确的漏洞类型识别
        if any(tag in tags_str for tag in ["sqli", "sql-injection"]) or "sql" in name_lower:
            return "sql_injection"
        elif any(tag in tags_str for tag in ["xss", "cross-site-scripting"]) or "xss" in name_lower:
            return "xss"
        elif any(tag in tags_str for tag in ["lfi", "local-file-inclusion"]) or "lfi" in name_lower:
            return "lfi"
        elif any(tag in tags_str for tag in ["rfi", "remote-file-inclusion"]) or "rfi" in name_lower:
            return "rfi"
        elif any(tag in tags_str for tag in ["csrf", "cross-site-request-forgery"]) or "csrf" in name_lower:
            return "csrf"
        elif any(tag in tags_str for tag in ["ssrf", "server-side-request-forgery"]) or "ssrf" in name_lower:
            return "ssrf"
        elif any(tag in tags_str for tag in ["rce", "remote-code-execution", "code-injection"]) or "rce" in name_lower:
            return "rce"
        elif any(tag in tags_str for tag in ["xxe", "xml-external-entity"]) or "xxe" in name_lower:
            return "xxe"
        elif any(tag in tags_str for tag in ["idor", "insecure-direct-object-reference"]) or "idor" in name_lower:
            return "idor"
        elif any(tag in tags_str for tag in ["disclosure", "exposure", "leak"]) or "disclosure" in name_lower:
            return "information_disclosure"
        elif any(tag in tags_str for tag in ["misconfig", "misconfiguration"]) or "config" in name_lower:
            return "misconfiguration"
        elif "cve" in tags_str:
            return "cve"
        elif any(tag in tags_str for tag in ["dos", "denial-of-service"]) or "dos" in name_lower:
            return "dos"
        elif any(tag in tags_str for tag in ["auth", "authentication", "bypass"]) or "auth" in name_lower:
            return "authentication_bypass"
        else:
            return "other"
    
    def _extract_cve_id(self, tags: List[str]) -> Optional[str]:
        """提取 CVE ID"""
        for tag in tags:
            if tag.upper().startswith("CVE-"):
                return tag.upper()
        return None
    
    async def check_available(self) -> bool:
        """检查 Nuclei 是否可用"""
        try:
            # 动态检测可能的路径
            nuclei_paths = [
                "nuclei",  # 系统PATH中
                "nuclei.exe"
            ]
            
            # 添加Go相关路径
            import os
            import subprocess
            
            # 获取Go环境变量
            try:
                result = subprocess.run(["go", "env", "GOPATH"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    gopath = result.stdout.strip()
                    if gopath:
                        nuclei_paths.extend([
                            os.path.join(gopath, "bin", "nuclei"),
                            os.path.join(gopath, "bin", "nuclei.exe")
                        ])
            except:
                pass
            
            # 添加常见Go安装路径
            common_go_paths = [
                "E:\\GoLang\\bin\\nuclei.exe",
                "E:\\GoLang\\GoModulesCache\\bin\\nuclei.exe", 
                "C:\\Go\\bin\\nuclei.exe",
                os.path.expanduser("~/go/bin/nuclei"),
                os.path.expanduser("~/go/bin/nuclei.exe")
            ]
            nuclei_paths.extend(common_go_paths)
            
            # 检查每个路径
            for nuclei_path in nuclei_paths:
                try:
                    process = await asyncio.create_subprocess_exec(
                        nuclei_path, "-version",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        version_info = stdout.decode().strip()
                        logger.info(f"找到 Nuclei: {nuclei_path}, 版本: {version_info}")
                        # 保存正确路径
                        self.nuclei_path = nuclei_path
                        return True
                except Exception:
                    continue
            
            logger.warning("未找到 Nuclei 工具")
            return False
        except Exception as e:
            logger.error(f"检查 Nuclei 可用性失败: {e}")
            return False
    
    async def update_templates(self) -> bool:
        """更新 Nuclei 模板"""
        try:
            logger.info("正在更新 Nuclei 模板...")
            process = await asyncio.create_subprocess_exec(
                "nuclei", "-update-templates",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info("Nuclei 模板更新成功")
                return True
            else:
                logger.error(f"Nuclei 模板更新失败: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"更新 Nuclei 模板异常: {e}")
            return False
    
    def get_template_categories(self) -> List[str]:
        """获取可用的模板分类"""
        return [
            "cves/",                    # CVE 漏洞
            "vulnerabilities/",         # 已知漏洞
            "exposures/",              # 信息泄露
            "misconfiguration/",       # 配置错误
            "takeovers/",              # 子域接管
            "default-logins/",         # 默认登录
            "file/",                   # 文件相关
            "network/",                # 网络服务
            "dns/",                    # DNS 相关
            "headless/",               # 无头浏览器
            "ssl/",                    # SSL/TLS
            "technologies/",           # 技术识别
            "fuzzing/",                # 模糊测试
            "cnvd/",                   # CNVD 漏洞
            "token-spray/",            # Token 喷射
            "iot/"                     # IoT 设备
        ]