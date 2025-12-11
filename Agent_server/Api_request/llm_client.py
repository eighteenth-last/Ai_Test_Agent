import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))


class LLMClient:
    """LLM Client for Qwen API calls"""
    
    def __init__(self):
        self.base_url = os.getenv('LLM_BASE_URL')
        self.api_key = os.getenv('LLM_API_KEY')
        self.model = os.getenv('LLM_MODEL')
        self.client = None  # 延迟初始化
    
    def _ensure_client(self):
        """[延迟初始化] 确保客户端已初始化"""
        if self.client is None:
            try:
                self.client = OpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key
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
        try:
            kwargs = {
                "model": self.model,
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
        priority: str = "medium"
    ) -> Dict[str, Any]:
        """
        Generate test cases based on requirements
        
        Args:
            requirement: User requirements or test points
            count: Number of test cases to generate
            priority: Default priority (high/medium/low)
        
        Returns:
            Generated test case data with success flag
        """
        # Use default template fields
        template_fields = [
            "module", "title", "precondition", "steps", "expected",
            "keywords", "priority", "case_type", "stage"
        ]
        
        system_prompt = """你是 AI 测试用例生成专家。根据需求生成结构化的测试用例，并以严格的 JSON 格式返回。

重要要求：所有输出内容必须使用中文，包括模块名、标题、步骤描述等，不要使用英文。"""
        
        user_prompt = f"""根据以下需求生成 {count} 个测试用例，每个用例遵循 template_fields：

需求：{requirement}

模板字段：{', '.join(template_fields)}

输出必须为 JSON 格式，所有内容使用中文：
{{
"test_cases": [
    {{
      "module": "模块名称",
      "title": "测试用例标题",
      "precondition": "前置条件",
      "steps": ["步骤1", "步骤2", "步骤3"],
      "expected": "预期结果",
      "keywords": "关键词1,关键词2",
      "priority": "{priority}",
      "case_type": "功能测试/接口测试/单元测试",
      "stage": "功能测试阶段/集成测试阶段/系统测试阶段"
    }}
  ]
}}

注意：
1. 模块名、标题、步骤、预期结果等所有描述性文字必须使用中文
2. 步骤描述要清晰具体，使用中文表达，例如："打开浏览器并访问登录页面"
3. 不要使用英文单词，除非是技术术语（如 URL、ID 等）
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
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
    
    def generate_test_code(
        self,
        test_case: Dict[str, Any],
        execution_style: str = "action_list"
    ) -> Dict[str, Any]:
        """
        Generate executable test code based on test case
        
        Args:
            test_case: Test case data
            execution_style: Execution style (action_list or code_snippet)
        
        Returns:
            Generated action list or code snippet
        """
        system_prompt = """你是 AI 自动化测试专家，专门生成 Selenium WebDriver 自动化测试代码。

严格规则：
1. 只能使用 Selenium 兼容的选择器语法
2. 严禁使用 Playwright 专有语法：:has-text、:text、text=、>> 等
3. 文本定位必须使用 XPath 表达式
4. CSS选择器的属性值必须使用双引号
5. 每个操作必须是原子操作（navigate/click/fill/wait_for/screenshot/finish）"""
        
        user_prompt = f"""你是自动化测试专家。根据以下测试用例和**实际提取到的页面元素**，转换为 action_list 格式。

注意：可交互的页面元素已经是从真实页面提取的，它们的 XPath 不是掉渠或假的。你必须空使用下列提取到的 XPath 和 CSS 选择器！

提取到的页面元素（实际存在）：
{self._format_page_elements(test_case.get('page_elements', []))}

测试用例：
- 标题：{test_case.get('title')}
- 前置条件：{test_case.get('precondition')}
- 步骤：{test_case.get('steps')}
- 预期结果：{test_case.get('expected')}
- 测试数据：{test_case.get('test_data', {{}})}

选择器规则（必须遵守）：

✅ 优先使用提取到的选择器：
- 使用提取的 XPath 茵: //button[text()='\u767b\u5f55']
- 使用提取的 CSS: input[name=\"username\"]

✅ 允许使用（Selenium 兼容）：
- CSS选择器：input[name=\"username\"]、button[type=\"submit\"]、#loginBtn、.btn-primary
- XPath（文本定位）：//button[text()='\u767b\u5f55']、//a[contains(text(),'\u8bfe\u7a0b')]

❌ 严禁使用（Playwright 专有）：
- text=\u767b\u5f55
- :has-text('\u6d4b\u8bd5')
- a:has-text=\"\u8bfe\u7a0b\"
- button >> text=\u63d0\u4ea4

⚠️ 密码加密处理（重要）：
- 所有密码字段的 value 必须使用 MD5 加密（32位小写）
- 示例：原始密码 \"123456\" → MD5加密后 \"e10adc3949ba59abbe56e057f20f883e\"
- 加密字段包括：password、passwd、pwd、密码等相关字段

输出必须为 JSON 格式：
{{
  \"actions\": [
    {{\"seq\":1, \"action\":\"navigate\", \"value\":\"http://example.com\", \"meta\":{{}}}},
    {{\"seq\":2, \"action\":\"fill\", \"selector\":\"/html/body/div[2]/div/div/div/div[2]/div/div[2]/div[2]/input\", \"value\":\"testuser\"}},
    {{\"seq\":3, \"action\":\"fill\", \"selector\":\"/html/body/div[2]/div/div/div/div[2]/div/div[2]/div[3]/input\", \"value\":\"e10adc3949ba59abbe56e057f20f883e\"}},
    {{\"seq\":4, \"action\":\"click\", \"selector\":\"/html/body/div[2]/div/div/div/div[2]/div/div[2]/button\"}},
    {{\"seq\":5, \"action\":\"wait_for\", \"selector\":\"//div[contains(text(),'\u6b22\u8fce')]\", \"timeout\":10000}}
  ],
  \"stop_condition\": \"\u4efb\u52a1\u5b8c\u6210\u6761\u4ef6\",
  \"metadata\": {{\"estimated_runtime_s\": 10}}
}}

重要提示：
1. **\u4e00定\u4f7f\u7528\u63d0\u53d6\u5230的选择器** - 它们是真实存在的，而不是提供的 HTML 口子或 name/id 属性
2. 优先使用 XPath（更重需），再使用 CSS 选择器
3. 密码字段的值必须是 MD5 加密后的 32 位小写字符串
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.chat(
            messages=messages,
            temperature=0.5,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response)
    
    @staticmethod
    def _format_page_elements(elements: List[Dict[str, Any]]) -> str:
        """
        Format page elements for LLM prompt
        
        Args:
            elements: List of page elements
        
        Returns:
            Formatted string for LLM
        """
        if not elements:
            return "(未提取到页面元素，请使用常见的选择器)"
        
        formatted = "可交互的页面元素列表："
        for elem in elements[:20]:  # Limit to 20 elements
            elem_type = elem.get('type', 'unknown')
            text = elem.get('text', '')
            placeholder = elem.get('placeholder', '')
            xpath = elem.get('xpath', '')
            css = elem.get('css', '')
            selector = elem.get('selector', '')  # Legacy fallback
            desc = elem.get('description', '')
            
            elem_label = text or placeholder or ''
            formatted += f"\n- [{elem_type}] {elem_label}"
            
            # Prioritize xpath, then css, then legacy selector
            if xpath:
                formatted += f" | XPath: {xpath}"
            elif css:
                formatted += f" | CSS: {css}"
            elif selector:
                formatted += f" | 选择器: {selector}"
            
            if desc:
                formatted += f" | {desc}"
        
        return formatted
    
    
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
        system_prompt = """你是 AI 测试报告生成专家。根据测试结果生成专业的测试报告。"""
        
        user_prompt = f"""根据以下测试结果生成测试报告：

测试概览：
- 总计：{summary.get('total', 0)} 个用例
- 通过：{summary.get('pass', 0)} 个
- 失败：{summary.get('fail', 0)} 个
- 总耗时：{summary.get('duration', 0)} 秒

详细结果：
{json.dumps(test_results, ensure_ascii=False, indent=2)}

请生成 {format_type.upper()} 格式的测试报告，包括：
1. 测试概览（通过率、总耗时等）
2. 每个测试用例的详细情况
3. 详细的行为分析（**重点**）：
   - 请深入分析每个用例的 `execution_log`（Agent 代理历史），提取关键操作路径。
   - 对于失败的用例，请根据 Agent 的思考过程 (`thinking`) 和操作日志，精准定位由于什么操作导致了失败，或者在哪一步无法找到元素。
4. 失败原因诊断与修复建议
5. 测试总结

要求：
- 使用中文
- 格式规范、结构清晰
- 对 `execution_log` 中的 Agent 行为进行语义化描述，不要只是罗列 JSON 数据
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
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
        system_prompt = """你是 AI Bug 分析专家。根据测试执行情况分析 Bug 的类型和严重程度。
请严格按照 JSON 格式返回结果，不要添加任何额外的文字说明。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
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