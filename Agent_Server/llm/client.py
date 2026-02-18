"""
LLM 客户端模块

提供与原有 LLMClient 兼容的接口，方便迁移

作者: Ai_Test_Agent Team
版本: 1.0
"""
import json
import logging
from typing import Any, Dict, List, Optional

from .manager import get_active_llm_config, model_config_manager
from .factory import create_llm_provider
from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLM 客户端
    
    兼容原有 LLMClient 接口，使用新的 Provider 架构
    """
    
    def __init__(self):
        self._provider: Optional[BaseLLMProvider] = None
        self._config: Optional[Dict] = None
    
    def _get_config(self) -> Dict:
        """获取模型配置"""
        if self._config is None:
            try:
                self._config = get_active_llm_config()
            except Exception as e:
                logger.error(f"[LLMClient] 获取数据库模型配置失败: {e}")
                raise
        return self._config
    
    def _ensure_provider(self):
        """确保 Provider 已初始化"""
        if self._provider is None:
            config = self._get_config()
            self._provider = create_llm_provider(
                provider=config['provider'],
                model_name=config['model_name'],
                api_key=config['api_key'],
                base_url=config['base_url'],
                temperature=config.get('temperature', 0.0),
                max_tokens=config.get('max_tokens', 128000),
            )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        response_format: Optional[Dict[str, str]] = None,
        source: str = "chat",
        session_id: int = None,
    ) -> str:
        """
        发送聊天请求（带自动切换和详细 Token 统计）
        """
        import time as _time
        self._ensure_provider()
        start_ms = int(_time.time() * 1000)
        
        try:
            response = self._provider.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format
            )
            
            duration_ms = int(_time.time() * 1000) - start_ms

            # 更新 token 使用量（增强版）
            model_config_manager.increment_token_usage(
                tokens=response.total_tokens,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                source=source,
                session_id=session_id,
                success=True,
                duration_ms=duration_ms,
            )
            
            return response.content
            
        except Exception as e:
            duration_ms = int(_time.time() * 1000) - start_ms
            logger.error(f"[LLMClient] 请求失败: {e}")

            # 记录失败的 token 使用
            model_config_manager.increment_token_usage(
                tokens=0,
                prompt_tokens=0,
                completion_tokens=0,
                source=source,
                session_id=session_id,
                success=False,
                error_type=str(type(e).__name__),
                duration_ms=duration_ms,
            )

            # 尝试自动切换
            try:
                from llm.auto_switch import get_auto_switcher, classify_failure_reason
                switcher = get_auto_switcher()
                # 确保 profiles 已加载（首次调用时可能为空）
                if not switcher._profiles:
                    switcher.load_profiles_from_db()
                if switcher.enabled and self._config and len(switcher._profiles) > 1:
                    reason = classify_failure_reason(e)
                    current_id = self._config.get('id', 0)
                    new_id = switcher.mark_failure(current_id, reason)
                    if new_id and new_id != current_id:
                        logger.info(f"[LLMClient] 🔄 自动切换: ID={current_id} → ID={new_id}，重试请求")
                        self.refresh()
                        self._ensure_provider()
                        response = self._provider.chat(
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            response_format=response_format
                        )
                        retry_duration = int(_time.time() * 1000) - start_ms
                        model_config_manager.increment_token_usage(
                            tokens=response.total_tokens,
                            prompt_tokens=response.prompt_tokens,
                            completion_tokens=response.completion_tokens,
                            source=source,
                            session_id=session_id,
                            success=True,
                            duration_ms=retry_duration,
                        )
                        return response.content
                    else:
                        logger.warning(f"[LLMClient] ❌ 没有可用的备选模型 (current={current_id}, new={new_id})")
            except Exception as retry_err:
                logger.error(f"[LLMClient] 自动切换重试也失败: {retry_err}")

            raise
    
    async def achat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        response_format: Optional[Dict[str, str]] = None,
        source: str = "chat",
        session_id: int = None,
    ) -> str:
        """异步聊天请求（带自动切换和详细 Token 统计）"""
        import time as _time
        self._ensure_provider()
        start_ms = int(_time.time() * 1000)
        
        try:
            response = await self._provider.achat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format
            )
            
            duration_ms = int(_time.time() * 1000) - start_ms

            model_config_manager.increment_token_usage(
                tokens=response.total_tokens,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                source=source,
                session_id=session_id,
                success=True,
                duration_ms=duration_ms,
            )
            
            return response.content
            
        except Exception as e:
            duration_ms = int(_time.time() * 1000) - start_ms
            logger.error(f"[LLMClient] 异步请求失败: {e}")

            model_config_manager.increment_token_usage(
                tokens=0, prompt_tokens=0, completion_tokens=0,
                source=source, session_id=session_id,
                success=False, error_type=str(type(e).__name__),
                duration_ms=duration_ms,
            )

            # 尝试自动切换
            try:
                from llm.auto_switch import get_auto_switcher, classify_failure_reason
                switcher = get_auto_switcher()
                # 确保 profiles 已加载（首次调用时可能为空）
                if not switcher._profiles:
                    switcher.load_profiles_from_db()
                if switcher.enabled and self._config and len(switcher._profiles) > 1:
                    reason = classify_failure_reason(e)
                    current_id = self._config.get('id', 0)
                    new_id = switcher.mark_failure(current_id, reason)
                    if new_id and new_id != current_id:
                        logger.info(f"[LLMClient] 🔄 自动切换: ID={current_id} → ID={new_id}，重试异步请求")
                        self.refresh()
                        self._ensure_provider()
                        response = await self._provider.achat(
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            response_format=response_format
                        )
                        retry_duration = int(_time.time() * 1000) - start_ms
                        model_config_manager.increment_token_usage(
                            tokens=response.total_tokens,
                            prompt_tokens=response.prompt_tokens,
                            completion_tokens=response.completion_tokens,
                            source=source, session_id=session_id,
                            success=True, duration_ms=retry_duration,
                        )
                        return response.content
                    else:
                        logger.warning(f"[LLMClient] ❌ 没有可用的备选模型 (current={current_id}, new={new_id})")
            except Exception as retry_err:
                logger.error(f"[LLMClient] 自动切换重试也失败: {retry_err}")

            raise
    
    def generate_test_cases(
        self,
        requirement: str,
        count: int = 3,
        priority: str = "3"
    ) -> Dict[str, Any]:
        """
        根据需求生成测试用例
        
        Args:
            requirement: 用户需求或测试点
            count: 生成数量
            priority: 默认优先级
        
        Returns:
            生成的测试用例数据
        """
        template_fields = [
            "module", "title", "precondition", "steps", "expected",
            "keywords", "priority", "case_type", "stage"
        ]
        
        system_prompt = """你是一个专业的软件测试工程师，擅长编写测试用例。
请根据用户提供的需求，生成结构化的测试用例。

输出格式要求:
- 必须返回有效的 JSON 对象
- 包含 test_cases 数组
- 每个测试用例包含: module, title, precondition, steps, expected, keywords, priority, case_type, stage"""
        
        user_prompt = f"""请根据以下需求生成测试用例:

需求: {requirement}

请生成包含以下字段的测试用例: {', '.join(template_fields)}

以 JSON 格式返回，格式如:
{{
    "test_cases": [
        {{
            "module": "模块名",
            "title": "用例标题",
            "precondition": "前置条件",
            "steps": ["步骤1", "步骤2"],
            "expected": "预期结果",
            "keywords": "关键词",
            "priority": "3",
            "case_type": "功能测试",
            "stage": "系统测试"
        }}
    ]
}}"""
        
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
                **result
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
        生成测试报告
        
        Args:
            test_results: 测试结果列表
            summary: 测试统计摘要
            format_type: 报告格式
        
        Returns:
            生成的报告
        """
        total_cases = summary.get('total', len(test_results))
        is_single_case = total_cases == 1
        
        test_results_json = json.dumps(test_results, ensure_ascii=False, indent=2)
        
        system_prompt = """你是一个专业的测试报告生成专家。
请根据测试结果生成清晰、专业的测试报告。"""
        
        if is_single_case:
            user_prompt = f"""请根据以下测试结果生成测试报告:

测试结果:
{test_results_json}

请生成 {format_type.upper()} 格式的测试报告。"""
        else:
            user_prompt = f"""请根据以下批量测试结果生成测试报告:

测试统计:
- 总用例数: {summary.get('total', 0)}
- 通过数: {summary.get('pass', 0)}
- 失败数: {summary.get('fail', 0)}
- 执行耗时: {summary.get('duration', 0)} 秒

测试结果详情:
{test_results_json}

请生成 {format_type.upper()} 格式的测试报告。"""
        
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
        分析 Bug
        
        Args:
            analysis_prompt: Bug 分析提示
        
        Returns:
            Bug 分析结果
        """
        system_prompt = """你是一个专业的 Bug 分析专家。
请分析测试失败的原因，并返回结构化的 Bug 报告。

返回 JSON 格式:
{
    "error_type": "错误类型（功能错误/设计缺陷/安全问题/系统错误）",
    "severity_level": "严重程度（一级/二级/三级/四级）",
    "actual_result": "实际结果描述",
    "result_feedback": "问题分析和建议"
}"""
        
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
            
            # 清理 markdown 代码块
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
            logger.warning(f"[LLMClient] JSON 解析失败: {e}")
            return {
                "success": True,
                "data": {
                    "error_type": "系统错误",
                    "severity_level": "一级",
                    "actual_result": response if 'response' in dir() else "响应格式异常",
                    "result_feedback": "LLM 返回格式异常，无法解析"
                }
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "data": {}
            }
    
    def refresh(self):
        """刷新配置和 Provider"""
        self._config = None
        self._provider = None
        model_config_manager.refresh_config()

    def parse_json_response(self, content: str) -> dict:
        """
        使用当前 Provider 的 JSON 解析器解析 LLM 响应

        自动根据当前活跃的模型 Provider 选择最合适的解析策略

        Args:
            content: LLM 原始响应文本

        Returns:
            解析后的 dict
        """
        self._ensure_provider()
        return self._provider.parse_json_response(content)


# 全局实例
_llm_client_instance: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取 LLM 客户端实例（单例）"""
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance
