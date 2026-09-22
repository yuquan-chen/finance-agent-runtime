# 开发指南

## 环境

- Python 3.11 或更高版本；
- mock 模式不需要 PostgreSQL；真实数据库模式才需要生成本地 `schema_catalog/schema.yaml`；
- 需要一个 LM Studio 或 OpenAI-compatible Chat Completions 服务来运行完整的自然语言规划；
- 可插拔材料处理模块如启用 PDF OCR，需要 Poppler；图片 OCR 需要 Tesseract。

## 安装和启动

```bash
./scripts/setup.sh
cp .env.example .env
./scripts/start.sh
```

默认地址：<http://127.0.0.1:8810/>。mock 模式会自动使用仓库内的 `schema_catalog/demo_schema.yaml`。

使用真实数据库时，不使用启动脚本也可以先生成 Schema 快照：

```bash
.venv/bin/python scripts/extract_schema.py \
  --from-db "$DATABASE_URL" \
  --output schema_catalog/schema.yaml
.venv/bin/python -m uvicorn finance_agent.api.app:app --host 127.0.0.1 --port 8810 --reload
```

健康检查：

```bash
./scripts/health.sh
```

## LLM 配置

本地 LM Studio 示例：

```dotenv
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=qwen2.5-coder-7b-instruct-mlx
LMSTUDIO_API_KEY=lm-studio
```

远程 OpenAI-compatible 服务只替换 Base URL、模型和 API key。API key 只能保存在服务端环境变量或 `.env`，不能写入 prompt、响应或审计日志。

## 查询执行器

默认：

```dotenv
EXECUTOR_MODE=mock
```

只读数据库模式：

```dotenv
EXECUTOR_MODE=direct_db
DATABASE_URL=postgresql+psycopg://readonly_user:password@host:5432/database
```

`direct_db` 只接受经过 Runtime 校验的只读方法，并使用 `DB_STATEMENT_TIMEOUT_MS`、`DB_MAX_ROWS` 和 `config/policy.yaml` 的限制。不要使用具有写权限的数据库账号。

## 身份模式

本地开发：

```dotenv
AUTH_MODE=local
```

客户端可以使用 `X-User-Id` 和 `X-Workspace-Id`。这只适用于本地开发，不应当被当成生产认证方案。

受保护模式：

```dotenv
AUTH_MODE=required
AUTH_SECRET=long-random-secret
```

请求必须使用 HMAC HS256 Bearer JWT，并携带 `sub`、`workspace_id`、`exp`。生产环境还需要在反向代理或认证服务中完成真实登录、组织和角色映射。

## 测试和静态检查

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
```

测试数据和运行文件默认写入 `data/`；测试配置会将其重定向到临时目录。不要用生产数据验证查询流程。

## 常见问题

### 服务启动但模型请求失败

检查 `LMSTUDIO_BASE_URL`、`LMSTUDIO_MODEL` 和 API key，确认模型服务可访问。`/health` 只表示 FastAPI 进程存活，不会验证 LLM 或数据库连接。

### `direct_db` 启动失败

确认设置了 `DATABASE_URL`，数据库可连接，并且使用的是只读账号。若只是本地验证 Agent 流程，切回 `EXECUTOR_MODE=mock`。

### KYC PDF 无法 OCR

macOS 本机安装：

```bash
brew install tesseract poppler
```

Docker 镜像包含对应工具。OCR 原文仅用于当前会话草稿和人工确认，不代表外部 KYC 审批结果。

### 修改配置后行为没有变化

运行时通过 `lru_cache` 缓存全局实例。修改 `.env`、catalog、policy、operations 或 skills 后重启服务。

## 外部业务 API 接入前检查

在新增 Client 之前，先取得并固定：环境和 API 版本、认证方式、组织/账户范围、请求和响应样例、错误码、状态枚举、限流和幂等语义。具体模板见 [admin-api-integration.md](admin-api-integration.md)。
