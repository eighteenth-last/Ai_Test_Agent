老大，你现在这个想法，已经不是在优化功能了。
你是在给系统装“长期记忆”。

这一步做对了，你的一键测试会从“临时聪明”进化为“持续进化”。

我们把这件事拆开讲清楚，不搞玄学，只讲结构。

---

## 一、你要解决的本质问题是什么？

当前流程：

每次一键测试
→ 浏览器重新探索页面
→ 收集 DOM
→ 生成任务

问题：

* 浪费时间
* 重复探索
* 对静态页面极度低效
* 没有历史记忆

你要的升级是：

探索一次
→ 存入知识库
→ 下次优先使用
→ 发现结构变更 → 自动更新

这就是一个“自修复页面知识系统”。

---

## 二、架构定位：不是简单缓存，是 RAG 记忆层

核心结构应该是：

Page Knowledge Base（页面知识库）

它本质是：

向量数据库 + 元数据存储 + 版本控制

不是简单 JSON 存库。

---

## 三、推荐架构设计

新增模块：

Agent_Server/Page_Knowledge/

结构：

```
Page_Knowledge/
├── service.py        # 读写知识库
├── embedding.py      # 向量生成
├── vector_store.py   # 向量数据库封装
├── diff_engine.py    # 页面结构对比
├── schema.py         # 页面结构模型
```

---

## 四、页面知识结构设计

不要只存 DOM。

存“页面能力结构”。

例如：

```json
{
  "url": "https://xxx/login",
  "page_type": "login",
  "forms": [
    {
      "name": "login_form",
      "fields": [
        {"name": "username", "type": "text"},
        {"name": "password", "type": "password"}
      ],
      "submit_button": "登录"
    }
  ],
  "buttons": ["登录", "忘记密码"],
  "dynamic_elements": ["toast"],
  "auth_required": false,
  "roles": [],
  "last_updated": "2026-03-04",
  "hash_signature": "xxxx"
}
```

关键点：

存“抽象能力”，而不是原始 HTML。

否则版本更新时你根本比对不了。

---

## 五、RAG 如何介入？

流程改造：

### 1️⃣ 用户发起任务

→ 先查询向量数据库：

“是否已有这个 URL 的页面知识？”

向量查询内容：

* URL
* 页面标题
* 页面语义描述

如果相似度 > 阈值（比如 0.85）

→ 直接使用历史页面知识

---

### 2️⃣ 如果没有

→ 执行浏览器探索
→ 抽象页面能力
→ 存入向量数据库

---

### 3️⃣ 版本检查机制（关键）

每次执行前：

计算当前页面结构签名：

可以用：

* DOM 树节点数量
* 表单字段数量
* 按钮数量
* 页面标题
* 关键元素 hash

生成：

hash_signature

和知识库里的对比：

如果不同：

→ 执行 diff_engine
→ 更新知识库
→ 标记为新版本

---

## 六、向量数据库选型

你可以选：

* FAISS（本地部署）
* Milvus（企业级）
* Qdrant（轻量且好用） 已配置，地址：http://localhost:6333/
* pgvector（如果你已经用 MySQL 就别用这个）

推荐：

Qdrant

轻量、支持元数据过滤、支持版本字段。

---

## 七、Embedding 模型建议

不要用大模型 embedding。

可以用：

* OpenAI embedding
* 或本地 bge-large
* 或 text-embedding-3-small

你要向量化的是：

页面结构摘要文本，例如：

“登录页面，包含用户名、密码输入框和登录按钮，存在错误提示 toast”

不要向量化整个 DOM。

Embedding 模型配置
key：sk-bdizvndprpoykyssjfjfiizvgvntemsysnngfdhyasnrjgxv
url：https://api.siliconflow.cn/v1/embeddings
model：Qwen/Qwen3-Embedding-4B
---

## 八、RAG 使用场景

当生成二级任务时：

不要只用当前页面结构。

要做：

context = RAG.retrieve(page_knowledge)

然后提示词里加入：

“历史页面能力记录如下…”

这会让任务规划更加稳定。

---

## 九、自动更新机制（核心逻辑）

新增：

diff_engine.py

逻辑：

```
if new_hash != old_hash:
    compute_diff(old_page, new_page)
    update_vector_store()
    update_metadata_version()
```

可以记录：

* 结构变更类型
* 新增字段
* 删除字段
* 修改字段

未来你甚至可以做：

“自动回归测试推荐”

如果页面新增字段：

自动插入新的边界测试子任务。

这就开始进化了。

---

## 十、知识库要不要做成全局？

建议分三层：

1. 页面级知识（URL 级）
2. 功能级知识（登录模块）
3. 系统级知识（整站结构）

未来可以做跨页面推理。

---

## 十一、你现在这一步的真正意义

你正在做的是：

让系统从：

Stateless Agent
变成
Stateful Learning Agent

也就是说：

它开始“记住世界”。

这才是智能系统真正的分水岭。

---

## 十二、要注意的坑

1. 不要存原始 HTML
2. 不要用向量数据库替代结构化数据库
3. 不要每次都重新 embedding
4. 不要忽略版本号字段
5. 不要忽略 hash 签名

---

## 十三、未来可以进化的方向

你可以加入：

知识老化机制：

如果 30 天未访问
自动重新验证页面结构

再往前一步：

引入变更预测机制。

如果系统发现：

“最近 7 天页面频繁变动”

自动降低 RAG 相似度阈值。

这已经开始有点智能体味道了。

---

老大，现在你的一键测试正在从：

“会操作浏览器”

升级为：

“会记住系统结构并持续学习”。

当任务树 + 页面知识库结合起来，

你会得到一个真正的：

自演进测试引擎。

下一步如果你愿意，我可以帮你设计完整的：

任务树 + RAG + 执行调度

三层融合架构图。

那会是一套真正企业级可扩展的 AI 测试内核。
