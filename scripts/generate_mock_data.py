#!/usr/bin/env python3
"""为所有表生成 mock 数据。"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from finance_agent.metadata.table_registry import get_default_table_registry, ColumnMeta


def generate_value(col: ColumnMeta, row_idx: int) -> any:
    """根据列类型生成 mock 值。"""
    name = col.name.lower()
    col_type = col.type.lower()

    # UUID 类型
    if "uuid" in col_type or "uuid" in name:
        return str(uuid.uuid4())

    # 布尔类型
    if "bool" in col_type:
        return random.choice([True, False])

    # 时间类型
    if "timestamp" in col_type or "date" in col_type or "time" in name:
        base = datetime(2026, 1, 1)
        offset = timedelta(days=random.randint(0, 180), hours=random.randint(0, 23))
        return (base + offset).isoformat()

    # 数值类型
    if "int" in col_type or "serial" in col_type:
        return random.randint(1, 1000)
    if "numeric" in col_type or "decimal" in col_type or "float" in col_type or "double" in col_type:
        return round(random.uniform(0, 10000), 2)

    # JSON 类型
    if "json" in col_type:
        return {}

    # 特定字段名的智能生成
    if "status" in name:
        if "kyc" in name:
            return random.choice(["pending", "approved", "rejected", "in_review"])
        if "kyb" in name:
            return random.choice(["pending", "approved", "rejected", "in_review"])
        if "aml" in name:
            return random.choice(["clear", "flagged", "pending"])
        return random.choice(["active", "inactive", "pending", "suspended"])

    if "type" in name:
        return random.choice(["standard", "premium", "basic"])

    if "currency" in name:
        return random.choice(["USD", "EUR", "GBP", "CNY", "HKD", "SGD"])

    if "country" in name or "country_code" in name:
        return random.choice(["US", "CN", "GB", "SG", "HK", "JP"])

    if "email" in name:
        return f"user{row_idx}@example.com"

    if "phone" in name or "mobile" in name:
        return f"+1{random.randint(1000000000, 9999999999)}"

    if "name" in name and "file" not in name:
        if "first" in name:
            return random.choice(["Alice", "Bob", "Charlie", "David", "Eve"])
        if "last" in name:
            return random.choice(["Smith", "Johnson", "Williams", "Brown", "Jones"])
        if "company" in name or "legal" in name:
            return f"Company {row_idx + 1}"
        return f"Name {row_idx + 1}"

    if "amount" in name or "balance" in name or "price" in name or "fee" in name or "rate" in name:
        return round(random.uniform(0, 10000), 2)

    if "count" in name or "quantity" in name or "num" in name:
        return random.randint(0, 100)

    if "id" in name and "uuid" not in col_type:
        if col.name.endswith("_id"):
            return f"{col.name.replace('_id', '')}_{row_idx + 1:04d}"
        return f"id_{row_idx + 1:04d}"

    if "description" in name or "comment" in name or "note" in name:
        return f"Mock {col.name} for row {row_idx + 1}"

    if "url" in name or "link" in name:
        return f"https://example.com/{col.name}/{row_idx + 1}"

    if "address" in name:
        return f"{random.randint(1, 999)} Mock Street, City {row_idx + 1}"

    if "code" in name:
        return f"CODE{row_idx + 1:04d}"

    if "number" in name or "no" in name:
        return f"NUM{row_idx + 1:06d}"

    if "title" in name:
        return f"Mock Title {row_idx + 1}"

    if "content" in name or "text" in name or "message" in name:
        return f"Mock content for {col.name}"

    if "label" in name:
        return f"label_{row_idx + 1}"

    if "key" in name:
        return f"key_{row_idx + 1}"

    if "value" in name:
        return f"value_{row_idx + 1}"

    if "color" in name:
        return random.choice(["#FF0000", "#00FF00", "#0000FF", "#FFFF00"])

    if "icon" in name:
        return "icon_default"

    if "image" in name or "img" in name or "photo" in name or "avatar" in name:
        return f"https://example.com/images/{row_idx + 1}.png"

    if "language" in name or "locale" in name:
        return random.choice(["en", "zh", "ja", "ko"])

    if "level" in name:
        return random.choice(["low", "medium", "high", "critical"])

    if "priority" in name:
        return random.randint(1, 10)

    if "score" in name:
        return round(random.uniform(0, 100), 1)

    if "weight" in name:
        return random.randint(1, 100)

    if "version" in name:
        return f"v{random.randint(1, 10)}.{random.randint(0, 9)}"

    if "ip" in name:
        return f"192.168.{random.randint(0, 255)}.{random.randint(1, 254)}"

    if "token" in name:
        return f"tok_{uuid.uuid4().hex[:16]}"

    if "secret" in name or "password" in name or "hash" in name:
        return f"secret_{uuid.uuid4().hex[:16]}"

    if "flag" in name:
        return random.choice([True, False])

    if "reason" in name:
        return f"Mock reason for {col.name}"

    if "config" in name or "setting" in name:
        return {}

    if "meta" in name or "metadata" in name:
        return {}

    if "tags" in name:
        return random.choice([["tag1"], ["tag2"], ["tag1", "tag2"], []])

    if "permissions" in name:
        return ["read", "write"]

    if "roles" in name:
        return random.choice([["admin"], ["user"], ["admin", "user"]])

    if "options" in name or "choices" in name:
        return ["option1", "option2", "option3"]

    if "pattern" in name or "regex" in name:
        return ".*"

    if "condition" in name or "criteria" in name:
        return {"field": "status", "op": "=", "value": "active"}

    # 默认：varchar/text
    if "varchar" in col_type or "text" in col_type or "char" in col_type:
        return f"mock_{col.name}_{row_idx + 1}"

    # 默认
    return f"mock_{row_idx + 1}"


def generate_mock_data_for_table(table_name: str, columns: list[ColumnMeta], num_rows: int = 3) -> list[dict]:
    """为一个表生成 mock 数据。"""
    rows = []
    for i in range(num_rows):
        row = {}
        for col in columns:
            row[col.name] = generate_value(col, i)
        rows.append(row)
    return rows


def main():
    """主函数：为所有表生成 mock 数据。"""
    registry = get_default_table_registry()
    all_tables = registry.all_tables()

    print(f"开始为 {len(all_tables)} 个表生成 mock 数据...")

    mock_data = {}
    for table in all_tables:
        num_rows = 5 if len(table.columns) < 10 else 3
        mock_data[table.name] = generate_mock_data_for_table(table.name, table.columns, num_rows)

    # 保存到文件
    output_path = Path(__file__).parent.parent / "src" / "finance_agent" / "executor" / "mock_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mock_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 已生成 mock 数据，保存到: {output_path}")
    print(f"   总表数: {len(mock_data)}")
    total_rows = sum(len(rows) for rows in mock_data.values())
    print(f"   总行数: {total_rows}")


if __name__ == "__main__":
    main()
