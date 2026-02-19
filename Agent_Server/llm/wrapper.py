"""
LLM 包装器模块

提供 LLM 包装器，解决与 browser-use 和 LangChain 的兼容性问题

作者: Ai_Test_Agent Team
版本: 1.0
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMWrapper:
    """
    LLM 包装器
    
    解决以下问题:
    1. Pydantic v2 与 browser-use token tracking 的兼容性
    2. browser-use 的 output_format 参数处理
    3. 不同模型输出格式的统一处理
    """
    
    def __init__(self, llm):
        """
        Args:
            llm: 原始的 LLM 实例（LangChain 或 browser-use 格式）
        """
        object.__setattr__(self, '_llm', llm)
        object.__setattr__(self, '_original_ainvoke', llm.ainvoke if hasattr(llm, 'ainvoke') else None)
        
        # 智能推断 provider
        llm_class_name = llm.__class__.__name__
        if 'OpenAI' in llm_class_name:
            provider = 'openai'
        elif 'Anthropic' in llm_class_name or 'Claude' in llm_class_name:
            provider = 'anthropic'
        elif 'Google' in llm_class_name or 'Gemini' in llm_class_name:
            provider = 'google'
        elif 'Ollama' in llm_class_name:
            provider = 'ollama'
        elif 'DeepSeek' in llm_class_name:
            provider = 'deepseek'
        else:
            provider = 'unknown'
        
        object.__setattr__(self, 'provider', provider)
        
        # 获取 model 名称
        if hasattr(llm, 'model_name'):
            model = llm.model_name
        elif hasattr(llm, 'model'):
            model = llm.model
        else:
            model = 'unknown'
        
        object.__setattr__(self, 'model', model)
    
    def _convert_messages(self, messages):
        """转换消息格式为 LangChain 格式"""
        from langchain_core.messages import (
            SystemMessage as LCSystemMessage,
            HumanMessage as LCHumanMessage,
            AIMessage as LCAIMessage,
        )
        
        converted = []
        for msg in messages:
            msg_type = type(msg).__name__
            
            # 如果已经是 LangChain 消息，直接使用
            if isinstance(msg, (LCSystemMessage, LCHumanMessage, LCAIMessage)):
                converted.append(msg)
                continue
            
            # 转换其他格式消息
            if hasattr(msg, 'role') and hasattr(msg, 'content'):
                role = msg.role.lower() if hasattr(msg.role, 'lower') else str(msg.role).lower()
                content = msg.content
                
                if role == 'system':
                    converted.append(LCSystemMessage(content=content))
                elif role == 'user' or role == 'human':
                    converted.append(LCHumanMessage(content=content))
                elif role == 'assistant' or role == 'ai':
                    converted.append(LCAIMessage(content=content))
                else:
                    logger.warning(f"[LLMWrapper] 未知消息角色: {role}，默认为 HumanMessage")
                    converted.append(LCHumanMessage(content=content))
            else:
                converted.append(msg)
        
        return converted
    
    async def ainvoke(self, messages, output_format=None, **kwargs):
        """
        异步调用，兼容 browser-use 的 output_format 参数
        """
        converted_messages = self._convert_messages(messages)
        
        # 处理 structured output
        if output_format is not None:
            logger.debug(f"[LLMWrapper] 处理 structured output: {output_format}")
            
            # 添加 JSON 格式要求到最后一条消息
            if converted_messages:
                last_msg = converted_messages[-1]
                if hasattr(last_msg, 'content'):
                    try:
                        if hasattr(output_format, 'model_json_schema'):
                            schema = output_format.model_json_schema()
                        elif hasattr(output_format, 'schema'):
                            schema = output_format.schema()
                        else:
                            schema = {}
                        
                        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
                        
                        from langchain_core.messages import HumanMessage
                        new_content = f"{last_msg.content}\n\nPlease respond with a valid JSON object matching this schema:\n{schema_str}"
                        converted_messages[-1] = HumanMessage(content=new_content)
                        
                    except Exception as e:
                        logger.warning(f"[LLMWrapper] 无法获取 schema: {e}")
            
            # 调用原始 LLM
            response = await self._original_ainvoke(converted_messages, **kwargs)
            
            # 解析响应
            try:
                content = response.content
                
                # 提取 JSON
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                # 尝试从自由文本中提取 JSON 对象
                content = content.strip()
                if not content.startswith('{'):
                    import re
                    match = re.search(r'\{[\s\S]*\}', content)
                    if match:
                        content = match.group(0)
                
                # 解析 JSON
                data = json.loads(content)
                
                # 修正常见的输出格式错误
                data = self._fix_action_format(data)
                
                # 构造 output_format 对象
                result = output_format(**data)
                logger.debug(f"[LLMWrapper] 成功构造 {output_format.__name__} 对象")
                
                return result
                
            except json.JSONDecodeError as je:
                logger.error(f"[LLMWrapper] JSON 解析失败: {je}")
                logger.error(f"[LLMWrapper] 原始响应: {response.content[:500]}")
                raise
            except Exception as e:
                logger.error(f"[LLMWrapper] 构造 {output_format.__name__} 失败: {e}")
                logger.error(f"[LLMWrapper] 原始响应: {response.content[:500]}")
                raise
        else:
            return await self._original_ainvoke(converted_messages, **kwargs)
    
    # browser-use AgentOutput 中合法的 action 类型
    VALID_BROWSER_ACTIONS = {
        'click', 'input', 'navigate', 'search', 'wait', 'done',
        'go_back', 'scroll_down', 'scroll_up', 'send_keys',
        'extract_content', 'switch_tab', 'open_tab', 'close_tab',
        'drag_drop', 'select_option', 'save_pdf', 'upload_file',
        'go_to_url', 'click_element', 'input_text', 'scroll_to_text',
        'get_dropdown_options', 'select_dropdown_option',
    }

    def _fix_action_format(self, data):
        """
        修正 LLM 输出的 action 格式错误
        
        常见错误:
        1. {'wait': 3} -> {'wait': {'seconds': 3}}
        2. {'input': {'index': 509, 'value': 'xxx'}} -> {'input': {'index': 509, 'text': 'xxx'}}
        3. 完全无效的 action 类型（如 'replace_file'）-> 过滤掉
        """
        if 'action' not in data:
            return data
        
        actions = data.get('action', [])
        if not isinstance(actions, list):
            return data
        
        fixed_actions = []
        has_valid = False
        for action in actions:
            if not isinstance(action, dict):
                fixed_actions.append(action)
                continue
            
            fixed_action = {}
            action_valid = False
            for key, value in action.items():
                # 检查是否为合法的 browser-use action 类型
                if key not in self.VALID_BROWSER_ACTIONS:
                    logger.warning(
                        f"[LLMWrapper] 过滤无效 action 类型: '{key}'，"
                        f"不在合法列表中"
                    )
                    continue
                
                action_valid = True

                # 修正 wait 格式
                if key == 'wait':
                    if isinstance(value, (int, float)):
                        fixed_action['wait'] = {'seconds': int(value)}
                        logger.debug(f"[LLMWrapper] 修正 wait 格式: {value} -> {{'seconds': {int(value)}}}")
                    elif isinstance(value, dict) and 'seconds' in value:
                        fixed_action['wait'] = value
                    else:
                        fixed_action['wait'] = {'seconds': 3}
                
                # 修正 input 格式
                elif key == 'input':
                    if isinstance(value, dict):
                        fixed_input = value.copy()
                        if 'value' in fixed_input and 'text' not in fixed_input:
                            fixed_input['text'] = fixed_input.pop('value')
                            logger.debug(f"[LLMWrapper] 修正 input 格式: 'value' -> 'text'")
                        fixed_action['input'] = fixed_input
                    else:
                        fixed_action['input'] = value
                
                else:
                    fixed_action[key] = value
            
            if fixed_action:
                fixed_actions.append(fixed_action)
                has_valid = True
            elif not action_valid:
                logger.warning(f"[LLMWrapper] 整个 action 被过滤（无合法字段）: {action}")
        
        # 如果所有 action 都被过滤了，插入一个 done 防止 Pydantic 验证崩溃
        if not has_valid and actions:
            logger.warning(
                f"[LLMWrapper] 所有 action 均无效，回退为 done。原始 actions: {actions}"
            )
            fixed_actions = [{"done": {"text": "操作无法执行：模型返回了无效的动作类型", "success": False}}]
        
        data['action'] = fixed_actions
        return data
    
    def __getattr__(self, name):
        """委托属性访问到原始 LLM"""
        if name in ['provider', 'model', '_original_ainvoke']:
            return object.__getattribute__(self, name)
        return getattr(self._llm, name)
    
    def __setattr__(self, name, value):
        """允许动态设置属性"""
        if name in ['_llm', '_original_ainvoke']:
            object.__setattr__(self, name, value)
        else:
            object.__setattr__(self, name, value)
    
    def __repr__(self):
        return f"LLMWrapper(provider={self.provider}, model={self.model}, llm={self._llm})"


def wrap_llm(llm) -> LLMWrapper:
    """
    包装 LLM 实例
    
    Args:
        llm: 原始 LLM 实例
    
    Returns:
        LLMWrapper 实例
    """
    if isinstance(llm, LLMWrapper):
        return llm
    return LLMWrapper(llm)
