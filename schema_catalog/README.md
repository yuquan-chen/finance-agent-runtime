# Schema Catalog

这个目录保存 Agent Schema Catalog。开源仓库包含一个不含真实业务数据的 `demo_schema.yaml`，用于 mock 模式和快速体验；每个使用者接入自己的数据库后，应生成独立的 `schema.yaml`，不要把不同数据库的 Schema 混用。

## 当前基线

- mock 模式：使用仓库内置的最小 demo Schema。
- 真实数据库模式：使用者自行生成本地 `schema.yaml`，内容取决于自己的数据库。
- 结构来源：PostgreSQL `information_schema` 和系统目录。

## 文件说明

- `schema.yaml`：本地生成的 YAML Schema 快照；包含表名、字段名、类型、可空性和数据库注释，不包含业务数据。
- `demo_schema.yaml`：仓库内置的最小示例 Schema，只用于 mock 模式。
- 业务别名、字段敏感级别、数据范围和表关系需要在确认业务规则后单独补充。

## 同步命令

```bash
.venv/bin/python scripts/extract_schema.py \
  --from-db "$DATABASE_URL" \
  --output schema_catalog/schema.yaml
```

同步前应确认 `DATABASE_URL` 指向目标测试库，并使用只读账号。同步过程只读取元数据，不读取业务数据，不修改数据库。

## 后续补充

Schema Catalog 只描述数据库结构，不负责实现 RBAC。后续需要补充：

- 业务模块和页面映射；
- 表之间的主键和关联关系；
- 字段业务含义和状态枚举；
- 敏感字段和脱敏规则；
- 查询能力和数据范围映射。
