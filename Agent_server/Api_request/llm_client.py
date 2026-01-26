import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from Api_request.prompts import (
    BUILD_TESTS_SYSTEM, 
    BUILD_TESTS_USER_TEMPLATE,
    REPORT_SYSTEM,
    REPORT_USER_SINGLE_CASE,
    REPORT_USER_MULTIPLE_CASES,
    BUG_ANALYSIS_SYSTEM
)

# 导入模型配置管理器
from Model_manage.config_manager import get_active_llm_config


class LLMClient:
    """LLM Client for API calls - 使用数据库中的模型配置"""
    
    def __init__(self):
        self.client = None  # 延迟初始化
        self._config = None  # 缓存配置
    
    def _get_config(self):
        """获取模型配置"""
        try:
            self._config = get_active_llm_config()
            return self._config
        except Exception as e:
            print(f"[LLMClient] 获取数据库模型配置失败: {e}")
            print(f"[LLMClient] 回退到环境变量配置")
            # 回退到环境变量
            return {
                'base_url': os.getenv('LLM_BASE_URL'),
                'api_key': os.getenv('LLM_API_KEY'),
                'model_name': os.getenv('LLM_MODEL')
            }
    
    def _ensure_client(self):
        """[延迟初始化] 确保客户端已初始化"""
        if self.client is None:
            config = self._get_config()
            try:
                self.client = OpenAI(
                    base_url=config['base_url'],
                    api_key=config['api_key']
                )
            except TypeError as e:
                # 处理 OpenAI 库版本兼容性问题
                if 'unexpected keyword' in str(e) or 'proxies' in str(e):
                    print(f"\n错误: OpenAI 库版本兼容性问题")
                    print(f"详情: {str(e)}")
                    print(f"\n处理方案: 执行以下命令升级 OpenAI 库:")
                    print(f"  pip install --upgrade openai\n")
                    raise RuntimeError(
                        f"OpenAI 库不兼容。请执行: pip install --upgrade openai"
                    )
                else:
                    raise
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Send chat request to LLM
        
        Args:
            messages: Message list, format: [{"role": "user", "content": "..."}]
            temperature: Temperature parameter
            max_tokens: Maximum token count
            response_format: Response format, e.g., {"type": "json_object"}
        
        Returns:
            LLM response content
        """
        self._ensure_client()  # 确保客户端已初始化
        config = self._get_config()
        try:
            kwargs = {
                "model": config['model_name'],
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            if response_format:
                kwargs["response_format"] = response_format
            
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        
        except Exception as e:
            print(f"LLM request error: {str(e)}")
            raise
    
    def generate_test_cases(
        self,
        requirement: str,
        count: int = 3,
        priority: str = "3"
    ) -> Dict[str, Any]:
        """
        Generate test cases based on requirements
        
        Args:
            requirement: User requirements or test points
            count: Number of test cases to generate
            priority: Default priority (1-4, default is 3)
        
        Returns:
            Generated test case data with success flag
        """
        # Use default template fields
        template_fields = [
            "module", "title", "precondition", "steps", "expected",
            "keywords", "priority", "case_type", "stage"
        ]
        
        # 使用 prompts.py 中的模板
        user_prompt = BUILD_TESTS_USER_TEMPLATE.format(
            requirement=requirement,
            template_fields=', '.join(template_fields)
        )
        
        messages = [
            {"role": "system", "content": BUILD_TESTS_SYSTEM},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.chat(
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response)
            return {
                "success": True,
                **result  # Include test_cases from LLM response
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "test_cases": []
            }
    
    
    def generate_test_report(
        self,
        test_results: List[Dict[str, Any]],
        summary: Dict[str, Any],
        format_type: str = "markdown"
    ) -> Dict[str, Any]:
        """
        Generate test report based on test results
        
        Args:
            test_results: Test result list
            summary: Test summary data
            format_type: Report format (markdown/html/text)
        
        Returns:
            Dict with success flag and report content
        """
        # 判断是单个用例还是多个用例
        total_cases = summary.get('total', len(test_results))
        is_single_case = total_cases == 1
        
        # 格式化测试结果为 JSON 字符串
        test_results_json = json.dumps(test_results, ensure_ascii=False, indent=2)
        
        # 根据用例数量选择不同的模板
        if is_single_case:
            user_prompt = REPORT_USER_SINGLE_CASE.format(
                test_results=test_results_json,
                format_type=format_type.upper()
            )
        else:
            user_prompt = REPORT_USER_MULTIPLE_CASES.format(
                total=summary.get('total', 0),
                pass_count=summary.get('pass', 0),
                fail_count=summary.get('fail', 0),
                duration=summary.get('duration', 0),
                test_results=test_results_json,
                format_type=format_type.upper()
            )
        
        messages = [
            {"role": "system", "content": REPORT_SYSTEM},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = self.chat(
                messages=messages,
                temperature=0.3
            )
            
            return {
                "success": True,
                "content": response
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "content": ""
            }
    
    def analyze_bug(self, analysis_prompt: str) -> Dict[str, Any]:
        """
        分析 Bug 并返回结构化数据
        
        Args:
            analysis_prompt: Bug 分析提示
        
        Returns:
            Dict with success flag and bug analysis data
        """
        messages = [
            {"role": "system", "content": BUG_ANALYSIS_SYSTEM},
            {"role": "user", "content": analysis_prompt}
        ]
        
        try:
            response = self.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=2000
            )
            
            # 尝试解析 JSON
            try:
                # 清理可能的 markdown 代码块标记
                cleaned_response = response.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.startswith('```'):
                    cleaned_response = cleaned_response[3:]
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()
                
                bug_data = json.loads(cleaned_response)
                
                return {
                    "success": True,
                    "data": bug_data
                }
            except json.JSONDecodeError as e:
                print(f"[LLM] JSON 解析失败: {str(e)}")
                print(f"[LLM] 原始响应: {response}")
                
                # 返回默认值
                return {
                    "success": True,
                    "data": {
                        "error_type": "系统错误",
                        "severity_level": "一级",
                        "actual_result": response,
                        "result_feedback": "LLM 返回格式异常，无法解析"
                    }
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "data": {}
            }


# Global instance - 延迟初始化
_llm_client_instance = None

def get_llm_client() -> 'LLMClient':
    """获取 LLM 客户端实例（延迟初始化）"""
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance