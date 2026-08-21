# Finance Agent Runtime

一个面向财务/数据分析场景的本地 Agent Runtime。

核心设计：**LLM 只提方案，系统才执行。**

用户和 LLM 对话；当问题需要查数、计算、分析时，LLM 输出一个 `MethodProposal`，系统校验、生成方法、请求用户授权，最后在沙箱里执行。LLM 永远不碰真实数据。

---

## 技术栈

| 组件 | 技术 |
|------|------|
| API / UI | FastAPI + 单页 HTML + SSE 流式输出 |
| 状态编排 | LangGraph（15 个节点，2 条主路径） |
| LLM | DeepSeek API / LM Studio（OpenAI-compatible） |
| 数据库 | PostgreSQL（只读账号） |
| 结构化输出 | Pydantic |
| 配置 | Python `TableRegistry`（schema）+ YAML（业务词典 / operations / skills / policy） |
| 记忆 | 文件型 Markdown（用户意图 + 结果摘要） |
| 审计 | JSONL 日志 |

---

## 安全红线

1. **LLM 不看真实数据** — 只能看到元数据（表名、字段名、描述）和结果的结构信息（列名、行数）
2. **LLM 只提方案** — 输出 `MethodProposal`，不等于授权，不等于执行
3. **系统校验一切** — SQL 只读检查、字段可见性、安全规则
4. **数据读取必须授权** — 用户确认后，沙箱才执行
5. **数字必须算出来** — 结果来自沙箱，不是 LLM 猜的
6. **禁止编造结果** — 如果查询为空，必须如实告知

---

## Context Engineering

参考 Codex / Claude Code 的分层注入模式，context 分三层：

```
Layer 1: INSTRUCTIONS（稳定，可缓存）
  角色定义、输出格式、安全规则

Layer 2: CONTEXT（动态，纯数据）
  - 能力/技能索引（name + description）
  - 通用操作索引（name + title + description）
  - 业务词典（name + aliases）
  - 之前的查询记录（用户意图 + 结果摘要）

Layer 3: USER_QUERY（每轮不同）
  纯用户消息
```

---

## 核心流程

```
用户消息
  ↓
LLM 理解业务意图 → ResponsePlan
  ├─ 闲聊 → 直接回复
  └─ 需要查数 → MethodProposal（能力 + 脱敏 Schema 检索词）
       ↓
  后端在完整注册表中搜索少量候选表（不把 173 张表发给 LLM）
       ↓
  LLM 仅从候选表摘要中选择需要展开的表
       ↓
  系统展开所选表的真实字段、关系，并剔除敏感字段
       ↓
  LLM 生成 SQL / MethodDraft
       ↓
  系统校验：表、字段、关系、参数、只读策略、语义和沙箱
       ├─ 不通过 → 带结构化错误重新检索 Schema 并规划（包含首轮最多 3 次）
       └─ 通过
       ↓
  展示给用户确认（SQL + 实际读取范围）
       ↓
  用户确认 → 沙箱执行
       ↓
  私有结果解读 → 生成自然语言回复
       ↓
  保存脱敏意图与结果摘要；真实结果不进入普通 LLM 对话上下文
```

---

## 记忆系统

### 对话历史持久化

使用 LangGraph 内置的 checkpoint 功能，自动保存对话状态：
- **MemorySaver**：内存存储（开发环境）
- **Thread**：按 thread_id 组织对话，支持多用户并发
- **自动持久化**：每个节点执行后自动保存状态
- **LLM 总结**：用 LLM 提取关键信息，注入摘要而不是全量（参考 Claude Code）

技术实现：
```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "user-123"}}
result = graph.invoke(input_data, config=config)
```

### 查询记录存储

每次查询后保存：
- 用户意图（不是 SQL）
- 涉及的表和字段
- 结果摘要（行数、列名）

保存到 `data/public_memory/` 目录，每条记忆一个 `.md` 文件。

### 上下文注入

下次对话时，系统自动注入：
- 最近 10 轮对话历史
- 最近 3 条查询记录
- 帮助 LLM 理解"排序一下"、"筛选一下"等操作性指令

---

## 技术细节

### SQL 参数绑定

```python
# LLM 生成带参数的 SQL
SELECT * FROM account WHERE legal_name = :customer_name

# 参数值单独传递
params = {"customer_name": "Company 5"}

# 系统自动转换为 psycopg2 格式
SELECT * FROM account WHERE legal_name ILIKE %(customer_name)s

# 模糊匹配：Company5 → %Company%5%（可匹配 "Company 5"）
```

### 不区分大小写

所有字符串比较自动使用 `ILIKE`，支持中英文混合查询。

### 自动修复

SQL 执行失败时，系统会自动分析错误并重试（最多 3 次）。

---

## 本地运行

```bash
# 1. 准备环境
cd /Users/joybot/Desktop/finance-agent-runtime
cp .env.example .env
./scripts/setup.sh

# 2. 配置 LLM（编辑 .env）
# DeepSeek API（推荐）
LMSTUDIO_BASE_URL=https://api.deepseek.com
LMSTUDIO_MODEL=deepseek-chat
LMSTUDIO_API_KEY=sk-your-api-key

# 或本地 LM Studio
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=qwen2.5-coder-7b-instruct-mlx

# 3. 启动 PostgreSQL（如果使用真实数据库）
# PG_HOST=localhost
# PG_PORT=5432
# PG_DATABASE=finance_sandbox
# PG_USER=readonly_user
# PG_PASSWORD=xxx

# 4. 启动服务
./scripts/start.sh
# 打开 http://127.0.0.1:8810/
```

---

## 测试查询

| 类型 | 示例 |
|------|------|
| 简单查询 | 查一下 Company 5 的 KYC 状态 |
| 多表关联 | 查询 Person 3 的卡交易记录 |
| 统计分析 | 统计每个交易状态有多少笔 |
| 连续查询 | （基于上一个结果）按渠道拆分一下 |

---

## 代码结构

```
src/finance_agent/
  api/app.py                   FastAPI + 单页 UI
  graph/
    runtime.py                 LangGraph 状态机（核心）
    state.py                   图状态定义
  chat/
    response_plan.py           ResponsePlan + 分层 Prompt
  llm/provider.py              LLM Provider
  operations/
    registry.py                能力注册表
    handler_registry.py        操作 Handler 注册表
    handlers/                  内置操作（top_n, distribution, trend...）
  skills/registry.py           技能注册表
  metadata/
    catalog.py                 Catalog 数据模型与兼容性 YAML 读取
    table_registry.py          运行时表结构注册表
    schema_selector.py         受控候选表选择器
    tables/                    上游项目 schema 提取的 173 张表元数据
    business_registry.py       业务词典
  methods/generator.py         Method Draft 生成
  sandbox/
    runners/sql.py             SQL 执行器（PostgreSQL）
    mock_data.py               Mock 数据
  memory/
    memory_store.py            文件型 Memory 存储
    selector.py                相关记忆选择
  renderer/
    reply_generator.py         LLM 回复生成（注入结果数据）
    method_review_renderer.py  方法审查渲染
  audit/audit_logger.py        审计日志
```

---

## 配置文件

| 文件 | 用途 |
|------|------|
| `config/catalog.yaml` | 业务词典与兼容性/测试 catalog；不是运行时完整 schema 的事实源 |
| `config/operations.yaml` | 通用操作定义 |
| `config/skills.yaml` | 技能定义 |
| `config/policy.yaml` | 安全策略 |
| `.env` | 环境变量（LLM、数据库连接） |

### Schema 元数据来源

运行时的完整 schema 来自 `schema_catalog/tables/` 中的 Python 表元数据：这些文件由上游业务项目的数据库 schema / ORM 定义提取并版本化，目前覆盖约 173 张表。表级业务 description 单独存放在 `schema_catalog/table_descriptions.yaml`，由人工或本地 LLM 维护，避免 ORM 同步覆盖业务语义。`TableRegistry` 自动合并两层元数据，构建只供后端检索的全局 Catalog。

因此，173 张表是系统拥有的元数据全集，而不是每次都应发送给 LLM 的上下文。查询路径分为三层：首轮只识别业务能力与检索词；后端返回少量候选表名和说明；模型从候选中选择后，系统才展开这些表的真实字段、关系和经过权限过滤的 `VisibleCatalog` 给 SQL 规划器。模型不能直接看到全量目录，也不能引用未展开的表或字段。`config/catalog.yaml` 保留业务词典及早期测试/兼容内容，不与 Python 表定义共同充当 schema 事实源。

上游 ORM 更新后，先重新生成快照，再校验二者字段完全一致：

```bash
.venv/bin/python scripts/extract_schema.py \
  --from-entity /path/to/wavepool-core/src/repository \
  --output schema_catalog/tables
.venv/bin/python scripts/verify_schema_sync.py \
  --from-entity /path/to/wavepool-core/src/repository
```

提取器会递归保留 TypeORM 继承链，以及 `CreateDateColumn`、`UpdateDateColumn`、`DeleteDateColumn`、`VersionColumn` 等专用字段。校验失败时不得发布新的 schema 快照。

缺失的表级业务说明可用本地 LLM 补齐；该脚本只更新覆盖层，不会修改 schema 文件：

```bash
.venv/bin/python scripts/generate_table_descriptions.py
```

---

## 下一阶段

已完成：受控 Schema 检索闭环。模型不再在首轮接收全量表目录，而是经过“候选表搜索 → 选择表 → 展开字段 → SQL 校验”的受控路径生成 SQL。

1. **真实数据库与沙箱可用性** — 配置 PostgreSQL 只读账号，并在部署环境保证预检沙箱可连接；连接失败属于环境问题，不应触发 LLM 重试。
2. **Schema 语义增强** — 持续同步并校验 173+ 表的快照，并补全关系、时间字段含义、业务别名和统计口径。
3. **查询正确性评估** — 建立覆盖客户、付款、交易、KYC、时间范围和连续追问的真实 Schema 回归集，持续检查 SQL 是否选对表、字段和关联关系。
4. **复杂查询** — 在评估覆盖后支持子查询、CTE、窗口函数和更复杂的多步骤分析。
5. **权限控制** — 基于用户角色、组织和字段级权限生成候选目录与 `VisibleCatalog`。
6. **图表生成** — 自动可视化已授权查询结果。
