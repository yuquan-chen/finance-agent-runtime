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
| 配置 | YAML（catalog / operations / skills / policy） |
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
LLM 分析意图 → ResponsePlan
  ├─ 闲聊 → 直接回复
  └─ 需要查数 → MethodProposal
       ↓
  系统校验 + 生成 MethodDraft（SQL / Python）
       ↓
  展示给用户确认（SQL + 预期结果）
       ↓
  用户确认 → 沙箱执行
       ↓
  结果注入 LLM 上下文 → 生成自然语言回复
       ↓
  保存到文件型 Memory（用户意图 + 结果摘要）
```

---

## 记忆系统

### 对话历史持久化

保存所有用户消息和 AI 回复，支持跨 session 查询：
- 保存到 `data/conversations/` 目录，按日期分文件（JSONL 格式）
- 下次对话时自动读取最近 10 轮对话历史
- **LLM 总结**：用 LLM 提取关键信息，注入摘要而不是全量（参考 Claude Code）
- 注入到 LLM 上下文，帮助理解连续对话

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
    catalog.py                 元数据目录
    table_registry.py          表结构注册（从 TypeORM 提取）
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
| `config/catalog.yaml` | 数据库元数据（表、字段、描述） |
| `config/operations.yaml` | 通用操作定义 |
| `config/skills.yaml` | 技能定义 |
| `config/policy.yaml` | 安全策略 |
| `.env` | 环境变量（LLM、数据库连接） |

---

## 下一阶段

1. **真实数据库** — 接入 PostgreSQL 只读账号
2. **更多表** — 扩展到 170+ 表的完整 schema
3. **复杂查询** — 子查询、CTE、窗口函数
4. **图表生成** — 自动可视化查询结果
5. **权限控制** — 基于用户角色的字段级权限
