#!/usr/bin/env python3
"""使用 LM Studio（本地 LLM）为表自动生成业务 description 覆盖层。

用法：
  python scripts/generate_table_descriptions.py

确保 LM Studio 已启动并加载了模型。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests
import yaml

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from finance_agent.metadata.table_registry import get_default_table_registry

# LM Studio 配置
LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
LMSTUDIO_MODEL = "qwen2.5-coder-7b-instruct-mlx"  # 或其他你加载的模型


def generate_description(table_name: str, columns: list[str]) -> str:
    """使用 LM Studio 生成表描述。"""
    prompt = f"""请为以下数据库表生成一个简洁的中文描述。

表名：{table_name}
字段：{', '.join(columns[:20])}

要求：
1. 描述长度控制在 30-50 个字符
2. 说明表的主要用途和记录的数据类型
3. 使用中文
4. 不要加句号

示例格式：
- 账户表，记录客户基本信息和 KYC 状态
- 卡交易表，记录消费、退款、冲正
- 付款交易表，记录付款和转账

只返回描述，不要其他文字。"""

    response = requests.post(
        f"{LMSTUDIO_BASE_URL}/chat/completions",
        json={
            "model": LMSTUDIO_MODEL,
            "messages": [
                {"role": "system", "content": "你是一个数据库专家，擅长为数据库表编写简洁的描述。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 100,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    description = data["choices"][0]["message"]["content"].strip()

    # 清理模型偶尔输出的引号、Markdown 列表符和句号。
    description = description.strip('"\'').strip()
    description = re.sub(r"^(?:[-*•]\s+)+", "", description)
    if description.endswith('。'):
        description = description[:-1]

    # 确保长度在 30-50 字符
    if len(description) > 50:
        description = description[:47] + "..."

    return description


OVERLAY_PATH = project_root / "schema_catalog" / "table_descriptions.yaml"


def load_overlay() -> dict[str, str]:
    if not OVERLAY_PATH.exists():
        return {}
    raw = yaml.safe_load(OVERLAY_PATH.read_text()) or {}
    tables = raw.get("tables", {}) if isinstance(raw, dict) else {}
    return {
        str(name): normalize_description(str(value))
        for name, value in tables.items()
        if str(value).strip()
    }


def normalize_description(description: str) -> str:
    description = description.strip('"\'').strip()
    return re.sub(r"^(?:[-*•]\s+)+", "", description).rstrip("。").strip()


def save_overlay(descriptions: dict[str, str]) -> None:
    """以固定的双引号 YAML 格式写入覆盖层。"""
    lines = ["# 业务 description 覆盖层：由人工或本地 LLM 维护，不随 ORM schema 同步覆盖。", "tables:"]
    for table_name, description in sorted(descriptions.items()):
        lines.append(f"  {table_name}: {json.dumps(normalize_description(description), ensure_ascii=False)}")
    OVERLAY_PATH.write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description="用本地 LLM 补齐缺失的表级业务说明")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="本次最多生成多少条；适合受执行时间限制的环境断点续跑",
    )
    parser.add_argument(
        "--include-source",
        action="store_true",
        help="也将仅来自上游 ORM 注释、尚未写入覆盖层的 description 统一为本地短描述",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="只规范已有 YAML 的列表符号与引号格式，不调用 LLM",
    )
    args = parser.parse_args()
    print("=" * 60)
    print("使用 LM Studio 为表自动生成描述")
    print("=" * 60)
    print(f"LM Studio 地址: {LMSTUDIO_BASE_URL}")
    print(f"模型: {LMSTUDIO_MODEL}")

    # 获取表注册表
    registry = get_default_table_registry()
    tables = registry.all_tables()

    overlay = load_overlay()
    if args.normalize:
        save_overlay(overlay)
        print(f"已规范 {len(overlay)} 条 description。")
        return
    # 装饰器内已有上游注释、或覆盖层已有业务说明的表都必须保留。
    tables_without_desc = [
        table
        for table in tables
        if not overlay.get(table.name) and (args.include_source or not table.description)
    ]
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit must be positive")
        tables_without_desc = tables_without_desc[:args.limit]
    print(f"需要生成描述的表: {len(tables_without_desc)} 个")

    if not tables_without_desc:
        print("\n所有表都有描述，无需处理。")
        return

    # 为每个表生成描述
    print("\n开始生成描述...")
    updated_count = 0

    for i, table in enumerate(tables_without_desc, 1):
        print(f"\n[{i}/{len(tables_without_desc)}] {table.name}")

        # 获取列名
        columns = [col.name for col in table.columns]

        # 生成描述
        try:
            description = generate_description(table.name, columns)
            print(f"  描述: {description}")

            overlay[table.name] = description
            # 每条立即落盘：本地模型调用较慢或进程被中断时，下次运行会
            # 自动跳过已完成项，实现无损断点续跑。
            save_overlay(overlay)
            updated_count += 1
        except Exception as e:
            print(f"  ✗ 生成失败: {e}")

    print("\n" + "=" * 60)
    print(f"完成！已更新 {updated_count} 个表的描述。")
    print("=" * 60)


if __name__ == "__main__":
    main()
