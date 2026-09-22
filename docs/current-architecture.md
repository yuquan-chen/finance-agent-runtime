# 当前架构

本文以当前仓库代码为准，不描述尚未实现的业务 API 或支付能力。

## 定位

Finance Agent Runtime 是一个面向敏感数据的受控 Text-to-SQL Runtime：模型负责理解多轮对话并提出查询方案，运行时负责验证、授权、执行、结果隔离和审计。

当前实现主要覆盖：

- 敏感业务数据的自然语言查询和分析；
- 多轮查询引用、条件修改、排序、分组和时间范围调整；
- 查询方法的安全审查和合成数据检查；
- 会话、run、记忆和结果隔离；
- 可通过 Registry 注册的 Skill 和领域模块。

仓库中的财务和 KYC 配置属于示例领域，不能视为 Runtime 的通用业务边界。

## 组件关系

```text
浏览器 / 其他客户端
        |
        v
FastAPI API
  |-- Session / Side Skill / Attachment API
  |-- Run / SSE API
  |-- Auth boundary
        |
        v
FinanceAgentRuntime
  |-- ResponsePlan + action validation
  |-- LangGraph workflow
  |-- Business knowledge + schema selector
  |-- Method generator + harness
  |-- Session / memory / audit / run stores
        |
        +--> MockExecutor
        +--> ReadonlyDbExecutor
        +--> Local / Firecracker sandbox provider
```

外部业务 API 当前不在这条链路中。未来接入时应增加平行的领域 Gateway 和 Service，不应让 SQL executor 发送业务写请求。

## 查询流程

```text
用户输入
  -> ResponsePlan
  -> Action Validation
  -> direct response / clarification / refusal
  -> business term and table candidate search
  -> LLM selects bounded tables
  -> selected metadata disclosure
  -> AnalysisPlan / MethodDraft（内部查询结构）
  -> Query Guard（静态校验 + Synthetic Check）
  -> 通过后自动 mock 或只读数据库执行，不生成用户确认卡
  -> private result and deterministic rendering
  -> safe memory + audit
```

LLM 只接收经过裁剪的业务词典、表摘要、选中字段和安全的多轮对话历史。真实结果行保存在 `PrivateResultStore`，普通规划上下文只能看到安全摘要和引用；后续问题通过结果引用和查询关系继续规划，不直接暴露上一轮真实结果。

## LangGraph 当前节点

`FinanceAgentRuntime._build_graph()` 当前主链路节点包括：

```text
plan_response
validate_action
render_direct_response
search_schema
select_schema
load_metadata
plan_analysis
generate_method
query_guard
execute_readonly
repair_method
prepare_schema_repair
refuse_method
load_prior_result
generate_dependent_method
audit
```

不同节点之间的路径由结构化状态字段决定，不由模型返回的自然语言直接决定。查询校验失败时最多进入受限修复循环，超过上限则受控拒绝。普通只读查询不会进入用户确认卡流程；遗留确认接口仅用于兼容已经存在的历史待确认任务。

## 持久化边界

| 存储 | 内容 | 约束 |
| --- | --- | --- |
| `SessionManager` | 会话历史、待确认状态、Skill 状态和 UI 时间线 | 按 `user_id + workspace_id` 隔离 |
| `RunStore` | run 安全快照、动作回执、租约和生命周期事件 | 不保存真实结果行 |
| `PrivateResultStore` | 真实结果、参数、授权证据和结果引用 | 只供当前授权用户/流程使用 |
| `MemoryStore` | `query_history` 和 `semantic` 安全记忆 | 只有安全投影可进入普通 LLM 上下文 |
| `AuditLogger` | 请求、策略、方法和执行审计事件 | 不记录凭据和敏感明文 |
| `SideThreadStore` | Skill 子会话事件和工作流 artifact | 与父 session 共享受控状态，不复制完整历史 |

LangGraph 的 `MemorySaver` 只负责单次 run 的内存 checkpoint。它不是跨进程、跨重启的业务存储。

## 身份边界

开发模式使用 `X-User-Id` 和 `X-Workspace-Id`。`AUTH_MODE=required` 时使用签名的 HMAC HS256 Bearer JWT，至少要求 `sub`、`workspace_id` 和 `exp`。

这解决的是 Runtime 资源归属，不等同于业务 Admin 的 RBAC。接入业务 API 后，必须把认证主体映射到业务组织、角色、账户范围和可执行动作，并由服务端强制传递给领域 Gateway。

## 执行模式

- `mock`：默认模式，使用仓库内生成的合成数据，适合开发和测试。
- `direct_db`：通过 SQLAlchemy 连接配置的数据库，只允许只读查询，并受行数、超时和字段策略约束。
- Local sandbox：本机受控执行 provider。
- Firecracker：生产目标的 provider 适配边界，当前 macOS 不具备原生 Linux/KVM 运行条件。

## 接入新领域的原则

新的业务领域至少需要独立定义：

```text
领域模型
Gateway protocol
请求/响应 adapter
权限和字段策略
状态机（如有）
持久化模型
审计事件
contract / permission / recovery tests
```

尤其是 `审`、`开户`、`配置`、`提交` 等有副作用动作，不能复用查询的 `Query Guard` 语义。它们需要单独的命令模型、确认版本、幂等策略和执行结果状态；普通只读查询不需要人工确认。
