# Schema Catalog

这个目录保存不属于上游 ORM、但对 Agent 理解业务必需的版本化元数据。

## 内容

- `table_descriptions.yaml`：173 张表的简短中文业务说明。它是 LLM 识别业务表时使用的语义层，不包含任何真实数据行、客户信息或查询结果。

数据库字段、类型和继承关系的结构快照位于 `tables/`，由上游项目 `/Users/joybot/Desktop/code/wavepool-core/src/repository` 的 TypeORM Entity 提取。

## 同步规则

1. 上游 ORM 是字段结构的事实源。
2. 本目录的 YAML 是表级业务语义的事实源；schema 同步不得删除或覆盖它。
3. 上游没有说明的新表，才允许用本地 LLM 补充 description；生成结果先人工检查，再提交到 Git。
4. 任何同步都必须通过字段一致性校验后才可提交。

## 常用命令

```bash
# 更新字段结构快照（会保留已有 description）
.venv/bin/python scripts/extract_schema.py \
  --from-entity /Users/joybot/Desktop/code/wavepool-core/src/repository \
  --output schema_catalog/tables

# 校验 173 张表的字段与上游 Entity 完全一致
.venv/bin/python scripts/verify_schema_sync.py \
  --from-entity /Users/joybot/Desktop/code/wavepool-core/src/repository

# 只为缺少说明的表调用本地 LM Studio；支持安全断点续跑
.venv/bin/python scripts/generate_table_descriptions.py --limit 8
```

不要把真实数据、SQL 查询结果或敏感字段样例写入此目录。
