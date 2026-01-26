"""
LLM Wrapper - 解决 Pydantic v2 与 browser-use token tracking 的兼容性问题

browser-use 0.3.3 尝试通过 setattr 动态设置 LLM 的 ainvoke 方法，
但 Pydantic v2 模型不允许设置任意字段。

同时修复 browser-use 0.3.3 与 LangChain 的 output_format 参数不兼容问题。

作者: Ai_Test_Agent Team
"""
import logging

logger = logging.getLogger(__name__)


class LLMWrapper:
    """
    包装 LangChain LLM 以支持动态属性设置和修复 output_format 问题
    
    允许 browser-use 的 token_cost_service 设置 ainvoke 属性，
    同时将所有其他调用委托给原始 LLM。
    
    修复 browser-use 0.3.3 调用 ainvoke(messages, output_format=...) 时的兼容性问题。
    """
    
    def __init__(self, llm):
        """
        Args:
            llm: 原始的 LangChain LLM 实例（如 ChatOpenAI）
        """
        object.__setattr__(self, '_llm', llm)
        object.__setattr__(self, '_original_ainvoke', llm.ainvoke)
        
        # 为 browser-use token tracking 添加必要的属性
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
        else:
            provider = 'unknown'
        
        object.__setattr__(self, 'provider', provider)
        
        # 尝试获取 model 名称
        if hasattr(llm, 'model_name'):
            model = llm.model_name
        elif hasattr(llm, 'model'):
            model = llm.model
        else:
            model = 'unknown'
        
        object.__setattr__(self, 'model', model)
    
    def _convert_messages(self, messages):
        """
        转换 browser-use 的消息格式为 LangChain 格式
        
        browser-use 使用自己的 Message 类，需要转换为 LangChain 的 Message 类
        """
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
            
            # 转换 browser-use 消息
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
                # 尝试直接使用
                logger.warning(f"[LLMWrapper] 无法识别的消息类型: {msg_type}，尝试直接使用")
                converted.append(msg)
        
        return converted
    
    async def ainvoke(self, messages, output_format=None, **kwargs):
        """
        修复的 ainvoke 方法
        
        browser-use 会调用 ainvoke(messages, output_format=AgentOutput)
        我们需要：
        1. 转换消息格式
        2. 调用 LLM 获取 JSON 响应
        3. 解析并构造 output_format 对象
        """
        # 转换消息格式
        converted_messages = self._convert_messages(messages)
        
        # 如果有 output_format，手动处理 structured output
        if output_format is not None:
            logger.debug(f"[LLMWrapper] 处理 structured output: {output_format}")
            
            # 添加 JSON 格式要求到最后一条消息
            if converted_messages:
                last_msg = converted_messages[-1]
                if hasattr(last_msg, 'content'):
                    # 获取 output_format 的 schema
                    try:
                        if hasattr(output_format, 'model_json_schema'):
                            schema = output_format.model_json_schema()
                        elif hasattr(output_format, 'schema'):
                            schema = output_format.schema()
                        else:
                            schema = {}
                        
                        import json
                        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
                        
                        # 修改最后一条消息，添加 JSON 格式要求
                        from langchain_core.messages import HumanMessage
                        new_content = f"{last_msg.content}\n\nPlease respond with a valid JSON object matching this schema:\n{schema_str}"
                        converted_messages[-1] = HumanMessage(content=new_content)
                        
                    except Exception as e:
                        logger.warning(f"[LLMWrapper] 无法获取 schema: {e}")
            
            # 调用原始 LLM
            response = await self._original_ainvoke(converted_messages, **kwargs)
            
            # 解析响应并构造 output_format 对象
            try:
                import json
                content = response.content
                
                # 提取 JSON（可能在 markdown 代码块中）
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                # 解析 JSON
                data = json.loads(content)
                
                # 构造 output_format 对象
                result = output_format(**data)
                logger.debug(f"[LLMWrapper] 成功构造 {output_format.__name__} 对象")
                
                return result
                
            except Exception as e:
                logger.error(f"[LLMWrapper] 解析响应失败: {e}")
                logger.error(f"[LLMWrapper] 原始响应: {response.content[:500]}")
                raise
        else:
            return await self._original_ainvoke(converted_messages, **kwargs)
    
    def __getattr__(self, name):
        """委托属性访问到原始 LLM"""
        # 先检查是否是我们自己设置的属性
        if name in ['provider', 'model', '_original_ainvoke']:
            return object.__getattribute__(self, name)
        return getattr(self._llm, name)
    
    def __setattr__(self, name, value):
        """允许动态设置属性（包括 ainvoke）"""
        if name in ['_llm', '_original_ainvoke']:
            object.__setattr__(self, name, value)
        else:
            # 设置到包装器本身，而不是原始 LLM
            object.__setattr__(self, name, value)
    
    def __repr__(self):
        return f"LLMWrapper(provider={self.provider}, model={self.model}, llm={self._llm})"
