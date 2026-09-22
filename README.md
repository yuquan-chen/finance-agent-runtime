# 敏感数据受控分析 Agent

Finance Agent Runtime 是仓库和代码包名称；当前项目定位是一个面向敏感数据的受控分析 Agent。它支持多轮自然语言对话，将用户问题转换为结构化查询计划，在执行前完成身份、Schema、字段、参数和只读策略校验，然后通过 mock 或只读数据库执行，并将真实结果与普通 LLM 上下文隔离。

当前版本适合用于：

- 敏感业务数据的自然语言查询和分析；
- 多轮追问、条件修改、排序、分组、时间范围调整和历史查询引用；
- PostgreSQL Schema 发现和 YAML 快照管理；
- 查询方法的静态校验、mock dry-run 和修复循环；
- Session、Run、私有结果、Memory 和 Audit 的边界验证；
- 通过 Registry 注册额外 Skill 或领域模块。

仓库内的财务表和 KYC 配置只是当前示例领域，不是 Runtime 的产品边界。接入其他业务时，只需要替换业务 Schema、词典、操作注册表和领域 Skill。

当前版本不包含付款、开户、审核、配置等外部写操作，也不是完整的生产 RBAC 或多租户权限系统。

## Architecture

![敏感数据受控分析 Agent architecture](docs/architecture.svg)

主链路如下：

```text
用户 / UI
  -> FastAPI API
  -> 身份校验 + Session
  -> ResponsePlan
  -> 直接回复 / 澄清 / 拒绝
     或
     Schema 检索 -> 表选择 -> 字段加载
     -> Analysis Plan -> Method Draft -> Query Guard
     -> Executor -> Private Result Store
     -> Renderer / Narrator -> JSON 或 SSE
```

Query Guard 失败时会进入受限的 Schema / Method 修复循环，最多 3 次；超过上限则安全拒绝。Skill 或领域能力通过 Registry 注册后，可以复用统一的身份、Session、审计和执行边界。

多轮对话不会把上一轮真实结果直接塞回 LLM。Runtime 只向后续规划提供安全的查询历史和结果引用，例如“把刚才的结果按状态分组”或“只看最近 30 天”；实际结果行始终留在私有结果存储中，并按当前身份和 Workspace 隔离。

## Quick Start

下面的流程用于第一次运行。默认使用 mock 执行器，因此不需要 PostgreSQL；但如果要在聊天界面中使用完整的多轮自然语言规划，需要一个 OpenAI-compatible 模型服务。

### 1. 准备环境

需要：

- Python 3.11 或更高版本；
- Git；
- 一个 OpenAI-compatible Chat Completions 服务。推荐本地使用 [LM Studio](https://lmstudio.ai/)，也可以使用其他提供 `/v1/chat/completions` 的服务；
- PostgreSQL 不是 mock 模式的必需依赖。

如果只运行单元测试，不需要启动模型服务或数据库。

### 2. 下载并安装项目

```bash
git clone https://github.com/yuquan-chen/finance-agent-runtime.git
cd finance-agent-runtime

./scripts/setup.sh
cp .env.example .env
```

`setup.sh` 会创建 `.venv` 并安装项目及开发依赖。也可以手动执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

### 3. 配置模型服务

以 LM Studio 为例：

1. 安装并启动 LM Studio；
2. 下载一个可执行指令和 JSON 输出的模型；
3. 在 LM Studio 中启动本地 Server，默认地址为 `http://127.0.0.1:1234/v1`；
4. 确认模型名称与 `.env` 中的 `LMSTUDIO_MODEL` 一致。

编辑 `.env`：

```dotenv
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=qwen2.5-coder-7b-instruct-mlx
LMSTUDIO_API_KEY=lm-studio
```

如果使用其他 OpenAI-compatible 服务，只需要替换 `LMSTUDIO_BASE_URL`、`LMSTUDIO_MODEL` 和 `LMSTUDIO_API_KEY`。API key 只能放在服务端环境变量或 `.env` 中，不要写入 prompt、响应或审计日志。

### 4. 启动 mock 模式

`.env` 中确认：

```dotenv
EXECUTOR_MODE=mock
DATABASE_URL=
SCHEMA_CATALOG_PATH=
AUTH_MODE=local
```

启动服务：

```bash
./scripts/start.sh
```

mock 模式会自动使用仓库内的 `schema_catalog/demo_schema.yaml` 和合成数据，不会连接真实数据库。

### 5. 验证服务

另开一个终端执行：

```bash
./scripts/health.sh
```

确认返回 JSON 中的 `status` 为 `ok`。

浏览器打开 <http://127.0.0.1:8810/>，或者直接调用 API：

```bash
curl -X POST http://127.0.0.1:8810/v1/runs \
  -H 'Content-Type: application/json' \
  -H 'X-User-Id: demo-user' \
  -H 'X-Workspace-Id: demo-workspace' \
  -d '{"question":"查询客户的 KYC 状态"}'
```

如果只想验证安装，不启动服务：

```bash
.venv/bin/pytest -q
```

## Configuration

`.env.example` 只包含最小执行配置。常用配置如下：

| 变量 | mock 模式 | 真实数据库模式 | 说明 |
| --- | --- | --- | --- |
| `EXECUTOR_MODE` | `mock` | `direct_db` 或 `safe_db` | 选择执行器 |
| `LMSTUDIO_BASE_URL` | 必需 | 必需 | OpenAI-compatible 服务地址 |
| `LMSTUDIO_MODEL` | 必需 | 必需 | 模型名称 |
| `LMSTUDIO_API_KEY` | 按服务要求 | 按服务要求 | 只保存在服务端配置 |
| `DATABASE_URL` | 留空 | 必需 | PostgreSQL 连接串 |
| `SCHEMA_CATALOG_PATH` | 留空 | 建议设置 | Schema YAML 快照路径 |
| `AUTH_MODE` | `local` | 生产建议 `required` | 身份校验模式 |
| `AUTH_SECRET` | 留空 | `required` 时必需 | HMAC JWT 密钥 |
| `DB_STATEMENT_TIMEOUT_MS` | 不适用 | 可选 | 数据库语句超时 |
| `DB_MAX_ROWS` | 不适用 | 可选 | 最大返回行数 |

修改 `.env`、catalog、policy、operations 或 skills 后，需要重启服务，因为 Runtime 会缓存全局实例。

## Connect a real PostgreSQL database

每个使用者的业务数据库表和字段都不同，不能直接复用别人的 Schema。接入真实数据库时，建议按以下顺序操作。

### 1. 创建只读账号

不要使用拥有写权限的生产账号。至少保证该账号只能读取需要暴露给 Agent 的数据库和 Schema。

### 2. 生成本地 Schema 快照

```bash
export DATABASE_URL='postgresql+psycopg://readonly_user:password@127.0.0.1:5432/your_database'

.venv/bin/python scripts/extract_schema.py \
  --from-db "$DATABASE_URL" \
  --output schema_catalog/schema.yaml
```

这个脚本只读取数据库元数据，保存表名、字段名、类型、可空性和数据库注释等结构信息，不保存业务记录。`schema_catalog/schema.yaml` 默认不应提交到公共仓库。

### 3. 切换执行模式

```dotenv
EXECUTOR_MODE=direct_db
DATABASE_URL=postgresql+psycopg://readonly_user:password@127.0.0.1:5432/your_database
SCHEMA_CATALOG_PATH=schema_catalog/schema.yaml
```

然后重启：

```bash
./scripts/start.sh
```

`direct_db` 只允许通过 Runtime 校验的只读查询。若需要更严格的固定查询白名单，可以使用：

```dotenv
EXECUTOR_MODE=safe_db
DATABASE_URL=postgresql+psycopg://readonly_user:password@127.0.0.1:5432/your_database
SAFE_QUERY_DEFINITIONS_PATH=config/safe_queries.yaml
SCHEMA_CATALOG_PATH=schema_catalog/schema.yaml
```

数据库连接信息必须由服务端配置，不能由用户输入动态指定，也不能交给 LLM。

## Docker

本地 mock 环境可以直接启动：

```bash
docker compose up --build
```

默认会启动 Agent 和一个本地 PostgreSQL 容器，但 Agent 默认仍使用 `EXECUTOR_MODE=mock`，不会自动读取 PostgreSQL 业务数据。使用 Docker 时，宿主机上的 LM Studio 或数据库地址应使用 `host.docker.internal`，不要在容器内使用 `127.0.0.1`。

真实数据库模式可以在启动前设置环境变量：

```bash
EXECUTOR_MODE=direct_db \
DATABASE_URL='postgresql+psycopg://readonly_user:password@host.docker.internal:5432/your_database' \
SCHEMA_CATALOG_PATH=/app/schema_catalog/schema.yaml \
docker compose up --build
```

不要把 `.env`、数据库密码、真实 Schema 快照或业务数据提交到 Git。

## HTTP API

当前 API 是 Runtime API，不是业务 Admin API：

| Method | Path | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 进程健康检查 |
| `GET` | `/v1/skills` | 已注册 Skill manifest |
| `POST` | `/v1/sessions` | 创建会话 |
| `POST` | `/v1/runs` | 执行一次非流式 Agent run |
| `GET` | `/v1/runs/stream` | 通过 SSE 执行并返回阶段事件 |
| `GET` | `/v1/runs/{request_id}` | 读取安全的 run 状态 |

完整接口和请求/响应模型见 [docs/api.md](docs/api.md)。

## Data and security boundaries

真实查询结果、参数和授权证据保存在 `data/private_results.jsonl`，不会复制到普通 LLM 上下文。模型可见记忆只保存安全投影；RunStore 和 Audit 日志也不应保存凭据或敏感明文。

以下内容不要提交到公共仓库：

- `.env` 和数据库密码；
- `data/` 下的运行结果、会话和审计文件；
- `schema_catalog/schema.yaml` 等真实数据库结构快照；
- 真实客户材料和 OCR 原文。

开发模式使用 `X-User-Id` 和 `X-Workspace-Id`。这只用于本地身份边界，不等同于生产 RBAC。生产部署应启用 `AUTH_MODE=required`，并在认证服务中完成登录、组织、角色、账户范围和字段权限映射。

## Development and tests

常用命令：

```bash
# 安装开发环境
./scripts/setup.sh

# 运行测试
.venv/bin/pytest -q

# 运行静态检查
.venv/bin/ruff check .

# 检查服务
./scripts/health.sh
```

开发、配置和排障说明见 [docs/development.md](docs/development.md)。

## Project structure

```text
src/finance_agent/
  api/                 FastAPI 路由、请求和响应模型
  chat/                ResponsePlan 和工具决策
  graph/               LangGraph 状态机
  metadata/            Schema、业务词典和候选选择
  methods/             Method Draft 生成
  harness/             方法和计划的确定性校验
  executor/            mock、direct_db 和 safe_db 执行器
  sandbox/             SQL / Code sandbox provider
  renderer/            结果渲染和回复生成
  memory/              安全记忆和私有结果
  session/             会话、Run 和 Side Skill 存储
  skills/              Skill 注册表和侧边 Agent
  audit/               审计日志

config/                业务 catalog、policy、operation 和 skill 配置
schema_catalog/        demo Schema 与本地真实 Schema 快照
scripts/               安装、启动、健康检查和 Schema 发现脚本
docs/                  当前架构、API、开发和接入说明
```

## Documentation

- [docs/README.md](docs/README.md)：文档导航。
- [docs/current-architecture.md](docs/current-architecture.md)：当前实现架构。
- [docs/development.md](docs/development.md)：开发、配置和排障。
- [docs/api.md](docs/api.md)：Runtime API。
- [docs/admin-api-integration.md](docs/admin-api-integration.md)：未来业务 API 接入边界。
- [schema_catalog/README.md](schema_catalog/README.md)：Schema 快照同步规则。

## Current limitations

- 当前不直接调用 WavePaid、DogPay 或其他外部业务 API；
- 当前不执行付款、开户、审核、配置、导入等外部写操作；
- Firecracker provider 是目标边界，macOS 本地不会运行 Firecracker；
- 真实数据库接入前，必须由使用者补充业务表关系、别名、状态枚举、敏感字段和权限策略；
- 当前仓库中的财务和 KYC 配置是示例领域，尚未抽象成开箱即用的通用领域包。

## License

当前仓库尚未包含许可证文件。正式公开发布前，请补充许可证并在此处添加链接。
