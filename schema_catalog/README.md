# Schema Catalog

这个目录保存 DogPay 测试数据库生成的 Agent Schema Catalog。

## 当前基线

- 数据库：`test-dogpay`
- Schema：`public`
- 表数量：257
- 字段数量：4216
- 结构来源：PostgreSQL `information_schema` 和系统目录

## 文件说明

- `tables/`：按表生成的 Python Schema 注册文件；包含表名、字段名、类型、可空性和数据库注释。
- 业务别名、字段敏感级别、数据范围和表关系需要在确认业务规则后单独补充。

## 同步命令

```bash
.venv/bin/python scripts/extract_schema.py \
  --from-db "$DATABASE_URL" \
  --output schema_catalog/tables
```

同步前应确认 `DATABASE_URL` 指向目标测试库，并使用只读账号。同步过程只读取元数据，不读取业务数据，不修改数据库。

## 后续补充

Schema Catalog 只描述数据库结构，不负责实现 RBAC。后续需要补充：

- 业务模块和页面映射；
- 表之间的主键和关联关系；
- 字段业务含义和状态枚举；
- 敏感字段和脱敏规则；
- 查询能力和数据范围映射。
