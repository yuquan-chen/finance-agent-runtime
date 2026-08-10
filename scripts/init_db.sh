#!/bin/bash
# 初始化 PostgreSQL 数据库

set -e

# 默认配置
DB_NAME="${PG_DATABASE:-finance_sandbox}"
DB_USER="${PG_USER:-postgres}"

echo "Creating database: $DB_NAME"

# 创建数据库
psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || echo "Database $DB_NAME already exists"

echo "Database initialized successfully!"
