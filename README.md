# Finance Agent Runtime

一个面向财务/数据分析场景的本地 Agent Runtime。

它不是普通聊天机器人，也不是让大模型自由写 SQL 的 text-to-SQL 工具。它的核心设计是：

```text
LLM 只提方案，系统才执行。
```

用户和 chat model 对话；当问题需要查数、计算、分析时，LLM 输出一个 `MethodProposal`，系统校验、生成方法、请求用户授权，最后在沙箱里执行。LLM 永远不碰真实数据。

---

## 安全红线

1. **LLM 不看真实数据。** 只能看到元数据（表名、字段名、描述）和结果的结构信息（列名、行数），不能看到数据值。
2. **LLM 只提方案。** 输出 `MethodProposal`，不等于授权，不等于执行。
3. **系统校验一切。** `validate_response_plan` 检查 entity 是否存在、字段是否可见、安全规则是否通过。
4. **数据读取必须授权。** 用户确认方法后，再确认数据授权范围，沙箱才执行。
5. **计算在沙箱里。** SQL/Python 在受控 sandbox 执行，LLM 不直接执行。
6. **数字必须算出来。** 结果来自沙箱，不是 LLM 猜的。
7. **展示和生成分离。** LLM 只看安全摘要做解读，真实数字由确定性 Renderer 插入。

---

## 技术选型

```text
API / UI           = FastAPI（单页 HTML + 调试面板）
状态编排            = LangGraph（15 个节点，2 条主路径）
LLM 调用           = LM Studio OpenAI-compatible API
结构化输出校验      = Pydantic
能力/技能注册表     = config/operations.yaml, config/skills.yaml
元数据目录          = config/catalog.yaml
安全策略            = config/policy.yaml
沙箱执行            = SQLite in-memory（SQL）+ restricted Python
私有结果存储        = data/private_results.jsonl
公开记忆            = data/public_memory.jsonl
审计日志            = data/audit.jsonl
```
---

## Context Engineering

参考 Codex / Claude Code 的分层注入模式，context 分三层：

```text
Layer 1: INSTRUCTIONS（稳定，可缓存）
  角色定义、输出格式、怎么理解 context、安全规则。
  基本不变，适合 prompt caching。

Layer 2: CONTEXT（动态，纯 JSON 数据）
  capabilities 索引：name + description
  skills 索引：name + title + description
  operations 索引：name + title + description（通用操作 Handler）
  business_terms 索引：name + description + aliases（业务词典）
  prior_results 索引：result_ref + fields + row_count
  不含任何指导语，不含真实数据值。

Layer 3: USER_QUERY（每轮不同）
  纯用户消息。
```

### 渐进披露

LLM 只看到精简索引，校验后才展开详情：

```text
Context 里看到的：
  capability → name + description（够匹配意图）
  skill → name + title + description（够匹配意图）
  operation → name + title + description（通用操作索引）
  business_term → name + description + aliases（业务术语映射）
  prior_result → result_ref + fields + row_count（够引用）

校验通过后展开的：
  capability detail → execution_modes, risk_level, authorization_policy
  skill detail → when_to_use, required_metadata_terms, clarification_policy
  prior result data → 完整数据（沙箱内，LLM 看不到）
```

安全收益：LLM 看到的信息量最小化。索引里没有 risk_level、preferred_mode、suggested_capabilities 等系统内部信息。

---

## ResponsePlan

LLM 输出统一的 `ResponsePlan`，没有 action type：

```text
ResponsePlan
  message: str                    # 给用户看的中文消息
  method_proposal: MethodProposal  # null = 闲聊
  confidence: float

MethodProposal
  entity_id: str          # 匹配的 capability/skill id
  entity_type: str        # "capability" | "skill"
  result_refs: list[str]  # 引用的先前结果
  goal: str               # 分析目标
  preferred_runtime: str  # sql / python / auto
  reason: str
  sql: str | null         # LLM 自写的 SQL（通用操作不覆盖时）
```

路由规则：

```text
无 method_proposal → direct_response（直接回复）
有 method_proposal
  ├─ 无 result_refs → 常规方法流（数据库表 → 沙箱）
  └─ 有 result_refs → 依赖执行流（prior result → 沙箱）
```

示例——闲聊：
```json
{"message": "你好，我是本地财务分析 Agent。", "method_proposal": null, "confidence": 0.95}
```

示例——数据分析：
```json
{
  "message": "我可以先准备按交易状态统计笔数的方法。",
  "method_proposal": {
    "entity_id": "status_distribution",
    "entity_type": "capability",
    "result_refs": [],
    "goal": "统计每个交易状态有多少笔",
    "preferred_runtime": "sql",
    "reason": "匹配注册能力"
  },
  "confidence": 0.95
}
```

示例——依赖执行：
```json
{
  "message": "基于之前的结果，按渠道拆分。",
  "method_proposal": {
    "entity_id": null,
    "result_refs": ["result_abc123"],
    "goal": "按渠道拆分",
    "preferred_runtime": "sql",
    "reason": "引用先前结果"
  },
  "confidence": 0.9
}
```

---

## Method Draft 与内部校验

LLM 提出 proposal 后，系统生成方法草稿（SQL/Python），必须经过：

```text
Method Draft
  → Static Harness Review（SQL 只读检查、字段可见性、代码安全）
  → Synthetic Sandbox Check（合成数据内部验证）
  → Self Repair（最多 3 次）/ Refuse
  → 用户确认 Method
  → 用户确认数据授权
  → 沙箱执行
```

依赖方法（data_source="result_ref"）跳过 catalog 字段校验，因为 prior result 不在元数据目录里。SQL 安全检查仍然执行。

---

## 记忆设计

### Public LLM Memory

LLM 可见，不含真实数据值：

```text
result_ref, method_name, fields, row_count, result_shape
values_visible_to_llm = false
```

### Private Result Store

LLM 不可见，保存真实结果：

```text
result_ref, 真实执行结果, result_hash, method_hash
visible_to_llm = false
```

### 依赖执行

用户追问"那 failed 的继续分析"时：

```text
LLM 看到 context.prior_results 里有 result_ref
LLM 提出 MethodProposal，result_refs 包含该 ref
系统从 PrivateResultStore 取出完整数据
生成依赖方法（SQL 查 prior_result 表）
用户确认 Prior Result Authorization
沙箱加载 prior result 为 extra_tables 执行
结果存回 Private/Public Memory
```

支持多源：`result_refs: ["result_abc", "result_xyz"]` → `prior_result_0`, `prior_result_1` 表可 JOIN。

---

## Renderer 边界

```text
LLM Narrator
  只接收 SafeResultSummary（结构信息，无真实值）
  生成自然语言解读

Deterministic Renderer
  接收 ExecutionResultCard.result
  插入真实计算结果
```

漂亮的自然语言由 LLM 生成，事实数字由 Renderer 插入。

---

## 当前实现状态

| 模块 | 状态 |
| --- | --- |
| FastAPI + 单页 UI | ✅ |
| LangGraph 状态机（15 节点，2 条路径） | ✅ |
| ResponsePlan（统一 MethodProposal） | ✅ |
| 分层 Context 注入（INSTRUCTIONS + CONTEXT + QUERY） | ✅ |
| 渐进披露（索引 → 校验后展开详情） | ✅ |
| 增量上下文（sent_memory_count） | ✅ |
| Capability 注册表 + 渐进披露 | ✅ |
| Skill 注册表 + 渐进披露 | ✅ |
| Analysis Plan Review | ✅ |
| Method Draft 生成与校验 | ✅ |
| 依赖方法生成（单源/多源） | ✅ |
| Harness Review + Synthetic Check | ✅ |
| Sandbox（SQL/Code，支持 extra_tables） | ✅ |
| Data Authorization + Prior Result Authorization | ✅ |
| Private/Public Memory 分层 | ✅ |
| Safe Narrator + Deterministic Renderer | ✅ |
| 审计日志 | ✅ |
| 装饰器自动注册（Handler/Runner/Executor/BusinessTerm） | ✅ |
| LLM 自写 SQL（超出通用操作时） | ✅ |
| 业务词典（装饰器 + YAML 双轨） | ✅ |
| 72 个测试 | ✅ |
| Real Readonly Data Proxy | ❌ |
| UI 产品化 | 部分 |
| E2E 自动化测试 | ❌ |

---

## 代码结构

```text
src/finance_agent/
  api/app.py                   FastAPI + 单页 UI
  graph/
    runtime.py                 LangGraph 状态机
    state.py                   图状态定义
  chat/
    response_plan.py           ResponsePlan, MethodProposal, validate, 分层 Prompt
    tool_decision.py           旧兼容层
  llm/provider.py              LLM Provider（LM Studio）
  operations/
    registry.py                Capability 注册表（@register_capability）
    handler_registry.py        通用操作 Handler 注册表（@register_operation）
    handlers/                  内置操作（top_n, distribution, trend, variance, group_by）
  skills/
    registry.py                Skill 注册表（@register_skill）
  metadata/
    catalog.py                 元数据目录
    policy.py                  安全策略
    pruner.py                  目录裁剪
    business_registry.py       业务词典注册表（@register_business_term）
    business_terms/            内置业务术语（退款、冲正等）
  planner/
    analysis_planner.py        LLM 分析计划生成
    rule_planner.py            规则兜底
  methods/generator.py         Method Draft 生成（含依赖方法）
  harness/
    method_validator.py        方法校验
    analysis_schema.py         数据模型（MethodDraft, AuthorizationCard 等）
  sandbox/
    runner_registry.py         Runner 注册表（@register_runner）
    runners/                   内置 runner（sql, code）
    local_provider.py          本地沙箱 Provider
  executor/
    executor_registry.py       Executor 注册表（@register_executor）
    executors/                 内置 executor（mock, direct_db）
  memory/
    private_result_store.py    私有结果存储
    public_memory.py           公开记忆
    safe_summary.py            安全摘要构建
  renderer/
    method_review_renderer.py  方法审查与结果渲染
    result_narrator.py         LLM 叙述（只看安全摘要）
  audit/audit_logger.py        审计日志
```

---

## 装饰器自动注册系统

所有注册中心都使用装饰器 + 自动发现模式，类似 HuggingFace Transformers。不需要手动改注册表代码。

### 通用操作 Handler（`@register_operation`）

最核心的注册中心。每个 Handler 同时携带 SQL 生成、依赖方法生成、结果解读三套逻辑。

**注册新操作：**

```python
# src/finance_agent/operations/handlers/my_handler.py
from finance_agent.operations.handler_registry import (
    register_operation, register_findings,
)
from finance_agent.harness.analysis_schema import AnalysisStep, MethodDraft

@register_operation(
    name="my_custom_op",              # 操作唯一 ID
    title="自定义操作",                # LLM 看到的标题
    description="按 X 统计 Y 的 Z。",  # LLM 看到的描述
    method_name="my_custom_method",   # 生成的 MethodDraft.name
    method_title="自定义分析",
    step_title_template="自定义 {dimension}",  # 步骤标题模板
    step_description="统计自定义指标。",
    findings_type="my_custom_op",     # 映射到 finding 函数
    dependent_fn=_generate_dependent, # 可选：依赖方法生成
    findings_fn=_my_findings,         # 可选：结果解读
)
def _generate(step: AnalysisStep) -> MethodDraft:
    # 你的 SQL 生成逻辑
    ...

@register_findings("my_custom_op")
def _my_findings(rows: list[dict]) -> list[str]:
    # 你的结果解读逻辑
    ...
```

文件放在 `operations/handlers/` 下即可，系统自动发现。

### Runner（`@register_runner`）

沙箱执行器，接收 `SandboxExecutionRequest`，返回执行结果。

```python
# src/finance_agent/sandbox/runners/my_runner.py
from finance_agent.sandbox.runner_registry import register_runner, SandboxExecutionRequest

@register_runner("my_runner")
def run_my_runner(request: SandboxExecutionRequest) -> SandboxExecutionResult:
    ...
```

文件放在 `sandbox/runners/` 下即可。

### Executor（`@register_executor`）

执行器工厂函数，返回执行器实例。

```python
# src/finance_agent/executor/executors/my_executor.py
from finance_agent.executor.executor_registry import register_executor

@register_executor("my_mode")
def create_my_executor(settings, policy):
    return MyExecutor(...)
```

文件放在 `executor/executors/` 下即可。

### 业务词典（`@register_business_term`）

业务术语注册，帮助 LLM 理解业务含义。

```python
# src/finance_agent/metadata/business_terms/my_terms.py
from finance_agent.metadata.business_registry import register_business_term

@register_business_term(
    name="大额交易",
    description="单笔金额超过阈值的交易。",
    aliases=["大额", "高额", "high_value"],
    candidate_fields=["total_amount"],
    filters=[{"field": "total_amount", "op": ">=", "value": 10000}],
)
def _():
    pass
```

文件放在 `metadata/business_terms/` 下即可。

### Capability 和 Skill

与 YAML 配置双轨运行，装饰器注册的条目不覆盖 YAML 已有的。

```python
# 代码中注册
@register_capability(name="my_cap", description="...")
def _: pass

@register_skill(name="my_skill", title="...", description="...")
def _: pass
```

### 自动发现机制

所有注册中心都使用 `pkgutil.iter_modules` 扫描对应包目录：

```text
operations/handlers/     → @register_operation + @register_findings
sandbox/runners/         → @register_runner
executor/executors/      → @register_executor
metadata/business_terms/ → @register_business_term
```

只要文件在对应目录下，装饰器在模块导入时执行，`get_default_*()` 时收集。**不需要手动 import 或注册。**

---

## LLM 自写 SQL

当用户的分析需求超出所有通用操作范围时，LLM 可以直接写 SQL。

### 流程

```text
用户消息 → LLM 看到通用操作列表
  → 匹配到 → entity_id 填操作名，sql=null
  → 匹配不到 → entity_id 留空，sql 填 SQL
  → 系统校验 SQL（只读、字段可见、无危险关键词）
  → 生成 MethodDraft → 走正常审批流程
```

### 安全校验

LLM 写的 SQL 经过两层校验：
1. **Proposal 层**：禁止 INSERT/UPDATE/DELETE/DROP 等关键词，必须以 SELECT 开头
2. **Method 层**：`assert_readonly_sql` 严格检查只读性

### LLM 输出示例

```json
{
  "message": "这个需求需要自定义查询，我来写一个 SQL。",
  "method_proposal": {
    "entity_id": null,
    "entity_type": null,
    "goal": "查询最近 7 天每天的交易成功率",
    "preferred_runtime": "sql",
    "reason": "通用操作不覆盖成功率计算",
    "sql": "SELECT DATE(transaction_at) as date, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as success_rate FROM card_transaction WHERE transaction_at >= DATE('now', '-7 days') GROUP BY DATE(transaction_at)"
  },
  "confidence": 0.85
}
```

---

## 本地运行

```bash
# 准备
cd /Users/joybot/Desktop/finance-agent-runtime
cp .env.example .env
./scripts/setup.sh

# 启动 LM Studio（OpenAI-compatible server）
# 默认：http://127.0.0.1:1234/v1, qwen2.5-coder-7b

# 启动服务
./scripts/start.sh
# 打开 http://127.0.0.1:8810/

# 运行测试
pytest
```

---

## 测试问题

闲聊：
```text
hi / 你是谁？ / 你能做什么？
```

能力匹配：
```text
统计每个交易状态有多少笔 / 查一下消费金额最高的客户 Top 5
```

技能匹配：
```text
帮我分析一下上半年的业务好不好 / 帮我看看交易质量有没有异常
```

安全拦截：
```text
删除交易表 / 把数据库连接串发给我
```

依赖执行：
```text
基于刚才的结果，按渠道拆分 / 那 failed 的交易继续看看
```

---

## 下一阶段

1. **Data Proxy** — 接入真实只读数据库（只读账号、字段权限、行级权限、最小化 snapshot）
2. **Sandbox 隔离** — Firecracker / gVisor（Mac 本机暂用本地 runner）
3. **Skill 增强** — examples、evaluation cases、routing hints
4. **UI 产品化** — 清晰的执行链路可视化
5. **E2E 测试** — 自动化 UI 测试
