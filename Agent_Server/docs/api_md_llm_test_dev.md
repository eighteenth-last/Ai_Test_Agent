# Web 端：选择测试用例 → 智能匹配 MinIO 接口文件 → 执行接口测试 → 报告入库 → BUG 入库并邮件通知（开发文档）

## 目标

实现 Web 端完整闭环：

1. Web 端选择测试用例（来自 `execution_cases`）
2. 大模型根据“测试用例文本”在 MinIO 的接口 Markdown 文件中检索/匹配，给出最适合的接口文件，并在前端展示
3. 用户确认接口文件无误后提交执行
4. 后端执行接口测试并保存结果，生成测试报告写入 `test_reports`
5. 若测试过程中接口报错/异常：写入 `bug_reports`，并自动给 `auto_receive_bug=1` 联系人发送邮件（写入 `email_records`）

## 当前代码可复用点

- 用例：`execution_cases`（见 [ExecutionCase](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/database/connection.py#L47-L65)）
- 结果：`test_records`（见 [TestRecord](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/database/connection.py#L77-L94)）
- 报告：`test_reports`（见 [TestReport](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/database/connection.py#L101-L113)）
- BUG：`bug_reports`（见 [BugReport](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/database/connection.py#L115-L136)）
- 报告生成：`Build_Report.service.TestReportService.generate_report`（见 [TestReportService.generate_report](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/Build_Report/service.py#L13-L145)）
- BUG 分析/入库：`Bug_Analysis.service.BugAnalysisService.create_bug_report`（见 [BugAnalysisService.create_bug_report](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/Bug_Analysis/service.py#L22-L123)）
- 联系人（自动接收 BUG 标记）：`contacts.auto_receive_bug`（见 [Contact_manage](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/Contact_manage/router.py#L20-L41)）
- LLM：复用 [LLMClient](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/llm/client.py) 或 `llm.get_llm_client()` 封装

## MinIO 配置

通过环境变量读取：

- `MINIO_ENDPOINT=http://localhost:9000`
- `MINIO_ACCESS_KEY=minioadmin`
- `MINIO_SECRET_KEY=minioadmin`
- `MINIO_BUCKET=aitest`
- `MINIO_REGION=cn-beijing-1`
- `MINIO_SECURE=false`

对象 Key 建议规范化（便于检索与版本追溯）：

- `api-md/{service_name}/{yyyyMMddHHmmss}/{original_filename}.md`

## 业务流程（Web 端交互）

### 1）选择测试用例

用户在 Web 端勾选多个测试用例（`execution_cases.id`）。

提交给后端用于匹配的最小信息：

- `test_case_ids: number[]`
- `service_name?: string`（可选，用于缩小匹配范围）

### 2）智能匹配最适合的接口（endpoint 级匹配）

目标是“匹配到具体接口（method + path）”，并展示给用户确认。接口来自已上传到 MinIO 的 Markdown 接口文件（例如 [answerInfo.md](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/answerInfo.md) 这类单文件），系统需要先解析出 endpoints，再做匹配。

推荐两段式匹配（兼顾速度与效果）：

1. 粗筛（非 LLM）：先筛候选 endpoints topK
   - 基于 `method/path/summary` 的关键词 overlap（来自 md 解析结果）
   - 若用例文本包含类似 `GET /xxx` 或 ``/xxx``，优先做 path 精确/前缀匹配
2. 精排（LLM）：将“测试用例文本 + 候选 endpoints（method/path/summary + 来源文件）”交给 LLM，输出 top1 推荐接口与理由、置信度

前端展示内容：

- 推荐接口（top1）与候选接口列表（topK）
- 推荐接口详情预览：`method/path/summary` + `来源文件(original_filename/minio_key)`（用于用户确认）

### 3）用户确认并提交执行

用户确认推荐文件无误后提交执行，后端接收：

- `test_case_ids: number[]`
- `spec_version_id: number`（用户确认的接口文件版本）
- `environment_id: number` 或 `environment: { base_url, headers?, variables? }`
- `mode: "smoke_only" | "llm_enhanced"`（默认 `llm_enhanced`）

### 4）执行接口测试（endpoint 级匹配 + DSL 生成 + Runner）

后端执行步骤（建议）：

1. 读取用例：按 `test_case_ids` 查询 `execution_cases`
2. 读取接口文件：按 `spec_version_id` 从 MinIO 拉取 md（若已解析入库则不必重复拉全文）
3. 解析接口：得到 endpoints（method/path/params/examples/notes）
4. 为每条测试用例选择最合适 endpoint（规则优先，必要时 LLM）
5. 生成可执行 DSL（smoke 或 LLM enhanced）
6. Runner 执行 HTTP 请求与断言
7. 将每条执行写入 `test_records`（用于生成报告、追溯、与 BUG 关联）
8. 统一调用 `TestReportService.generate_report(test_result_ids=[...])` 写入 `test_reports`

### 5）异常处理：生成 BUG 报告并自动邮件通知

触发条件建议：

- Runner 报错（网络错误、超时、5xx、JSON 解析失败、断言异常、代码异常）
- 记录到 `test_records.status = fail` 且 `error_message` 不为空

执行完成后统一处理：

1. 对每条失败记录创建 `bug_reports`（复用 `BugAnalysisService.create_bug_report` 或实现接口测试专用版本）
2. 查询 `contacts` 中 `auto_receive_bug=1` 的联系人
3. 使用激活的 `email_config` 发送邮件，并写 `email_records`

## 数据模型（落地方案）

### 1）接口文件索引（新增表）

为实现“在 MinIO 多份 md 文件中搜索并展示最适合文件”，需要把文件元数据入库。

建议新增两张表（命名可按项目风格调整）：

`api_spec`
- `id` bigint pk
- `service_name` varchar(100) null
- `created_at` datetime

`api_spec_version`
- `id` bigint pk
- `spec_id` bigint not null index
- `original_filename` varchar(255) not null
- `minio_bucket` varchar(100) not null
- `minio_key` varchar(500) not null
- `file_hash` char(64) not null
- `etag` varchar(200) null
- `parse_summary` text null（用于 LLM 匹配的“文件摘要”）
- `parse_warnings` json null
- `created_at` datetime

`parse_summary` 建议包含：

- endpoint 数量
- endpoint 列表摘要（method/path/summary，截断）
- 文档中出现的业务关键词（截断）

### 2）接口资产（新增表）

`api_endpoint`
- `id` bigint pk
- `spec_version_id` bigint not null index
- `method` varchar(10) not null
- `path` varchar(300) not null
- `summary` varchar(300) null
- `description` longtext null
- `params` json null
- `success_example` json null
- `error_example` json null
- `notes` longtext null
- `created_at` datetime

索引建议：

- `idx_endpoint_spec_version`(`spec_version_id`)
- `idx_endpoint_method_path`(`method`,`path`)

### 3）结果、报告、BUG、邮件（复用现有表）

接口测试执行后使用现有表沉淀：

- `test_records`：每条用例一条执行记录（用于报告生成）
  - `test_case_id = execution_cases.id`
  - `execution_log`：建议保存结构化 JSON 文本，包含：
    - 选中的 `spec_version_id` / `minio_key`
    - endpoint（method/path）
    - request（url/headers/query/body）
    - response（status/headers/body_trunc/json_trunc）
    - assertions（断言列表与结果）
  - `status`：pass/fail
  - `error_message`：失败原因
  - `duration`：耗时
- `test_reports`：每次执行结束写一条报告
  - 使用 [TestReportService.generate_report](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/Build_Report/service.py#L13-L145)
- `bug_reports`：失败用例写入 bug 表
  - 建议将“接口请求/响应摘要”和“失败原因”映射到 `BugReport.description/actual_result/result_feedback`
- `email_records`：邮件发送记录（供邮件管理页面追溯）

## LLM 设计（两次调用）

### 1）文件级匹配（选择最适合 md 文件）

输入：

- 用例文本：title/steps/expected（多条用例可合并摘要）
- 候选文件列表：`spec_version_id + original_filename + parse_summary`

输出 JSON（固定结构）：

```json
{
  "recommended": { "spec_version_id": 1, "confidence": 0.83, "reason": "..." },
  "candidates": [
    { "spec_version_id": 2, "confidence": 0.55, "reason": "..." }
  ]
}
```

### 2）endpoint 级匹配 + DSL 生成（执行前）

输入：

- 用户确认的 spec_version（必要时附带 endpoint 列表）
- 单条用例文本（title/steps/expected/test_data）

输出：

- endpoint 选择：`{method,path}`
- 可执行 DSL（包含请求构造、断言、止损配置）

## 后端接口（FastAPI）建议

### 1）上传接口文件（入库索引 + 解析）

`POST /api/specs/import-md`
- form-data：
  - `file`：md
  - `service_name`：可选
- 返回：
  - `spec_version_id`
  - `original_filename`
  - `minio_key`
  - `parse_summary`
  - `endpoint_count`
  - `warnings[]`

### 2）智能匹配接口文件（展示给用户确认）

`POST /api/api-test/match-spec`
- body：
  - `test_case_ids: number[]`
  - `top_k?: number`（默认 5）
  - `service_name?: string`
- 返回：
  - `recommended`: `{ spec_version_id, original_filename, minio_key, confidence, reason }`
  - `candidates[]`: 同结构
  - `preview_endpoints[]`: `[{method,path,summary}]`（用于前端预览）

### 3）确认后执行（生成记录 + 报告 + BUG + 邮件）

`POST /api/api-test/execute`
- body：
  - `test_case_ids: number[]`
  - `spec_version_id: number`
  - `environment_id?: number`
  - `environment?: { base_url: string, headers?: object, variables?: object }`
  - `mode?: "smoke_only" | "llm_enhanced"`
- 返回：
  - `test_record_ids: number[]`
  - `report_id: number`
  - `bug_report_ids: number[]`
  - `summary`

### 4）报告与 BUG 查询（复用已有路由）

- 报告：见 [Build_Report.router](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/Build_Report/router.py)
- BUG：见 [Bug_Analysis.router](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/Bug_Analysis/router.py)
- 联系人：见 [Contact_manage.router](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/Contact_manage/router.py)

## 前端（ApiTest.vue）页面改造要点

将 [ApiTest.vue](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/agent_web_server/src/views/test/ApiTest.vue) 从占位页面改为三步式：

1. 选择用例（多选）
2. 智能匹配接口文件（展示推荐与候选，展示接口预览）
3. 确认执行（展示执行摘要、报告入口、BUG 入口）

## BUG 邮件通知（自动接收 BUG）

### 收件人

从 `contacts` 筛选 `auto_receive_bug=1`（见 [contacts.auto_receive_bug](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/database/connection.py#L174-L185)）。

### 邮件配置

使用 `email_config` 中 `is_active=1` 的配置（见 [EmailConfig](file:///r:/Code/Python/Python_selenium_test_Agent/Ai_Test_Agent/Agent_Server/database/connection.py#L205-L220)）。

### 邮件内容（建议汇总一封）

- subject：`[AI Test Agent][BUG] 接口测试失败汇总 - yyyy-MM-dd HH:mm`
- 内容包含：
  - 每条失败用例：用例标题、接口 method/path、环境 base_url、错误信息、关键 request/response 摘要
  - `bug_report_id` 列表（用于 Web 端定位）

发送结果写入 `email_records`。

## MVP 验收标准（按你的业务口径）

- Web 端选择用例 → 能智能匹配到一份“最合适 md 文件”并展示接口预览
- 用户确认后执行 → `test_records` 有执行记录，`test_reports` 有新报告
- 若接口运行报错 → `bug_reports` 有记录，并给 `auto_receive_bug=1` 联系人发送邮件（有 `email_records` 可追溯）

