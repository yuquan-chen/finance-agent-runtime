# 文档导航

本目录只保留当前项目需要维护的文档。

## 当前文档

| 文档 | 用途 |
| --- | --- |
| [architecture.svg](architecture.svg) | README 使用的当前运行架构图 |
| [current-architecture.md](current-architecture.md) | 当前组件、边界、数据流和状态模型 |
| [development.md](development.md) | 本地启动、配置、测试和排障 |
| [api.md](api.md) | 当前 Runtime HTTP API 和安全边界 |
| [admin-api-integration.md](admin-api-integration.md) | 外部业务 API 接入的设计约束和契约模板 |

代码和配置是实现事实源：

- HTTP 路由以 `src/finance_agent/api/` 为准；
- 工作流以 `src/finance_agent/graph/runtime.py` 和 `src/finance_agent/graph/state.py` 为准；
- Skill 以 `config/skills.yaml` 为准；
- 分析操作以 `config/operations.yaml` 为准；
- 查询策略以 `config/policy.yaml` 为准；
- Schema 以本地 `schema_catalog/schema.yaml` 和其同步规则为准；
- 行为回归以测试为准。

未来方案和历史资料不放在当前文档目录中。发生接口或状态变化时，先更新测试，再同步更新相关文档。
