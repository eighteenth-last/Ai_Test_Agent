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
| **用例编辑管理** | 支持在线编辑测试用例，包括模块、标题、步骤、优先级、用例类型等字段 |
| **AI 智能执行** | Browser-Use + LLM 实时决策，无需编写代码，支持暂停/恢复/停止控制 |
| **自动答题功能** | 内置智能答题，支持单选、多选、判断、填空等 6 种题型，平均 0.5 秒/题 |
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
- ✅ **自动答题**：内置智能答题功能，支持单选、多选、判断、填空等多种题型
- ✅ **用例编辑**：支持在线编辑测试用例，标准化用例类型（功能/单元/接口/安全/性能）
- ✅ **提示词管理**：所有 LLM 提示词集中在 `prompts.py` 统一管理，易于维护和优化
- ✅ **架构优化**：使用 Browser-Use 原生 API，移除 LangChain 依赖，简化集成

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
│   │   ├── llm_client.py          # Qwen API 封装（生成用例/报告/Bug分析）
│   │   └── prompts.py             # Prompt 模板库（统一管理所有提示词）
│   │
│   ├── Build_tests/                # 测试用例生成模块
│   │   ├── service.py             # 业务逻辑（调用 LLM）
│   │   └── router.py              # FastAPI 路由定义
│   │
│   ├── Build_test_code/            # 测试执行模块（Browser-Use）
│   │   ├── browser_use_service.py # 核心执行服务
│   │   ├── custom_actions.py      # 自定义答题 Action
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
│   ├── auto_answer.js             # 自动答题脚本（备用方案）
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

**用例类型标准化**：
系统支持 5 种标准用例类型，LLM 会根据需求内容智能选择：
- **功能测试**：测试系统功能是否符合需求（默认）
- **单元测试**：测试单个模块或函数
- **接口测试**：测试 API 接口
- **安全测试**：测试系统安全性
- **性能测试**：测试系统性能和负载

**在线编辑功能**：
1. 在测试用例列表中点击 **查看详情**
2. 点击 **编辑** 按钮进入编辑模式
3. 修改模块、标题、步骤、优先级、用例类型等字段
4. 支持添加/删除测试步骤
5. 点击 **保存** 提交修改

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

**自动答题功能**：
- 🤖 **智能检测**：自动识别答题页面（根据测试用例关键词）
- 📝 **多题型支持**：单选、多选、判断、填空、简答、下拉框
- ⚡ **无缝集成**：作为 Browser-Use 的内置 Action，大模型可直接调用
- 🎯 **自动作答**：使用 Playwright API 直接操作页面元素
- ✅ **智能继续**：答题完成后，大模型自动继续执行后续步骤

**答题工作流程**：
1. 系统检测测试用例是否包含答题关键词（错题再练、错题集、练习等）
2. 如需答题，自动注册 `auto_answer` action 到 Browser-Use
3. 大模型进入答题页面后，调用 `auto_answer` action
4. 系统自动检测题目数量和类型，逐题作答
5. 答题完成后，大模型继续执行后续步骤（如点击提交按钮）

### 场景 3️⃣：查看测试报告

1. 打开 Web UI → **测试报告** 选项卡
2. 查看报告列表（包含通过率、耗时等统计）
3. 点击 **查看报告** 查看详细内容
4. 点击 **下载报告** 按钮导出 HTML 文件

**报告内容包含**：
- 测试概览（仅多用例执行时显示：通过数、失败数、总耗时）
- 每个用例的执行详情
- 详细的 Agent 行为分析（思考过程和操作路径）
- 失败原因诊断和修复建议

**报告特性**：
- 📊 现代化设计，间距合理，阅读体验佳
- 🎨 使用卡片布局和颜色标识
- 📥 支持一键下载 HTML 格式
- 💾 离线可查看，包含完整样式
- 🎯 智能适配：单用例不显示概览，多用例显示完整统计

### 场景 4️⃣：自动答题功能

**功能说明**：
系统内置智能答题功能，当测试用例涉及答题场景时，AI 会自动完成所有题目的作答。

**支持的题型**：
- ✅ 单选题（自动选择第一个选项）
- ✅ 多选题（自动选择第一个选项）
- ✅ 判断题（自动选择"正确"）
- ✅ 填空题（自动填入"答案"）
- ✅ 简答题（自动填入"答案"）
- ✅ 下拉框选择（自动选择第一个非空选项）

**使用方式**：

1. **自动检测**：
   - 系统会自动检测测试用例步骤中的关键词
   - 关键词包括：错题再练、错题集、练习、答题、做题等
   - 如果检测到关键词，自动启用答题功能

2. **执行流程**：
   ```
   开始测试 → 进入答题页面 → AI 调用 auto_answer → 自动完成所有题目 → 继续后续步骤
   ```

3. **日志输出**：
   ```
   [BrowserUse] 该测试用例需要答题，注册自定义答题 action
   [AutoAnswer] 🎯 开始自动答题...
   [AutoAnswer] ✓ 检测到 20 道题目
   [AutoAnswer] 正在作答第 1/20 题...
   [AutoAnswer] 正在作答第 2/20 题...
   ...
   [AutoAnswer] ✅ 所有题目已作答完成！共完成 20 道题
   ```

4. **性能指标**：
   - 平均答题速度：0.5 秒/题
   - 支持题目数量：1-100 题
   - 成功率：≥ 95%

**技术实现**：
- 使用 Playwright API 直接操作页面元素
- 作为 Browser-Use 的自定义 Action 实现
- 无需独立脚本和 CDP 连接
- 大模型可以直接调用 `auto_answer` action

**注意事项**：
- 答题策略为默认策略（选择第一个选项或填入"答案"）
- 如需智能答题（根据题目内容选择正确答案），需集成答案数据库
- 答题完成后，大模型会自动继续执行后续步骤（如点击提交按钮）

### 场景 5️⃣：Bug 管理

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

PUT /api/test-cases/{case_id}
  请求: {
    "module": "模块名",
    "title": "用例标题",
    "precondition": "前置条件",
    "steps": ["步骤1", "步骤2"],
    "expected": "预期结果",
    "keywords": "关键词",
    "priority": "3",
    "case_type": "功能测试",
    "stage": "功能测试阶段"
  }
  响应: {"success": true, "message": "测试用例更新成功"}
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

**步骤 1：在 `prompts.py` 中定义提示词模板**

编辑 `Agent_server/Api_request/prompts.py`：

```python
# 新功能的系统提示词
YOUR_FEATURE_SYSTEM = """你是 AI XXX 专家。..."""

# 新功能的用户提示词模板
YOUR_FEATURE_USER_TEMPLATE = """根据以下输入生成结果：

输入内容：{input_param}

输出格式：
{{
  "result": "..."
}}
"""
```

**步骤 2：在 `llm_client.py` 中实现方法**

编辑 `Agent_server/Api_request/llm_client.py`：

```python
from Api_request.prompts import YOUR_FEATURE_SYSTEM, YOUR_FEATURE_USER_TEMPLATE

def your_new_method(self, param1, param2):
    """你的方法描述"""
    user_prompt = YOUR_FEATURE_USER_TEMPLATE.format(
        input_param=param1
    )
    
    messages = [
        {"role": "system", "content": YOUR_FEATURE_SYSTEM},
        {"role": "user", "content": user_prompt}
    ]
    
    response = self.chat(messages=messages)
    return response
```

**优势**：
- 提示词集中管理，易于维护和版本控制
- 代码逻辑与提示词分离，职责清晰
- 便于团队协作和提示词优化

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
- **提示词管理**：所有 LLM 提示词必须在 `prompts.py` 中定义，不要硬编码在业务代码中
- **用例类型**：必须使用标准的 5 种类型（功能/单元/接口/安全/性能测试）
- **优先级**：使用数字 1-4 表示，1 级最高，4 级最低

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

### 问题 0：答题功能误触发

**问题描述**：
- 测试用例明确要求"不作答任何题目，直接点击提交按钮"
- 但系统因检测到"错题再练"关键词而注册了答题 action
- 导致大模型在页面提示后主动调用答题方法，违背测试意图

**根本原因**：
- 只检测正向关键词（错题再练、答题等），未考虑否定场景
- 没有识别"不作答"、"直接提交"等否定指令

**解决方案**：
- ✅ 在 `_need_auto_answer` 方法中添加否定关键词检测
- ✅ 否定关键词包括：不作答、不答题、直接提交、跳过答题等
- ✅ 如果检测到否定关键词，则不注册答题 action
- ✅ 根据是否启用答题功能，生成不同的任务提示词

**关键代码**：
```python
@staticmethod
def _need_auto_answer(test_case: TestCase) -> bool:
    """检查是否需要自动答题（考虑否定关键词）"""
    steps_text = ' '.join(test_case.steps).lower()
    
    # 否定关键词
    negative_keywords = ['不作答', '不答题', '直接提交', '跳过答题', '不要答题']
    if any(keyword in steps_text for keyword in negative_keywords):
        return False
    
    # 正向关键词
    return any(keyword in steps_text for keyword in ANSWER_KEYWORDS)
```

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

### 问题 4：自动答题功能集成

**问题描述**：
- 初始方案使用独立的 Node.js/Python 脚本通过 CDP 连接浏览器
- 需要监控线程检测 URL 变化，触发答题脚本
- 进程间通信复杂，端口配置繁琐（9222）

**根本原因**：
- 将答题功能作为外部脚本，与 Browser-Use 分离
- 需要额外的进程管理和通信机制
- 依赖 CDP 协议和 websockets 库

**解决方案**：
- ✅ 将答题功能实现为 Browser-Use 的自定义 Action
- ✅ 使用 Playwright API 直接操作页面，无需 CDP 连接
- ✅ 大模型可以直接调用 `auto_answer` action
- ✅ 不需要独立脚本、监控线程和端口配置

**关键代码**：
```python
# 注册自定义答题 Action
@controller.registry.action(
    '自动答题 - 检测页面上的题目并自动作答',
)
async def auto_answer(page: Page):
    return await auto_answer_questions(page)

# 在 Agent 中使用
agent = Agent(
    task=task_description,
    llm=llm,
    browser=browser,
    controller=controller,  # 包含自定义 action
)
```

**优势对比**：

| 特性 | 旧方案（已废弃） | 新方案（当前） |
|------|----------------|---------------|
| 实现方式 | 独立脚本 + CDP | Browser-Use Action |
| 浏览器连接 | CDP (端口 9222) | Playwright API |
| 进程管理 | 需要独立进程 | 无需额外进程 |
| 监控机制 | URL 监控线程 | 大模型主动调用 |
| 代码复杂度 | 高（多文件） | 低（单文件） |
| 维护成本 | 高 | 低 |
| 集成度 | 松耦合 | 紧耦合 |

**参考文档**：
- [答题功能集成完成说明](./答题功能集成完成说明.md)
- [自定义 Actions 实现](./Ai_Test_Agent/Agent_server/Build_test_code/custom_actions.py)

### 问题 5：AI 思考内容英文化

**问题描述**：
- Browser-Use Agent 的思考过程（thinking）显示为英文
- 执行动作名称也是英文，不符合中文优先原则

**解决方案**：
- ✅ 在创建 Agent 时添加 `extend_system_message` 参数，明确要求使用中文
- ✅ 添加 `_format_action_name` 方法，将动作名称格式化为中文描述
- ✅ 在执行日志中显示中文化的思考和动作

**关键代码**：
```python
# 中文化系统提示
chinese_instruction = """
重要：你必须使用中文进行思考和回复。
所有的思考过程（thinking）必须用中文表达。
"""

agent = Agent(
    task=task_description,
    llm=llm,
    browser=browser,
    controller=controller,
    extend_system_message=chinese_instruction
)

# 格式化动作名称
@staticmethod
def _format_action_name(action_name: str) -> str:
    """将动作名称格式化为中文描述"""
    action_map = {
        'go_to_url': '访问页面',
        'click_element': '点击元素',
        'input_text': '输入文本',
        # ...
    }
    return action_map.get(action_name, action_name)
```

### 问题 6：测试报告概览显示逻辑

**问题描述**：
- 单个测试用例执行时，报告仍显示"测试概览"（总用例数 0 个等）
- 这在单用例场景下显得冗余和不专业

**解决方案**：
- ✅ 修改 `generate_test_report` 方法，根据用例数量选择不同的 prompt 模板
- ✅ 单个用例：使用 `REPORT_USER_SINGLE_CASE`，不生成测试概览
- ✅ 多个用例：使用 `REPORT_USER_MULTIPLE_CASES`，显示完整概览

**关键代码**：
```python
def generate_test_report(self, test_results, summary, format_type="markdown"):
    total_cases = summary.get('total', len(test_results))
    is_single_case = total_cases == 1
    
    if is_single_case:
        user_prompt = REPORT_USER_SINGLE_CASE.format(
            test_results=test_results_json,
            format_type=format_type.upper()
        )
    else:
        user_prompt = REPORT_USER_MULTIPLE_CASES.format(
            total=summary.get('total', 0),
            pass_count=summary.get('pass', 0),
            # ...
        )
```

### 问题 7：提示词管理混乱

**问题描述**：
- `llm_client.py` 中硬编码了大量提示词
- `prompts.py` 中有专门的模板但未被使用
- 提示词分散在多个文件，难以维护和优化

**解决方案**：
- ✅ 将所有提示词迁移到 `prompts.py` 统一管理
- ✅ 添加了 `REPORT_SYSTEM`, `REPORT_USER_SINGLE_CASE`, `REPORT_USER_MULTIPLE_CASES`, `BUG_ANALYSIS_SYSTEM`
- ✅ `llm_client.py` 导入并使用这些模板，通过 `.format()` 填充参数

**优势**：
- 统一管理：所有提示词在一个文件中，便于查找和修改
- 易于维护：修改提示词不需要改动业务逻辑代码
- 代码整洁：业务代码专注于逻辑，提示词专注于内容
- 版本控制：提示词变更历史清晰可追溯

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

- **后端代码行数**：~3500+
- **前端代码行数**：~2500+
- **支持的测试场景**：功能测试、单元测试、接口测试、安全测试、性能测试
- **平均执行速度**：20-30 秒/个测试用例
- **成功率**：≥ 85%（取决于网页复杂度）
- **Browser-Use 版本**：0.3.3（稳定版，使用原生 API）
- **LLM 支持**：Qwen 3 VL（通过 OpenAI 兼容接口）
- **支持文档格式**：MD / TXT / PDF / DOC / DOCX
- **任务控制**：支持暂停/恢复/停止
- **报告格式**：HTML（优化布局，支持下载，智能适配单/多用例）
- **自动答题**：支持 6 种题型，平均 0.5 秒/题
- **用例类型**：5 种标准类型（功能/单元/接口/安全/性能）
- **提示词模板**：10+ 个专业模板，集中管理
- **Bug 分析**：4 级严重程度，自动决策是否中止测试

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
11. **集成自动答题功能，作为 Browser-Use 的内置 Action**
12. **支持 6 种题型，无需独立脚本和 CDP 连接**
13. **实现测试用例在线编辑功能**
14. **标准化用例类型为 5 种（功能/单元/接口/安全/性能）**
15. **提示词统一管理，迁移到 `prompts.py`**
16. **修复答题功能误触发问题，支持否定关键词检测**
17. **AI 思考内容中文化，优化用户体验**
18. **智能报告生成：单用例不显示概览，多用例显示统计**

---

**祝你使用愉快！🎉**

如有问题或建议，欢迎反馈或贡献代码。

---

<sub>最后更新：2025-12-12 | 版本：1.2.1</sub>

## 🆕 更新日志

### v1.2.1 (2025-12-12)
- ✨ 新增自动答题功能，作为 Browser-Use 的内置 Action
- ✨ 支持 6 种题型：单选、多选、判断、填空、简答、下拉框
- ✨ 新增测试用例在线编辑功能，支持修改所有字段
- ✨ 标准化用例类型为 5 种：功能/单元/接口/安全/性能测试
- 🔧 使用 Playwright API 直接操作页面，无需 CDP 连接
- � 移除独立答题题脚本和监控线程，简化架构
- 🔧 提示词统一迁移到 `prompts.py` 集中管理
- 🔧 优化报告生成逻辑：单用例不显示概览，多用例显示完整统计
- 🔧 修复答题功能误触发问题：检测否定关键词（不作答、直接提交等）
- 🤖 大模型可直接调用 `auto_answer` action
- 🎨 AI 思考内容中文化，添加动作名称格式化
- 📝 完善自动答题文档和使用说明
- 🎯 智能检测答题页面，自动注册答题功能

### v1.2.0 (2025-12-11)
- ✨ 新增 Bug 智能管理功能，自动分析严重程度（一级~四级）
- ✨ 新增 Bug 复现步骤自动提取，标记成功/失败位置
- ✨ 新增失败页面自动截图（PDF 格式），保存到 bug_floder 目录
- ✨ 新增 Bug 状态跟踪（待处理/已确认/已修复/已关闭）
- 🎨 新增错误集合页面，支持按严重程度和状态筛选
- 🤖 LLM 自动分析 Bug 类型和结果反馈
- 🔧 一级/二级 Bug 自动中止测试，三级/四级继续执行
- 📝 完善 Bug 管理文档和使用指南
- 📝 添加分页插件

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
