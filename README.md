# 御策天检（AI 自动化测试平台）

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.8%2B-green.svg)
![Node.js](https://img.shields.io/badge/Node.js-16%2B-green.svg)

一个基于大模型 + 浏览器自动化的 **AI 驱动测试平台**，无需编写代码，LLM 实时决策和执行网页测试。

## ✨ 核心特性

### 🎯 五大功能模块

| 功能 | 描述 |
|------|------|
| **测试用例生成** | 输入需求描述或上传文档（支持 MD/TXT/PDF/DOC/DOCX），AI 自动生成结构化测试用例 |
| **AI 智能执行** | Browser-Use + LLM 实时决策，无需编写代码，支持暂停/恢复/停止控制 |
| **自动报告生成** | 执行完成自动分析日志，生成专业测试报告，支持 HTML 格式下载 |
| **Bug 智能管理** | 测试失败时自动分析 Bug 严重程度，记录复现步骤和截图，支持状态跟踪 |
| **任务管理** | 实时监控测试执行状态，支持暂停、恢复、停止操作 |

### 🚀 技术亮点

- ✅ **LLM 驱动**：集成 Qwen 3 VL，支持视觉分析和中文处理
- ✅ **无代码执行**：Browser-Use 框架，LLM 动态决策每一步操作
- ✅ **完整工作流**：从需求→用例→执行→报告，一体化闭环
- ✅ **智能容错**：自动处理弹窗、动态加载、页面变化等异常
- ✅ **全栈现代化**：Vue 3 + FastAPI + MySQL，采用异步架构
- ✅ **中文优先**：UI、注释、提示词全中文，支持密码 MD5 加密
- ✅ **文档解析**：支持上传 MD/TXT/PDF/DOC/DOCX 文件自动生成测试用例
- ✅ **任务控制**：实时暂停/恢复/停止测试执行，精确控制测试流程
- ✅ **报告导出**：一键下载 HTML 格式测试报告，支持离线查看
- ✅ **优化布局**：报告采用现代化设计，间距合理，阅读体验佳
- ✅ **Bug 管理**：自动分析 Bug 严重程度（一级~四级），智能提取复现步骤和截图
- ✅ **智能决策**：一级/二级 Bug 中止测试，三级/四级 Bug 继续执行并记录

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    AI 自动化测试平台                         │
└─────────────────────────────────────────────────────────────┘
        ↓                                    ↓
    ┌────────────────────────┐      ┌───────────────────────┐
    │   Vue 3 Web UI         │      │   FastAPI 后端        │
    │   (http://localhost:5173)    │   (http://localhost:8000)  │
    ├────────────────────────┤      ├───────────────────────┤
    │ • 测试用例生成        │      │ • Qwen LLM 集成       │
    │ • 执行用例（无代码）   │  ←→  │ • Browser-Use Agent   │
    │ • 查看测试报告        │      │ • 数据库 ORM          │
    └────────────────────────┘    └───────────────────────┘
                                            ↓
                                    ┌───────────────────────┐
                                    │   MySQL + Redis       │
                                    │   数据存储            │
                                    └───────────────────────┘
```

---

## 📁 项目目录结构

```
Ai_Test_Agent/
├── Agent_server/                   # 后端主目录
│   ├── Api_request/                # LLM 客户端
│   │   ├── llm_client.py          # Qwen API 封装（生成用例/代码/报告）
│   │   └── prompts.py             # Prompt 模板库
│   │
│   ├── Build_tests/                # 测试用例生成模块
│   │   ├── service.py             # 业务逻辑（调用 LLM）
│   │   └── router.py              # FastAPI 路由定义
│   │
│   ├── Build_test_code/            # 测试执行模块（Browser-Use）
│   │   ├── browser_use_service.py # 核心执行服务
│   │   ├── task_manager.py        # 任务管理器（暂停/恢复/停止）
│   │   └── router.py              # FastAPI 路由
│   │
│   ├── Build_Report/               # 报告生成模块
│   │   ├── service.py             # 报告逻辑（调用 LLM 分析）
│   │   └── router.py              # FastAPI 路由
│   │
│   ├── Bug_Analysis/               # Bug 分析模块
│   │   ├── service.py             # Bug 分析逻辑（LLM 智能分析）
│   │   └── router.py              # FastAPI 路由
│   │
│   ├── browser_use_core/           # Browser-Use 增强核心（来自 web-ui）
│   │   ├── browser_use_agent.py   # 自定义 Agent
│   │   ├── custom_browser.py      # 自定义浏览器配置
│   │   ├── custom_context.py      # 浏览器上下文
│   │   └── custom_controller.py   # MCP 工具控制器
│   │
│   ├── database/                   # 数据库层
│   │   └── connection.py          # SQLAlchemy 模型定义 + 初始化
│   │
│   ├── mcp_utils/                  # MCP 工具集成
│   │   └── mcp_client.py          # Firecrawl MCP 客户端
│   │
│   ├── app.py                      # FastAPI 主应用入口
│   ├── requirements.txt            # Python 依赖
│   ├── .env                        # 环境配置（敏感信息）
│   └── Template.csv               # 测试用例模板
│
├── web_agent/                      # 前端主目录（Vue 3 + Vite）
│   ├── src/
│   │   ├── api/
│   │   │   └── index.js           # Axios 实例 + API 模块（生成、执行、报告）
│   │   │
│   │   ├── router/
│   │   │   └── index.js           # Vue Router 路由配置
│   │   │
│   │   ├── views/
│   │   │   ├── TestCaseView.vue    # 测试用例生成页面
│   │   │   ├── ExecuteCaseView.vue # 执行用例页面（核心交互）
│   │   │   ├── TestReportView.vue  # 报告查看页面
│   │   │   └── BugReportView.vue   # Bug 管理页面
│   │   │
│   │   ├── App.vue                # 主应用组件（导航 + 布局）
│   │   └── main.js                # Vue 应用入口
│   │
│   ├── package.json               # npm 依赖 + 脚本
│   ├── vite.config.js             # Vite 构建配置
│   ├── index.html                 # HTML 入口
│   └── node_modules/              # npm 安装的依赖
│
├── save_floder/                    # 生成文件输出目录
│   ├── test_case_*.csv            # 生成的测试用例
│   ├── test_report_*.html         # 生成的测试报告
│   ├── bug_floder/                # Bug 截图目录
│   │   └── *.pdf                  # 失败页面截图（PDF 格式）
│   └── ...
│
└── README.md                       # 本文件
```

---

## 💻 技术栈

### 后端

| 组件 | 技术 | 版本 |
|------|------|------|
| **Web 框架** | FastAPI | 0.115.0 |
| **ASGI 服务器** | Uvicorn | 0.32.0 |
| **ORM** | SQLAlchemy | 2.0.25 |
| **LLM 集成** | Browser-Use 原生 LLM | - |
| **浏览器自动化** | Browser-Use | 0.3.3 |
| **测试框架** | Pytest | 8.0.0 |
| **数据库驱动** | PyMySQL | 1.1.0 |
| **缓存** | Redis | 5.0.1 |
| **配置管理** | Python-dotenv | 1.0.0 |

### 前端

| 组件 | 技术 | 版本 |
|------|------|------|
| **框架** | Vue.js | 3.4.0 |
| **路由** | Vue Router | 4.2.5 |
| **构建工具** | Vite | 5.0.0 |
| **HTTP 客户端** | Axios | 1.6.0 |
| **UI 组件库** | Element Plus | 2.5.0 |
| **图标库** | @element-plus/icons-vue | 2.3.1 |

### 数据库

- **主数据库**：MySQL 5.7+
- **缓存**：Redis
- **字符集**：UTF-8MB4（支持中文）

---

## 🚀 快速开始

### 前置要求

- **Python** ≥ 3.8
- **Node.js** ≥ 16
- **MySQL** ≥ 5.7
- **Redis**（可选）

### 1️⃣ 后端启动

```bash
# 进入后端目录
cd Agent_server

# 安装 Python 依赖
pip install -r requirements.txt

# 配置环境变量
# 编辑 .env 文件，填入你的配置：
# - LLM_API_KEY（Qwen API Key）
# - DB_HOST、DB_USER、DB_PASSWORD（MySQL 连接信息）
# - FIRECRAWL_API_KEY（Firecrawl API Key，可选）

# 启动 FastAPI 服务
python app.py
```

**输出示例**：
```
=================================================================
初始化数据库...
表 'test_cases' 创建成功
表 'test_results' 创建成功
...
=================================================================
📚 API 文档访问地址：
=================================================================
  ✓ Swagger UI 文档: http://localhost:8000/docs
  ✓ ReDoc 文档:       http://localhost:8000/redoc
  ✓ OpenAPI JSON:    http://localhost:8000/openapi.json
=================================================================

🚀 AI 自动化测试平台 API 已成功启动！
```

### 2️⃣ 前端启动

```bash
# 进入前端目录
cd web_agent

# 安装 npm 依赖
npm install

# 启动开发服务器
npm run dev
```

**访问 Web UI**：http://localhost:5173

### 3️⃣ 环境配置文件示例（.env）

```ini
# ========== LLM 配置 ==========
LLM_BASE_URL=https://api.ppinfra.com/openai
LLM_API_KEY=your_api_key_here
LLM_MODEL=qwen/qwen3-vl-235b-a22b-instruct
LLM_USE_VISION=true

# ========== 数据库配置 ==========
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=ai_test_agent

# ========== 服务配置 ==========
HOST=0.0.0.0
PORT=8000
DEBUG=True

# ========== Browser-Use 配置 ==========
HEADLESS=false
MAX_STEPS=100
MAX_ACTIONS=10
BROWSER_WINDOW_WIDTH=1920
BROWSER_WINDOW_HEIGHT=1200
DISABLE_SECURITY=false

# ========== 文件路径 ==========
SAVE_FOLDER_DIR=../save_floder
```

---

## 📖 使用指南

### 场景 1️⃣：生成测试用例

#### 方式一：文本输入
1. 打开 Web UI → **测试用例** 选项卡
2. 在左侧文本框输入测试需求（例如：用户登录、查看课程、上传文件）
3. 点击 **生成测试用例**
4. 系统自动调用 Qwen LLM 生成 3 个结构化用例
5. 用例保存到数据库 + CSV 文件

#### 方式二：文档上传
1. 打开 Web UI → **测试用例** 选项卡
2. 在右侧上传区域拖拽或点击上传文档
3. 支持格式：`.md` / `.txt` / `.pdf` / `.doc` / `.docx`
4. 文件大小限制：10MB
5. 系统自动解析文档内容并生成测试用例

**生成结果包含**：
- 模块名、用例标题、前置条件
- 测试步骤（列表形式）
- 预期结果、优先级、用例类型

### 场景 2️⃣：执行测试用例（AI 智能执行）

1. 打开 Web UI → **执行用例** 选项卡
2. 选择待执行的测试用例
3. 配置执行参数：
   - **无头模式**：关闭后可观察浏览器操作过程
   - **最大步数**：防止无限循环（默认 20）
   - **视觉能力**：启用后 LLM 可分析截图（成本略高）
4. 点击 **🤖 执行用例**
5. Browser-Use Agent 接管浏览器，LLM 实时决策每一步操作
6. 执行完成后自动生成测试报告

**执行过程显示**：
- 🤖 AI 思考过程（LLM 的推理）
- 🌐 访问的页面 URL
- ⚡ 执行的动作（点击、输入、等待等）
- ⏰ 每一步的时间戳

**任务控制功能**：
- ⏸️ **暂停执行**：暂时停止测试，保持当前状态
- ▶️ **继续执行**：从暂停点恢复测试
- ⏹️ **停止执行**：完全终止测试（需确认）

**浏览器配置**：
- 窗口大小：1920x1200（可在 .env 中配置）
- 自动最大化窗口
- 禁用自动化检测特征

### 场景 3️⃣：查看测试报告

1. 打开 Web UI → **测试报告** 选项卡
2. 查看报告列表（包含通过率、耗时等统计）
3. 点击 **查看报告** 查看详细内容
4. 点击 **下载报告** 按钮导出 HTML 文件

**报告内容包含**：
- 测试概览（通过数、失败数、总耗时）
- 每个用例的执行详情
- 失败原因分析和修复建议
- Agent 的行为路径描述

**报告特性**：
- 📊 现代化设计，间距合理，阅读体验佳
- 🎨 使用卡片布局和颜色标识
- 📥 支持一键下载 HTML 格式
- 💾 离线可查看，包含完整样式

### 场景 4️⃣：Bug 管理

1. 打开 Web UI → **错误集合** 选项卡
2. 查看 Bug 列表（按严重程度和状态筛选）
3. 点击 **查看详情** 查看 Bug 完整信息
4. 使用 **更新状态** 下拉菜单跟踪 Bug 处理进度

**Bug 自动分析**：
- 🤖 LLM 自动分析 Bug 类型（功能错误、设计缺陷、安全问题、系统错误）
- 📊 智能判定严重程度（一级~四级）
- 📸 自动保存失败页面截图（PDF 格式）
- 📝 提取测试用例步骤作为复现步骤，标记失败位置

**严重程度分级**：
| 级别 | 定义 | 颜色 | 处理策略 |
|------|------|------|----------|
| **一级（致命）** | 系统崩溃/核心功能完全失效/数据丢失 | 🔴 深红色 | 立即中止测试 |
| **二级（严重）** | 主要功能异常/存在重大安全隐患 | 🟠 橙色 | 立即中止测试 |
| **三级（一般）** | 次要功能异常/用户体验显著下降 | 🟡 黄色 | 继续测试并记录 |
| **四级（轻微）** | 优化建议/不影响使用的UI/文案问题 | ⚪ 灰色 | 继续测试并记录 |

**Bug 信息包含**：
- Bug 名称（测试用例标题）
- 定位地址（失败页面 URL）
- 错误类型和严重程度
- 复现步骤（✅ 成功步骤 / ❌ 失败步骤）
- 失败截图（PDF 格式）
- 预期结果 vs 实际结果
- LLM 分析的结果反馈
- Bug 状态（待处理/已确认/已修复/已关闭）

---

## 🔌 API 接口文档

### 测试用例相关

```
POST /api/test-cases/generate
  请求: {"requirement": "用户可以登录并查看课程"}
  响应: {"success": true, "test_cases": [...], "csv_file_path": "..."}

POST /api/test-cases/upload-file
  请求: FormData (file: 上传的文件)
  响应: {"success": true, "test_cases": [...], "uploaded_file": "..."}
  支持格式: .md / .txt / .pdf / .doc / .docx

GET /api/test-cases/list?limit=20&offset=0
  响应: {"success": true, "data": [...], "total": 10}

GET /api/test-cases/{case_id}
  响应: {"success": true, "data": {...}}
```

### 测试执行相关

```
POST /api/test-code/execute-browser-use
  请求: {
    "test_case_id": 1,
    "headless": true,
    "max_steps": 20,
    "use_vision": false
  }
  响应: {"success": true, "data": {"status": "pass", "total_steps": 15, ...}}

POST /api/test-code/pause-task/{task_id}
  响应: {"success": true, "message": "任务已暂停"}

POST /api/test-code/resume-task/{task_id}
  响应: {"success": true, "message": "任务已恢复"}

POST /api/test-code/stop-task/{task_id}
  响应: {"success": true, "message": "任务已停止"}

GET /api/test-code/task-status/{task_id}
  响应: {"success": true, "data": {"status": "running", ...}}
```

### 报告相关

```
POST /api/reports/generate
  请求: {"test_result_ids": [1, 2, 3], "format_type": "markdown"}
  响应: {"success": true, "data": {"id": 1, "title": "...", "details": "..."}}

GET /api/reports/list?limit=20&offset=0
  响应: {"success": true, "data": [...], "total": 5}

GET /api/reports/{report_id}
  响应: {"success": true, "data": {"id": 1, "details": "..."}}

GET /api/reports/{report_id}/download
  响应: 文件下载（HTML/Markdown/TXT 格式）
  Content-Type: text/html / text/markdown / text/plain
```

### Bug 管理相关

```
GET /api/bugs/list?limit=20&offset=0&severity_level=一级&status=待处理
  响应: {"success": true, "data": [...], "total": 5}

GET /api/bugs/{bug_id}
  响应: {"success": true, "data": {"id": 1, "bug_name": "...", ...}}

PUT /api/bugs/{bug_id}/status
  请求: {"status": "已确认"}
  响应: {"success": true, "message": "Bug 状态已更新为: 已确认"}
```

**详细 API 文档访问**：
- Swagger UI：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc

---

## 🗄️ 数据库模型

### TestCase（测试用例表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 ID |
| module | String(100) | 所属模块 |
| title | String(200) | 用例标题 |
| precondition | Text | 前置条件 |
| steps | Text | 测试步骤（JSON 数组） |
| expected | Text | 预期结果 |
| keywords | String(200) | 关键词 |
| priority | String(20) | 优先级（high/medium/low） |
| case_type | String(50) | 用例类型 |
| stage | String(50) | 适用阶段 |
| test_data | JSON | 测试数据 |
| csv_file_path | String(500) | 关联 CSV 文件路径 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### TestResult（测试结果表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 ID |
| test_case_id | Integer | 关联测试用例 ID |
| execution_log | LONGTEXT | 执行日志（JSON 格式，支持大量数据） |
| screenshots | JSON | 截图路径数组 |
| status | String(20) | 测试状态（pass/fail/error） |
| error_message | LONGTEXT | 错误信息（支持大量错误堆栈） |
| duration | Integer | 执行耗时（秒） |
| executed_at | DateTime | 执行时间 |

### TestReport（测试报告表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 ID |
| title | String(200) | 报告标题 |
| summary | JSON | 测试统计摘要（status/duration） |
| details | Text | 报告详细内容（HTML/Markdown） |
| file_path | String(500) | 报告文件路径 |
| format_type | String(20) | 格式类型（html/markdown/txt） |
| created_at | DateTime | 生成时间 |

### BugReport（Bug 报告表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 ID |
| bug_name | String(200) | Bug 名称（测试用例标题） |
| test_case_id | Integer | 关联测试用例 ID |
| test_result_id | Integer | 关联测试结果 ID |
| location_url | String(500) | 定位地址（失败页面 URL） |
| error_type | String(50) | 错误类型（功能错误/设计缺陷/安全问题/系统错误） |
| severity_level | String(20) | 严重程度（一级/二级/三级/四级） |
| reproduce_steps | Text | 复现步骤（JSON 数组） |
| screenshot_path | String(500) | 失败截图路径（PDF 格式） |
| result_feedback | Text | 结果反馈（LLM 分析） |
| expected_result | Text | 预期结果 |
| actual_result | Text | 实际结果 |
| status | String(20) | Bug 状态（待处理/已确认/已修复/已关闭） |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

---

## 🔐 安全说明

### 密码加密

所有密码字段自动进行 **MD5 加密处理**（32 位小写）：
```
原始密码：123456
MD5加密：e10adc3949ba59abbe56e057f20f883e
```

相关字段：password、passwd、pwd、密码 等

### API 密钥管理

- **LLM API Key**：存储在 `.env` 文件，通过环境变量加载
- **Firecrawl API Key**：同上
- **数据库密码**：通过 `.env` 配置，不提交版本控制

**建议**：
1. 将 `.env` 添加到 `.gitignore`
2. 部署前更换所有默认密钥
3. 定期轮换 API Key

---

## 🛠️ 开发指南

### 添加新的 LLM 调用

编辑 `Agent_server/Api_request/llm_client.py`：

```python
def your_new_method(self, param1, param2):
    """你的方法描述"""
    messages = [
        {"role": "system", "content": "系统提示词"},
        {"role": "user", "content": f"用户提示词：{param1}"}
    ]
    
    response = self.chat(messages=messages)
    return response
```

### 添加新的 API 路由

1. 创建新的 service 类（`Build_xxx/service.py`）
2. 创建 router 文件（`Build_xxx/router.py`）
3. 在 `app.py` 中注册路由：

```python
from Build_xxx.router import router as xxx_router
app.include_router(xxx_router)
```

### 代码规范

- **注释语言**：全部使用中文
- **异步编程**：使用 `async/await`，避免 `asyncio.run()`（ASGI 环境）
- **密码处理**：自动 MD5 加密
- **字符编码**：使用 UTF-8（含 BOM）

---

## 📦 依赖说明

### 核心依赖

| 包 | 用途 |
|-----|------|
| `fastapi==0.115.0` | Web 框架 |
| `browser-use==0.3.3` | 浏览器自动化 + AI 决策（使用原生 LLM） |
| `playwright==1.49.1` | 浏览器驱动 |
| `sqlalchemy==2.0.25` | ORM 数据库映射 |
| `pymysql==1.1.0` | MySQL 驱动 |
| `redis==5.0.1` | 缓存服务 |
| `PyPDF2==3.0.1` | PDF 文件解析 |
| `python-docx==1.1.0` | DOCX 文件解析 |
| `markdown==3.7` | Markdown 转 HTML |

**注意**：本项目使用 browser-use 0.3.3 原生的 LLM 抽象层，**不依赖 LangChain**。

### 前端依赖

| 包 | 用途 |
|-----|------|
| `vue@^3.4.0` | 前端框架 |
| `vite@^5.0.0` | 构建工具 |
| `element-plus@^2.5.0` | UI 组件库 |
| `axios@^1.6.0` | HTTP 客户端 |

---

## 🔧 技术难点与解决方案

### 问题 1：Browser-Use 与 LLM 集成兼容性

**问题描述**：
- 初始尝试使用 LangChain 的 `ChatOpenAI` 与 browser-use 0.3.3 集成
- 出现多个错误：`items` 错误、消息类型不兼容、`usage` 属性缺失

**根本原因**：
- browser-use 0.3.3 有自己完整的 LLM 抽象层（`browser_use.llm.base.BaseChatModel`）
- 不依赖 LangChain，强行适配导致各种兼容性问题

**解决方案**：
- ✅ 使用 browser-use 0.3.3 原生的 `ChatOpenAI` 类
- ✅ 移除所有 LangChain 依赖和适配层
- ✅ 直接使用 browser-use 的 `Agent` 类

**关键代码**：
```python
# 使用 browser-use 原生 LLM
from browser_use.llm.openai.chat import ChatOpenAI
from browser_use import Agent

llm = ChatOpenAI(
    model='qwen/qwen3-vl-235b-a22b-instruct',
    api_key='your_key',
    base_url='https://api.ppinfra.com/openai',
    temperature=0.0,
)

agent = Agent(task="your task", llm=llm)
```

**参考文档**：
- [Browser-Use 0.3.3 集成指南](./BROWSER_USE_0.3.3_INTEGRATION.md)
- [实施指南](./IMPLEMENTATION_GUIDE.md)
- [最终修复方案](./Agent_server/FINAL_FIX.md)

### 问题 2：Qwen 模型与 Browser-Use 的兼容性

**解决方案**：
- Qwen 提供 OpenAI 兼容接口，可直接使用 browser-use 的 `ChatOpenAI`
- 设置正确的 `base_url` 和 `api_key`
- 调整 `temperature` 参数以提高输出稳定性

### 问题 3：异步编程与 Windows 环境

**解决方案**：
- 使用 `asyncio.WindowsProactorEventLoopPolicy()` 确保 Windows 兼容性
- 避免在 ASGI 环境中使用 `asyncio.run()`
- 正确处理异步上下文和资源清理

---

## 🙏 致谢与引用

本项目的 Browser-Use 增强核心模块（`browser_use_core/`）**借鉴并改编自**：

**[web-ui](https://github.com/browser-use/web-ui)** by Gregor Žunič  
- 提供了 `BrowserUseAgent`、`CustomBrowser`、`CustomController` 等核心组件
- 完整的 MCP 工具集成架构
- 增强的错误处理和控制流

**致谢对象**：
- ✅ Gregor Žunič 及 browser-use 团队
- ✅ Anthropic（Claude）提供的 LLM 技术基础
- ✅ Qwen（阿里巴巴）提供的多模态 LLM 支持

---

---

## 🐛 问题反馈

如遇到任何问题，请：

1. 查看 [API 文档](http://localhost:8000/redoc)
2. 检查 `.env` 配置是否正确
3. 查看启动日志是否有错误提示
4. 确认 MySQL 和 Redis 服务已启动
5. **运行快速修复脚本**：`quick_fix.bat`（Windows）
6. **查看详细故障排查指南**：[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

**常见问题**：

| 问题 | 解决方案 |
|------|--------|
| `LLM API Key 无效` | 检查 `.env` 中的 `LLM_API_KEY` 是否正确 |
| `数据库连接失败` | 确认 MySQL 正在运行，检查 DB_HOST/DB_PORT/DB_USER |
| `前端无法连接后端` | 确认后端运行在 8000 端口，检查 CORS 配置 |
| `Browser-Use 执行失败 (items 错误)` | 运行 `python test_llm_connection.py` 测试 LLM 连接，参考 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) |
| `浏览器停留在 about:blank` | 确保测试用例第一步包含完整的 URL，检查 LLM 响应格式 |
| `playwright 未安装` | 运行 `playwright install chromium` |

### 🔧 快速修复

如果遇到 Browser-Use 执行问题，运行快速修复脚本：

```bash
# Windows
cd Ai_Test_Agent
quick_fix.bat

# 或手动执行
cd Agent_server
pip install -r requirements.txt
playwright install chromium
python test_llm_connection.py
```

---

## 📚 相关资源

- **Browser-Use 官方文档**：https://github.com/browser-use/browser-use
- **Qwen 模型文档**：https://dashscope.aliyun.com/api-details/qwenvl
- **FastAPI 官方文档**：https://fastapi.tiangolo.com/
- **Vue 3 官方文档**：https://vuejs.org/

---

## 📞 联系方式

如有问题或建议，欢迎通过以下方式联系：
- **作者**：程序员Eighteen
- **邮箱**：32732495516@qq.com & eighteenthstuai@gmail.com


### 🤝 参与贡献

我们欢迎所有形式的贡献：

1. **报告 Bug**：如遇到问题，请详细描述复现步骤和错误日志
2. **功能建议**：欢迎提出改进意见和新功能想法
3. **代码贡献**：提交 Pull Request 前，请确保：
   - 代码遵循项目规范（中文注释、异步最佳实践）
   - 包含必要的单元测试
   - 更新相关文档

### 📧 沟通方式

| 方式 | 说明 |
|------|------|
| **GitHub Issues** | 报告 Bug、讨论功能需求 |
| **GitHub Discussions** | 技术讨论、经验分享 |
| **代码审查** | 发起 Pull Request 进行代码审查 |

### 🔗 相关链接

- **项目源码**：ttps://github.com/eighteenth-last/Ai_Test_Agent.git
- **问题反馈**：提交 Issue 或讨论
- **技术支持**：参考 API 文档或常见问题

### 💡 反馈渠道

- 如有紧急问题或安全问题，请通过私密方式反馈
- 对于一般问题，建议在 GitHub Issues 中公开讨论（便于他人参考）
- 欢迎分享你的使用经验和成功案例

---

---

## 📊 项目统计

- **后端代码行数**：~3000+
- **前端代码行数**：~2000+
- **支持的测试场景**：功能测试、接口测试、UI 自动化
- **平均执行速度**：20-30 秒/个测试用例
- **成功率**：≥ 85%（取决于网页复杂度）
- **Browser-Use 版本**：0.3.3（稳定版）
- **LLM 支持**：Qwen 3 VL（通过 OpenAI 兼容接口）
- **支持文档格式**：MD / TXT / PDF / DOC / DOCX
- **任务控制**：支持暂停/恢复/停止
- **报告格式**：HTML（优化布局，支持下载）

---

## 🎉 项目状态

✅ **项目已成功运行！**

经过深入调试和优化，项目已完全解决 browser-use 与 LLM 的集成问题：
- ✅ 使用 browser-use 0.3.3 原生 API
- ✅ 移除 LangChain 依赖，简化架构
- ✅ 完整的测试用例生成、执行、报告流程
- ✅ 支持 Qwen 3 VL 多模态大模型

**关键改进**：
1. 重写 `browser_use_service.py`，使用原生 API
2. 移除复杂的适配层和包装器
3. 优化 LLM 配置和参数
4. 完善错误处理和日志输出
5. 添加文件上传功能，支持多种文档格式
6. 实现任务管理器，支持暂停/恢复/停止
7. 优化报告布局，支持 HTML 下载
8. 数据库字段升级为 LONGTEXT，支持大量日志
9. **新增 Bug 智能管理系统，自动分析和跟踪**
10. **智能提取复现步骤，自动保存失败截图**

---

**祝你使用愉快！🎉**

如有问题或建议，欢迎反馈或贡献代码。

---

<sub>最后更新：2025-12-11 | 版本：1.2.0</sub>

## 🆕 更新日志

### v1.2.0 (2025-12-11)
- ✨ 新增 Bug 智能管理功能，自动分析严重程度（一级~四级）
- ✨ 新增 Bug 复现步骤自动提取，标记成功/失败位置
- ✨ 新增失败页面自动截图（PDF 格式），保存到 bug_floder 目录
- ✨ 新增 Bug 状态跟踪（待处理/已确认/已修复/已关闭）
- 🎨 新增错误集合页面，支持按严重程度和状态筛选
- 🤖 LLM 自动分析 Bug 类型和结果反馈
- 🔧 一级/二级 Bug 自动中止测试，三级/四级继续执行
- 📝 完善 Bug 管理文档和使用指南

### v1.1.1 (2025-12-11)
- 🎨 优化测试报告标题，使用测试用例名称替代时间戳
- 🎨 简化测试汇总显示，只显示"成功/失败"和"耗时"
- 🔧 前端兼容新旧报告格式
- 📝 更新报告列表修改说明文档

### v1.1.0 (2025-12-11)
- ✨ 新增文件上传功能，支持 MD/TXT/PDF/DOC/DOCX 格式
- ✨ 新增任务管理器，支持暂停/恢复/停止测试执行
- ✨ 新增报告下载功能，支持 HTML 格式导出
- 🎨 优化报告布局，采用现代化设计，间距合理
- 🔧 数据库字段升级为 LONGTEXT，支持大量执行日志
- 🔧 优化浏览器窗口配置，默认 1920x1200 分辨率
- 🐛 修复停止任务时浏览器继续执行的问题
- 📝 更新 README 文档，补充最新功能说明

### v1.0.1 (2025-12-10)
- 🐛 修复 Browser-Use 与 LLM 集成兼容性问题
- 🔧 移除 LangChain 依赖，使用 browser-use 原生 API
- 📝 完善技术文档和故障排查指南

### v1.0.0 (2025-12-09)
- 🎉 项目初始版本发布
- ✨ 实现测试用例生成、执行、报告三大核心功能
- ✨ 集成 Browser-Use 0.3.3 和 Qwen 3 VL
