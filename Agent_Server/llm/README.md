# LLM 模块说明

## 概述

LLM 模块提供统一的大模型接口，支持用户通过 Web 端自定义配置大模型。

## 工作流程

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Web 前端       │────▶│   llm_models 表   │────▶│   LLM 模块       │
│   激活模型       │     │   is_active = 1   │     │   Provider 工厂  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                 │                        │
                                 │                        ▼
                                 │              ┌─────────────────┐
                                 │              │  根据 provider   │
                                 │              │  字段选择 Provider │
                                 │              └─────────────────┘
                                 │                        │
                                 ▼                        ▼
                        ┌──────────────────┐    ┌─────────────────┐
                        │  model_providers  │   │  OpenAI Provider │
                        │  表（供应商配置）   │   │  DeepSeek Provider│
                        │  - code           │   │  Anthropic Provider│
                        │  - default_base_url│   │  Google Provider  │
                        └──────────────────┘    │  Ollama Provider  │
                                                │  ...              │
                                                └─────────────────┘
```

## 用户使用流程

1. **Web 端配置模型**：用户在模型管理页面添加/编辑模型

   - 选择 Provider（如 `deepseek`、`openai`、`alibaba` 等）
   - 填写 API Key
   - 填写 Base URL（可选，使用默认值）
   - 填写模型名称
2. **激活模型**：用户点击激活按钮，设置 `is_active = 1`
3. **后端自动使用**：系统根据 `provider` 字段自动选择对应的处理方式

   ```python
   # 后端代码自动获取激活的模型
   from llm import get_active_langchain_llm, get_active_browser_use_llm

   # 获取 LangChain 格式的 LLM（用于生成测试用例、报告等）
   llm = get_active_langchain_llm()

   # 获取 Browser-Use 格式的 LLM（用于执行测试）
   browser_llm = get_active_browser_use_llm()
   ```

## 支持的 Provider

| provider 代码   | 显示名称           | 说明                       |
| --------------- | ------------------ | -------------------------- |
| `openai`      | OpenAI             | GPT-4、GPT-3.5、O1 等      |
| `anthropic`   | Anthropic          | Claude 3 系列              |
| `google`      | Google (Gemini)    | Gemini 系列                |
| `deepseek`    | DeepSeek           | DeepSeek Chat、R1 推理模型 |
| `alibaba`     | Alibaba (通义千问) | Qwen 系列                  |
| `baidu`       | Baidu (文心一言)   | 文心一言模型               |
| `ollama`      | Ollama             | 本地运行的模型             |
| `mistral`     | Mistral AI         | Mistral 系列               |
| `grok`        | Grok               | xAI 的 Grok 模型           |
| `openrouter`  | OpenRouter         | 聚合模型平台               |
| `vercel`      | Vercel AI          | Vercel AI SDK              |
| `cerebras`    | Cerebras           | 超高速推理服务             |
| `browser_use` | Browser Use Cloud  | Browser-Use 官方模型服务   |
| `moonshot`    | MoonShot/Kimi      | 月之暗面                   |
| `siliconflow` | 硅基流动           | 国产模型平台               |
| `modelscope`  | 魔搭社区           | 阿里模型社区               |
| `zhipu`       | 智谱 AI            | GLM 系列                   |

## 数据库表结构

### llm_models 表（用户配置的模型）

```sql
CREATE TABLE `llm_models` (
  `id` int NOT NULL AUTO_INCREMENT,
  `model_name` varchar(100) NOT NULL COMMENT '模型名称',
  `api_key` varchar(500) NOT NULL COMMENT 'API密钥',
  `base_url` varchar(500) DEFAULT NULL COMMENT 'API基础URL',
  `provider` varchar(50) DEFAULT NULL COMMENT '模型供应商（对应 model_providers.code）',
  `is_active` int DEFAULT NULL COMMENT '是否激活（0:否 1:是）',
  ...
);
```

### model_providers 表（支持的供应商列表）

```sql
CREATE TABLE `model_providers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL COMMENT '供应商名称',
  `code` varchar(50) NOT NULL COMMENT '供应商代码（如 openai, deepseek）',
  `display_name` varchar(100) NOT NULL COMMENT '显示名称',
  `default_base_url` varchar(500) DEFAULT NULL COMMENT '默认API基础URL',
  `is_active` int DEFAULT 1 COMMENT '是否启用',
  ...
);
```

## 代码示例

### 1. 获取激活模型的配置

```python
from llm import get_active_llm_config

config = get_active_llm_config()
print(f"当前激活的模型: {config['model_name']}")
print(f"Provider: {config['provider']}")
print(f"Base URL: {config['base_url']}")
```

### 2. 在测试执行中使用

```python
from llm import get_active_browser_use_llm
from llm.config import supports_structured_output

# 获取 Browser-Use LLM
llm = get_active_browser_use_llm()

# 检查是否支持结构化输出（DeepSeek 等不支持）
config = get_active_llm_config()
use_structured = supports_structured_output(config['provider'])

# 创建 Agent
from browser_use import Agent, BrowserSession

agent = Agent(
    task="执行测试任务",
    llm=llm,
    browser_session=BrowserSession(),
)
```

### 3. 在用例生成中使用

```python
from llm import get_llm_client

client = get_llm_client()

# 生成测试用例
result = client.generate_test_cases(
    requirement="测试登录功能",
    count=3
)
```

## 特殊处理

### DeepSeek R1 推理模型

DeepSeek R1 模型会返回思考过程（`reasoning_content`），系统会自动处理：

```python
from llm import create_llm_provider

provider = create_llm_provider(
    provider="deepseek",
    model_name="deepseek-reasoner",
    api_key="sk-xxx"
)

response = provider.chat([{"role": "user", "content": "问题"}])
print(f"思考过程: {response.reasoning_content}")
print(f"最终答案: {response.content}")
```

### 不支持结构化输出的 Provider

某些 Provider（如 DeepSeek、Ollama、Moonshot）不支持结构化输出，系统会自动设置：

```python
# 自动禁用结构化输出
dont_force_structured_output = True
```

## 文件结构

```
llm/
├── __init__.py       # 模块入口
├── base.py           # Provider 基类
├── config.py         # 配置（Provider 列表、默认端点等）
├── exceptions.py     # 异常定义
├── factory.py        # 工厂模式
├── manager.py        # 配置管理器（从数据库获取）
├── client.py         # LLM 客户端（兼容旧接口）
├── wrapper.py        # 包装器（兼容性处理）
└── providers/        # 具体 Provider 实现
    ├── openai_provider.py
    ├── deepseek_provider.py
    ├── anthropic_provider.py
    ├── google_provider.py
    ├── alibaba_provider.py
    ├── ollama_provider.py
    ├── generic_provider.py  # 通用 OpenAI 兼容
    └── ...
```

## 添加新的 Provider

1. 如果新 Provider 兼容 OpenAI API，直接在数据库 `model_providers` 表添加记录即可
2. 如果需要特殊处理，在 `providers/` 目录创建新的 Provider 类
3. 在 `factory.py` 的 `_load_providers()` 中注册新 Provider
