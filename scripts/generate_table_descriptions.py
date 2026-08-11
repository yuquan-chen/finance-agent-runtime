#!/usr/bin/env python3
"""使用 LM Studio（本地 LLM）为表自动生成描述。

用法：
  python scripts/generate_table_descriptions.py

确保 LM Studio 已启动并加载了模型。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

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

    # 清理描述（去掉可能的引号、句号等）
    description = description.strip('"\'')
    if description.endswith('。'):
        description = description[:-1]

    # 确保长度在 30-50 字符
    if len(description) > 50:
        description = description[:47] + "..."

    return description


def update_table_file(file_path: Path, table_name: str, description: str) -> None:
    """更新表定义文件，添加描述。"""
    content = file_path.read_text()

    # 查找 @register_table 装饰器
    pattern = r'@register_table\(name="' + re.escape(table_name) + r'",\s*description="[^"]*"\)'
    replacement = f'@register_table(name="{table_name}", description="{description}")'

    new_content = re.sub(pattern, replacement, content)

    if new_content != content:
        file_path.write_text(new_content)
        print(f"  ✓ 已更新: {file_path.name}")
    else:
        print(f"  - 未找到匹配的装饰器: {file_path.name}")


def main():
    print("=" * 60)
    print("使用 LM Studio 为表自动生成描述")
    print("=" * 60)
    print(f"LM Studio 地址: {LMSTUDIO_BASE_URL}")
    print(f"模型: {LMSTUDIO_MODEL}")

    # 获取表注册表
    registry = get_default_table_registry()
    tables = registry.all_tables()

    # 找出没有描述的表
    tables_without_desc = [t for t in tables if not t.description]
    print(f"需要生成描述的表: {len(tables_without_desc)} 个")

    if not tables_without_desc:
        print("\n所有表都有描述，无需处理。")
        return

    # 表定义目录
    tables_dir = project_root / "src" / "finance_agent" / "metadata" / "tables"

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

            # 更新文件
            file_path = tables_dir / f"{table.name}.py"
            if file_path.exists():
                update_table_file(file_path, table.name, description)
                updated_count += 1
            else:
                print(f"  ✗ 文件不存在: {file_path}")
        except Exception as e:
            print(f"  ✗ 生成失败: {e}")

    print("\n" + "=" * 60)
    print(f"完成！已更新 {updated_count} 个表的描述。")
    print("=" * 60)


if __name__ == "__main__":
    main()
