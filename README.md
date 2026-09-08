# Finance Agent Runtime

Finance Agent Runtime 是一个以自然语言驱动的财务查询与业务流程编排运行时。

当前仓库的可验证能力集中在两条线上：

- 受控的财务数据查询：模型提出查询计划和方法，系统校验后再执行只读 SQL。
- KYC 辅助工作流：收集字段、管理材料、执行本地 OCR、保存和检查会话级草稿。

业务 API、支付网关和 Admin 页面能力目前还没有接入。后续接入必须通过独立的领域 API 适配层，不应把写操作混入 SQL 查询执行器。

## 当前边界

项目遵循以下责任划分：

```text
LLM
  理解意图，提出结构化计划或方法

Runtime
  校验计划、权限、字段、SQL 和流程状态

Executor / Workflow Handler
  在受控边界内执行只读查询或本地工作流

Renderer / Audit
  展示计算结果，保存安全摘要和审计事件
```

查询链路中的真实数据不会进入普通 LLM 上下文。查询结果、授权证据和参数保存在私有结果区；模型可见记忆只保存经过裁剪的查询历史和安全语义信息。

当前不支持：

- 直接调用 WavePaid、DogPay 或其他业务 API；
- 付款、开户、审核、配置、导入等外部写操作；
- 生产级 RBAC、组织权限和业务数据租户隔离；
- 将 Firecracker 作为 macOS 本地执行环境；
- 把自然语言当作真实业务状态或支付成功结论。

## 技术栈

| 层 | 当前实现 |
| --- | --- |
| HTTP / UI | FastAPI + 单页 HTML + SSE 阶段事件 |
| 状态编排 | LangGraph，每次请求使用独立 run checkpoint |
| 模型 | `LlmProvider`，兼容 LM Studio / OpenAI-compatible API |
| 查询计划 | Pydantic schema、业务词典、Operation Registry、Schema 选择器 |
| 查询执行 | `mock` 默认模式；`direct_db` 只读 PostgreSQL/SQLAlchemy 模式 |
| 方法校验 | SQL 只读校验、参数校验、字段校验、合成数据检查、修复循环 |
| 会话 | `SessionManager` 文件存储；Side Skill 使用 SQLite |
| 运行控制面 | `RunStore` SQLite WAL，保存安全快照、动作幂等回执和生命周期事件 |
| 记忆 | `MemoryStore` JSONL；私有结果单独保存 |
| 审计 | JSONL append-only 日志 |

## 快速开始

环境要求：Python 3.11+。默认查询模式使用本地 mock 数据，不要求 PostgreSQL。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
.venv/bin/python -m uvicorn finance_agent.api.app:app --host 127.0.0.1 --port 8810 --reload
```

打开 <http://127.0.0.1:8810/>。

也可以使用：

```bash
./scripts/setup.sh
./scripts/start.sh
./scripts/health.sh
```

`.env` 中至少需要配置一个可用的 LM Studio 或 OpenAI-compatible 模型服务。默认值为本机 LM Studio：

```dotenv
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=qwen2.5-coder-7b-instruct-mlx
LMSTUDIO_API_KEY=lm-studio
EXECUTOR_MODE=mock
```

切换到只读数据库执行时，需要同时设置 `EXECUTOR_MODE=direct_db` 和 `DATABASE_URL`。PostgreSQL 连接信息不能交给 LLM，也不能通过用户输入动态指定。

Docker 启动：

```bash
docker compose up --build
```

容器只通过 `./data:/app/data` 持久化运行数据。若模型或数据库运行在宿主机上，Docker Desktop 中应使用 `host.docker.internal`，而不是容器内的 `127.0.0.1`。

## 当前运行流程

```text
用户问题
  -> ResponsePlan
  -> Action Validation
  -> 直接回复 / 澄清 / 受控拒绝
  -> Schema 候选检索与选择
  -> 字段和关系披露
  -> Analysis Plan（内部中间结构）
  -> Method Draft（内部可执行结构）
  -> Query Guard（只读 SQL、字段和合成预检）
  -> 通过后自动受控执行
  -> Private Result Store
  -> 结果渲染和安全记忆
```

每个请求使用 `run_<request_id>` 作为 LangGraph checkpoint thread。跨请求恢复依赖 `SessionManager` 和 `RunStore`，不是依赖 `MemorySaver` 的跨进程持久化。

## HTTP API

当前 HTTP API 是 Runtime API，不是业务 API：

- `GET /health`：健康检查。
- `GET /v1/skills`：读取已注册 Skill manifest。
- `POST/GET /v1/sessions`：创建和读取会话。
- `POST /v1/runs`：执行一次非流式 Agent run。
- `GET /v1/runs/stream`：通过 SSE 获取阶段事件。
- `GET /v1/runs/{request_id}`：读取安全的 run 状态。
- `/v1/runs/{request_id}/...`：分析计划、方法和数据授权动作。
- `/v1/sessions/.../attachments`：会话材料和 KYC 辅助流程。

完整的当前接口清单见 [docs/api.md](docs/api.md)。

## 配置与数据

| 路径 | 作用 | 是否进入普通 LLM 上下文 |
| --- | --- | --- |
| `config/catalog.yaml` | 业务词典和兼容性 catalog | 经过裁剪后可见 |
| `config/operations.yaml` | 分析操作注册表 | 可见操作摘要 |
| `config/skills.yaml` | Skill 和卡片定义 | 可见 Skill manifest |
| `config/policy.yaml` | 行数、超时、敏感字段和 SQL 策略 | 作为系统策略使用 |
| `schema_catalog/tables/` | 版本化表结构快照 | 只披露选中表的安全字段 |
| `data/sessions/` | 会话、时间线和 Skill 状态 | 按策略裁剪 |
| `data/private_results.jsonl` | 真实结果、参数和授权证据 | 不可见 |
| `data/public_memory.jsonl` | 查询历史和安全语义记忆 | 仅安全投影可见 |
| `data/runs.sqlite3` | run 控制面和幂等动作 | 不可见 |
| `data/audit.jsonl` | 审计事件 | 不可见 |

不要将 `data/`、`.env`、真实数据库数据或真实客户材料提交到 Git。

## 测试与质量门槛

运行全部测试：

```bash
.venv/bin/pytest -q
```

测试覆盖当前查询和 KYC 边界，包括：

- ResponsePlan、Schema 选择、SQL 构建和参数绑定；
- 方法校验、合成执行、结果渲染和连续追问；
- session、run、side Skill、KYC 材料和私有结果隔离；
- 身份边界、动作幂等和重复确认；
- 沙箱 provider 和只读执行器。

接入任何外部业务 API 前，还需要新增 contract test、权限测试、超时/重试测试、错误映射测试和状态恢复测试。

## 代码结构

```text
src/finance_agent/
  api/                 FastAPI 装配、路由和响应模型
  chat/                ResponsePlan 和工具决策
  graph/               LangGraph 状态机
  metadata/            Schema、业务词典、策略和候选选择
  methods/             Method Draft 生成
  harness/             方法和计划的确定性校验
  executor/            mock 与只读数据库执行器
  sandbox/             SQL/Code sandbox provider
  renderer/            方法卡、结果和回复渲染
  memory/              安全记忆和私有结果
  session/             会话、run 和 side thread 存储
  kyc/                 本地 KYC 草稿、OCR 和材料意图
  skills/              Skill 注册表和侧边 Agent
  audit/               审计日志
```

## 文档入口

- [docs/README.md](docs/README.md)：文档分类和现行基线。
- [docs/current-architecture.md](docs/current-architecture.md)：以当前代码为准的架构说明。
- [docs/development.md](docs/development.md)：开发、配置和故障排查。
- [docs/api.md](docs/api.md)：当前 Runtime API。
- [docs/admin-api-integration.md](docs/admin-api-integration.md)：未来业务 API 接入边界和契约模板。
- [schema_catalog/README.md](schema_catalog/README.md)：Schema 快照同步规则。

`docs/` 中未列为当前基线的文件均属于历史设计、实验记录或待实现方案，不能单独覆盖当前代码行为。
