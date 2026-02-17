# AI Test Agent - 智能自动化测试平台

<div align="center">
  <img src="agent_web_server/src/assets/logo.png" alt="AI Test Agent Logo" width="200"/>

  ![License](https://img.shields.io/badge/License-MIT-blue.svg)
  ![Python](https://img.shields.io/badge/Python-3.11%2B-green.svg)
  ![Node.js](https://img.shields.io/badge/Node.js-18%2B-green.svg)
  ![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg)
  ![Vue](https://img.shields.io/badge/Vue-3.4.0-4FC08D.svg)
</div>

## 项目简介

AI Test Agent 是一个基于人工智能的自动化测试平台，利用大语言模型（LLM）和浏览器自动化技术，实现测试用例的智能生成、自动执行、Bug 分析和报告生成。平台采用 **适配器模式（Adapter Pattern）** 重构了底层模型架构，支持 15+ 主流大模型供应商，并内置了智能止损、模糊匹配、Agent 判定优先等策略，大幅提升了测试的稳定性和效率。

## 核心特性

### 1. 智能测试用例生成
- 基于自然语言需求自动生成测试用例
- 支持多种文件导入（TXT、PDF、DOCX、DOC）
- 自动生成结构化用例（模块、标题、步骤、预期结果、优先级）
- 智能覆盖正常、异常、边界及安全测试场景

### 2. 自动化测试执行与智能策略
- **基于 Browser-Use 0.11.1 的智能执行**：利用视觉识别和 DOM 分析进行精准操作
- **单量 / 批量执行模式**：
  - 单量执行：逐条执行并生成独立报告
  - 批量执行：多用例连续执行，生成统一汇总报告，支持暂停/恢复/停止控制
- **智能止损策略 (Stop Loss)**：
  - 连续 3 步操作无效自动熔断
  - 单用例超时控制，防止阻塞整体进度
- **模糊匹配验证 (Fuzzy Matching)**：
  - 支持语义级断言（如"账号或密码错误"与"密码错误"视为匹配），减少误报
- **Agent 判定优先**：
  - Agent 自身的 `done(success=True/False)` 判定优先于 browser-use 内置 judge 的判定
  - 解决 Toast 等瞬时提示消失后 DOM 无法捕获导致的误判问题
- **主动回溯与重触发**：
  - 验证失败时自动回溯上一步操作，精准捕捉瞬时 Toast 提示

### 3. 接口测试（API Testing）
- **接口文件管理**：上传 Markdown 接口文档到 MinIO，自动解析提取 endpoints（method/path/summary/params/examples）
  - 多策略解析器：支持标题内联格式、中文 KV 格式（`- **路径**: /v1/xxx`）、Markdown 表格、全文正则扫描兜底
  - 卡片式文件管理界面，支持查看详情、原文预览、删除
- **智能接口匹配**：两段式匹配（关键词粗筛 + LLM 精排），根据测试用例文本自动推荐最合适的接口文件
- **三步式执行流程**：
  1. 选择测试用例（多选）
  2. AI 智能匹配接口文件，展示推荐与候选列表、接口预览，支持手动切换
  3. 配置环境（Base URL、Headers）后执行，LLM 生成可执行 DSL → HTTP Runner 发送请求 → 断言验证
- **全链路闭环**：执行结果写入 `test_records` → 自动生成 `test_reports` → 失败用例创建 `bug_reports` → 自动邮件通知 `auto_receive_bug=1` 联系人

### 4. 一键测试（OneClick Test）
- **全自动 AI 测试**：输入自然语言指令（如"帮我测试登录功能"），AI 自动完成意图分析 → 用例生成 → 浏览器执行全流程
- **对话式交互界面**：类 ChatGPT 的对话流 UI，实时展示分析进度、生成的用例列表和执行结果
- **智能用例生成**：LLM 分析用户意图，结合数据库已有用例和测试环境信息，自动生成覆盖正常/异常/边界场景的测试用例
- **用户确认机制**：生成用例后展示给用户确认或编辑，确认后才开始执行
- **浏览器复用**：所有用例共享一个 BrowserSession，避免每条用例都启动/关闭浏览器，大幅提升执行速度
- **真正的停止控制**：通过 asyncio.Event 取消机制 + 浏览器强制关闭，点击停止后立即生效
- **429 限流智能熔断**：检测到 API 配额耗尽（429 错误）时立即停止后续用例，避免无效重试
- **Skills 知识注入**：执行时自动加载相关 Skills 作为"便签"注入 LLM 提示词，增强 Agent 测试能力

### 5. Skills 管理
- **知识增强系统**：Skills 是 Markdown 格式的程序化知识文件，为 AI Agent 提供测试领域的专业指导
- **MinIO 存储**：Skills 文件存储在 MinIO 对象存储中，数据库仅保存索引信息
- **多种安装方式**：
  - 从 GitHub 仓库下载安装（支持 `GITHUB_PROXY` 代理配置）
  - 手动上传 `.md` 文件安装（适用于无法访问 GitHub 的网络环境）
- **卡片式管理界面**：直观展示已安装 Skills，支持启用/禁用/删除/查看详情
- **便签式注入**：执行测试时，将相关 Skills 内容以"便签"形式注入到 LLM 系统提示词中

### 6. 多模型适配与管理
- **全平台支持**：内置适配器支持以下模型供应商：
  - **OpenAI** (GPT-4o, GPT-3.5)
  - **DeepSeek** (DeepSeek-V3, R1)
  - **Anthropic** (Claude 3.5 Sonnet/Opus)
  - **Google** (Gemini 1.5 Pro/Flash)
  - **Azure OpenAI**
  - **Alibaba / ModelScope** (Qwen3-235B 等通义系列)
  - **Ollama** (本地模型)
  - **Mistral AI**
  - **Moonshot** (Kimi)
  - 以及更多通用 OpenAI 兼容接口
- **智能调度**：基于数据库配置的优先级和激活状态自动选择最佳模型
- **成本监控**：实时统计 Token 使用量和 API 成本

### 7. 智能 Bug 分析
- 自动分析失败原因，区分系统 Bug 与脚本错误
- 智能定级（一级致命至四级轻微）
- 自动提取复现步骤，生成带截图的 Bug 报告
- 关联测试用例，记录预期结果与实际结果

### 8. 报告与通知
- **运行测试报告**：详细执行日志、思维链（Thinking）、步骤截图
- **综合评估报告**：AI 驱动的多报告聚合分析，包含质量评级（A/B/C/D）、通过率、改进建议，Markdown 渲染展示
- **邮件推送**：集成阿里云 DirectMail 和 Resend，支持自动发送格式化 HTML 邮件给联系人
- **Bug 报告**：按严重程度、状态、错误类型多维度管理

### 9. 数据可视化仪表盘
- 测试结果分布（通过/失败/待执行）
- 用例优先级与类型分布
- 测试趋势图（支持近一月/一季/一年）
- Bug 严重程度分布（横向柱状图）
- Bug 状态分布（环形饼图）
- Bug 错误类型分布（雷达图）
- 邮件发送统计

## 技术架构

### 后端技术栈
- **框架**: FastAPI 0.115.0 + Uvicorn
- **架构模式**: Adapter Pattern (LLM Layer), Factory Pattern
- **数据库**: MySQL + SQLAlchemy 2.0.25
- **核心引擎**: Browser-Use 0.11.1 + Playwright
- **LLM 集成**: 支持 OpenAI, Anthropic, Google GenAI, Ollama, Alibaba 等多协议
- **对象存储**: MinIO（接口文件存储与版本管理）
- **邮件服务**: 阿里云 DirectMail (HMAC-SHA1 签名) + Resend
- **其他**: PyPDF2, Pandas, python-docx, Markdown, requests

### 前端技术栈
- **框架**: Vue 3.4.0 + Naive UI 2.38.0
- **状态管理**: Pinia 2.1.7
- **构建工具**: Vite 5.0.0
- **样式**: TailwindCSS + SCSS
- **图表**: ECharts
- **Markdown 渲染**: marked

## 项目结构

```
Ai_Test_Agent/
├── Agent_Server/                # 后端服务
│   ├── app.py                  # FastAPI 入口
│   ├── llm/                    # LLM 核心模块
│   │   ├── base.py             # Provider 基类
│   │   ├── factory.py          # Provider 工厂
│   │   ├── client.py           # LLM 客户端（兼容层）
│   │   ├── manager.py          # 模型配置管理
│   │   ├── config.py           # 默认配置
│   │   └── providers/          # 具体 Provider 实现
│   │       ├── openai_provider.py
│   │       ├── anthropic_provider.py
│   │       ├── google_provider.py
│   │       ├── deepseek_provider.py
│   │       ├── alibaba_provider.py
│   │       ├── ollama_provider.py
│   │       ├── mistral_provider.py
│   │       ├── moonshot_provider.py
│   │       ├── azure_provider.py
│   │       └── generic_provider.py
│   ├── Api_Spec/               # 接口文件管理（MinIO + 解析器）
│   │   ├── router.py           # 上传/列表/详情/删除 API
│   │   ├── parser.py           # Markdown 多策略解析器
│   │   └── minio_client.py     # MinIO 客户端封装
│   ├── Api_Test/               # 接口测试模块
│   │   ├── router.py           # 智能匹配 + 执行 API
│   │   └── service.py          # 匹配/DSL生成/HTTP Runner/报告/Bug/邮件
│   ├── OneClick_Test/          # 一键测试模块
│   │   ├── router.py           # 一键测试 + Skills 管理 API
│   │   ├── service.py          # 核心服务（意图分析/用例生成/浏览器执行/停止控制/429熔断）
│   │   ├── session.py          # 会话状态机管理
│   │   └── skill_manager.py    # Skills 管理（MinIO存储/GitHub下载/手动上传/便签注入）
│   ├── Api_request/            # 提示词模板
│   ├── Bug_Analysis/           # Bug 分析服务
│   ├── Build_Report/           # 报告生成服务
│   ├── Build_Use_case/         # 用例生成服务
│   ├── Execute_test/           # 浏览器测试执行服务
│   ├── Dashboard/              # 仪表盘数据
│   ├── Contact_manage/         # 联系人管理
│   ├── Email_manage/           # 邮件管理
│   ├── Model_manage/           # 模型配置管理
│   ├── Browser_Control/        # 浏览器控制
│   ├── Test_Tools/             # 任务管理器
│   ├── database/               # 数据库模型与连接
│   ├── docs/                   # 开发文档
│   └── save_floder/            # 截图等文件存储
├── agent_web_server/           # 前端服务
│   ├── src/
│   │   ├── api/                # API 接口定义
│   │   ├── views/
│   │   │   ├── dashboard/      # 数据可视化仪表盘
│   │   │   ├── test/           # 测试执行
│   │   │   │   ├── FuncTest.vue      # 功能测试（单量/批量 Browser-Use）
│   │   │   │   ├── ApiTest.vue       # 接口测试（三步式：选用例→匹配→执行）
│   │   │   │   ├── OneClickTest.vue  # 一键测试（对话式 AI 全自动测试）
│   │   │   │   ├── PressTest.vue     # 性能测试
│   │   │   │   └── SecurityTest.vue  # 安全测试
│   │   │   ├── skills/         # Skills 管理
│   │   │   │   └── SkillManage.vue   # Skills 管理（卡片式 + 上传安装）
│   │   │   ├── case/           # 用例管理与生成
│   │   │   │   ├── CaseGenerate.vue  # 用例生成
│   │   │   │   ├── CaseManage.vue    # 用例管理
│   │   │   │   └── ApiSpecManage.vue # 接口文件管理（卡片式）
│   │   │   ├── report/         # 报告管理
│   │   │   │   ├── RunReport.vue     # 运行测试报告
│   │   │   │   ├── BugReport.vue     # Bug 报告
│   │   │   │   └── MixedReport.vue   # 综合评估报告
│   │   │   ├── model/          # 模型配置
│   │   │   ├── mail/           # 邮件发送与配置
│   │   │   └── prompt/         # 提示词管理
│   │   ├── components/         # 公共组件
│   │   ├── composables/        # 组合式函数
│   │   ├── router/             # 路由配置
│   │   ├── layouts/            # 布局组件
│   │   └── styles/             # 全局样式
│   └── package.json
└── README.md
```

## 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+
- MySQL 8.0+
- MinIO（接口文件存储）
- Chrome / Edge 浏览器

### 后端部署

1. **安装依赖**
```bash
cd Agent_Server
pip install -r requirements.txt
playwright install chromium
```

2. **配置环境变量** (`.env`)
```env
# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=ai_test_agent

# 服务端口
PORT=8001

# 浏览器配置
HEADLESS=false

# MinIO 对象存储
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=aitest
MINIO_REGION=cn-beijing-1
MINIO_SECURE=false

# GitHub 代理（一键测试 Skills 下载，可选）
GITHUB_PROXY=https://ghproxy.com/
```

3. **初始化数据库**
```bash
python -c "from database.connection import init_db; init_db()"
```

4. **启动服务**
```bash
python app.py
```

### 前端部署

```bash
cd agent_web_server
npm install
npm run dev
```

前端默认运行在 `http://localhost:5175`，通过 Vite 代理转发 API 请求到后端 `http://localhost:8001`。

## 使用指南

### 1. 模型配置
进入"模型管理"页面，添加模型时选择对应的 Provider（如 `openai`、`deepseek`、`alibaba`）。系统会根据 `is_active=1` 且优先级最高的规则自动调用对应模型。

### 2. 功能测试（Browser-Use）
- **单量执行**：在"功能测试"页面选择单条用例执行，Agent 自动启动浏览器完成操作并生成报告。
- **批量执行**：勾选多条用例批量执行，系统生成统一汇总报告，支持实时暂停/恢复/停止。
- 若遇到验证失败，Agent 会自动尝试回溯操作或进行模糊匹配，无需人工干预。

### 3. 接口测试（API Testing）
- **上传接口文件**：在"用例生成模块 → 接口文件管理"页面上传 Markdown 接口文档，系统自动解析并存储到 MinIO。
- **执行接口测试**：在"测试模块 → 接口测试"页面，三步完成：
  1. 勾选测试用例
  2. AI 自动匹配最合适的接口文件，展示推荐结果和接口预览
  3. 配置目标环境（Base URL、Headers），选择执行模式（LLM 增强 / 冒烟测试），点击执行
- 执行完成后自动生成测试报告，失败用例自动创建 Bug 并邮件通知相关联系人。

### 4. 一键测试（OneClick Test）
- 在"一键测试"页面输入自然语言指令，如"帮我测试课程作业的所有功能"
- AI 自动分析意图、查询数据库已有用例、获取测试环境，生成完整测试用例列表
- 确认用例后点击"确认执行"，Agent 自动启动浏览器逐条执行
- 执行过程中可随时点击"停止"按钮，系统会立即终止当前任务并关闭浏览器
- 如遇 API 配额耗尽（429），系统自动停止后续用例并提示

### 5. Skills 管理
- 在"Skills 管理"页面通过手动上传 `.md` 文件安装 Skills（推荐，无需网络）
- 也可通过 GitHub slug（如 `anthropics/webapp-testing`）在线安装（需配置 `GITHUB_PROXY`）
- 安装后的 Skills 会在一键测试执行时自动注入到 AI Agent 的提示词中，增强测试能力
- 支持启用/禁用/删除/查看详情

### 6. 查看结果
- **运行测试报告**：查看详细的执行日志、AI 思维链和步骤详情，状态根据通过/失败数量自动判定。
- **Bug 报告**：测试失败时自动生成 Bug 单，包含关联用例、复现步骤、预期/实际结果和修复建议。
- **综合评估报告**：选择多份运行报告，AI 自动聚合分析生成质量评级和改进建议。

### 7. 邮件通知
在"邮件配置"中配置阿里云 DirectMail 或 Resend 服务，即可将综合评估报告一键发送给联系人。

### 8. 数据看板
仪表盘提供全局视角的测试数据可视化，包括测试趋势、Bug 分布、用例覆盖等多维度图表。

## 许可证

MIT License

---

**AI Test Agent** - 让自动化测试更智能、更高效！
