#!/usr/bin/env python3
"""数据库 Schema 提取工具。

支持多种输入格式：
  --from-sql    从 SQL DDL 文件提取
  --from-db     从数据库连接提取
  --from-entity 从 TypeORM entity 文件提取

用法：
  python scripts/extract_schema.py --from-sql /path/to/ddl/
  python scripts/extract_schema.py --from-db postgresql://user:pass@host/db
  python scripts/extract_schema.py --from-entity /path/to/repository/
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# SQL DDL 解析
# ---------------------------------------------------------------------------

def parse_sql_ddl(content: str) -> list[dict[str, Any]]:
    """解析 SQL DDL，提取表和列信息。"""
    tables = []
    # 匹配 CREATE TABLE 语句
    create_pattern = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?'
        r'(?:["\']?(\w+)["\']?\.)?["\']?(\w+)["\']?\s*'
        r'\((.*?)\)\s*;',
        re.IGNORECASE | re.DOTALL,
    )

    for match in create_pattern.finditer(content):
        schema_name = match.group(1)
        table_name = match.group(2)
        body = match.group(3)

        columns = _parse_column_definitions(body)
        tables.append({
            "table_name": table_name,
            "columns": columns,
            "schema": schema_name,
        })

    # 匹配 COMMENT ON COLUMN 语句
    comment_pattern = re.compile(
        r"COMMENT\s+ON\s+COLUMN\s+(?:[\"']?(\w+)[\"']?\.)?[\"']?(\w+)[\"']?\.[\"']?(\w+)[\"']?\s+IS\s+'([^']*)'",
        re.IGNORECASE,
    )
    for match in comment_pattern.finditer(content):
        table_name = match.group(2)
        column_name = match.group(3)
        comment = match.group(4)

        # 找到对应的表和列，添加注释
        for table in tables:
            if table["table_name"] == table_name:
                for col in table["columns"]:
                    if col["name"] == column_name:
                        col["description"] = comment

    # 匹配 ALTER TABLE ADD COLUMN 语句
    alter_pattern = re.compile(
        r"ALTER\s+TABLE\s+(?:[\"']?(\w+)[\"']?\.)?[\"']?(\w+)[\"']?\s+"
        r"ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"']?(\w+)[\"']?\s+"
        r"(\w+(?:\([^)]*\))?)\s*(NULL|NOT\s+NULL)?",
        re.IGNORECASE,
    )
    for match in alter_pattern.finditer(content):
        table_name = match.group(2)
        column_name = match.group(3)
        col_type = match.group(4)
        nullable = match.group(5) is None or match.group(5).upper() == "NULL"

        # 找到对应的表，添加列
        for table in tables:
            if table["table_name"] == table_name:
                # 检查列是否已存在
                if not any(c["name"] == column_name for c in table["columns"]):
                    table["columns"].append({
                        "name": column_name,
                        "type": _normalize_sql_type(col_type),
                        "nullable": nullable,
                        "description": "",
                    })

    return tables


def _parse_column_definitions(body: str) -> list[dict[str, Any]]:
    """解析列定义。"""
    columns = []
    # 按逗号分割，但要考虑括号内的逗号
    parts = _split_column_definitions(body)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 跳过约束定义
        if re.match(r'(?:PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK|CONSTRAINT|INDEX)', part, re.IGNORECASE):
            continue

        # 解析列定义
        col_match = re.match(
            r"""[\"']?(\w+)[\"']?\s+(\w+(?:\([^)]*\))?)\s*(NOT\s+NULL|NULL)?""",
            part,
            re.IGNORECASE,
        )
        if col_match:
            col_name = col_match.group(1)
            col_type = col_match.group(2)
            nullable = col_match.group(3) is None or col_match.group(3).upper() == "NULL"

            columns.append({
                "name": col_name,
                "type": _normalize_sql_type(col_type),
                "nullable": nullable,
                "description": "",
            })

    return columns


def _split_column_definitions(body: str) -> list[str]:
    """按逗号分割列定义，考虑括号内的逗号。"""
    parts = []
    depth = 0
    current = []

    for char in body:
        if char == '(':
            depth += 1
            current.append(char)
        elif char == ')':
            depth -= 1
            current.append(char)
        elif char == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(char)

    if current:
        parts.append(''.join(current))

    return parts


def _normalize_sql_type(sql_type: str) -> str:
    """标准化 SQL 类型。"""
    sql_type = sql_type.upper()
    type_map = {
        'INT': 'integer',
        'INTEGER': 'integer',
        'BIGINT': 'bigint',
        'SMALLINT': 'smallint',
        'DECIMAL': 'numeric',
        'NUMERIC': 'numeric',
        'FLOAT': 'numeric',
        'REAL': 'numeric',
        'DOUBLE': 'numeric',
        'VARCHAR': 'varchar',
        'CHAR': 'varchar',
        'TEXT': 'text',
        'BOOLEAN': 'boolean',
        'BOOL': 'boolean',
        'UUID': 'uuid',
        'JSON': 'json',
        'JSONB': 'jsonb',
        'TIMESTAMP': 'timestamptz',
        'TIMESTAMPTZ': 'timestamptz',
        'DATE': 'date',
        'TIME': 'time',
    }

    # 提取基础类型（去掉括号）
    base_type = re.match(r'(\w+)', sql_type)
    if base_type:
        base = base_type.group(1)
        return type_map.get(base, 'text')

    return 'text'


# ---------------------------------------------------------------------------
# TypeORM Entity 解析
# ---------------------------------------------------------------------------

ENTITY_RE_WITH_NAME = re.compile(r'@Entity\(\s*\{[^}]*name:\s*[\'\"](\w+)[\'"]')
ENTITY_RE_WITHOUT_NAME = re.compile(r'@Entity\(\s*[\'\"](\w+)[\'"]\s*\)')
ENTITY_RE_WITH_COMMENT = re.compile(r'@Entity\(\s*[\'\"](\w+)[\'"]\s*,\s*\{[^}]*comment:\s*[\'\"]([^\'"]+)[\'"]\s*\}\s*\)')
ENTITY_RE_EMPTY = re.compile(r'@Entity\(\s*\)')
COLUMN_RE = re.compile(
    r'@Column\(\s*\{([^}]+)\}\s*\)\s*\n\s*(\w+)[\?:]',
    re.MULTILINE,
)
PRIMARY_COLUMN_RE = re.compile(
    r'@PrimaryColumn\(\s*(?:\{([^}]*)\})?\s*\)\s*\n\s*(\w+)[\?:]',
    re.MULTILINE,
)
PRIMARY_GENERATED_COLUMN_RE = re.compile(
    r'@PrimaryGeneratedColumn\(\s*[\'"]?(\w+)[\'"]?\s*(?:,\s*\{([^}]*)\})?\s*\)\s*\n\s*(\w+)[\?:]',
    re.MULTILINE,
)
COMMENT_RE = re.compile(r'comment:\s*[\'"]([^\'"]+)[\'"]')
TYPE_RE = re.compile(r'type:\s*[\'"](\w+)[\'"]')
NULLABLE_RE = re.compile(r'nullable:\s*(true|false)')
JSDOC_RE = re.compile(r'/\*\*\s*(.*?)\s*\*/\s*\n\s*@Entity', re.DOTALL)
SINGLE_LINE_COMMENT_RE = re.compile(r'//\s*(.*?)\s*\n\s*@Entity')


def _extract_columns_from_content(content: str, class_name: str | None = None) -> list[dict[str, Any]]:
    """从文件内容中提取列定义。

    如果指定了 class_name，只提取该类及其上方的装饰器。
    """
    columns = []
    seen_fields = set()

    # 如果指定了类名，只提取该类的作用域
    if class_name:
        # 找到类的起始位置
        class_pattern = re.compile(rf'export class {class_name}\b', re.IGNORECASE)
        class_match = class_pattern.search(content)
        if not class_match:
            return columns

        # 找到类的结束位置（下一个 export class 或文件结尾）
        next_class_pattern = re.compile(r'export class \w+', re.IGNORECASE)
        start_pos = class_match.start()
        end_pos = len(content)
        for next_match in next_class_pattern.finditer(content[class_match.end():]):
            end_pos = class_match.end() + next_match.start()
            break

        content = content[start_pos:end_pos]

    # 先提取主键（PrimaryGeneratedColumn）
    for col_match in PRIMARY_GENERATED_COLUMN_RE.finditer(content):
        pk_type = col_match.group(1)  # uuid, increment, 等
        col_body = col_match.group(2) or ''
        field_name = col_match.group(3)

        col_type = _map_typeorm_type(pk_type)
        nullable = False  # 主键不可为 null
        description = '主键'

        comment_match = COMMENT_RE.search(col_body)
        if comment_match:
            description = comment_match.group(1)

        if field_name not in seen_fields:
            seen_fields.add(field_name)
            columns.append({
                'name': field_name,
                'type': col_type,
                'nullable': nullable,
                'description': description,
            })

    # 提取 PrimaryColumn
    for col_match in PRIMARY_COLUMN_RE.finditer(content):
        col_body = col_match.group(1) or ''
        field_name = col_match.group(2)

        col_type = 'text'
        nullable = False  # 主键不可为 null
        description = '主键'

        type_match = TYPE_RE.search(col_body)
        if type_match:
            col_type = _map_typeorm_type(type_match.group(1))

        comment_match = COMMENT_RE.search(col_body)
        if comment_match:
            description = comment_match.group(1)

        if field_name not in seen_fields:
            seen_fields.add(field_name)
            columns.append({
                'name': field_name,
                'type': col_type,
                'nullable': nullable,
                'description': description,
            })

    # 提取普通列
    for col_match in COLUMN_RE.finditer(content):
        col_body = col_match.group(1)
        field_name = col_match.group(2)

        if field_name in seen_fields:
            continue

        col_type = 'text'
        nullable = True
        description = ''

        type_match = TYPE_RE.search(col_body)
        if type_match:
            col_type = _map_typeorm_type(type_match.group(1))

        nullable_match = NULLABLE_RE.search(col_body)
        if nullable_match:
            nullable = nullable_match.group(1) == 'true'

        comment_match = COMMENT_RE.search(col_body)
        if comment_match:
            description = comment_match.group(1)

        seen_fields.add(field_name)
        columns.append({
            'name': field_name,
            'type': col_type,
            'nullable': nullable,
            'description': description,
        })

    return columns


def _resolve_inherited_columns(filepath: Path, content: str) -> list[dict[str, Any]]:
    """解析继承的基类，提取列定义。"""
    columns = []

    # 查找 extends 基类
    extends_match = re.search(r'export class \w+ extends (\w+)', content)
    if not extends_match:
        return columns

    base_class_name = extends_match.group(1)

    # 在同目录和父目录中查找基类文件
    search_dirs = [filepath.parent, filepath.parent.parent, filepath.parent.parent / 'base']
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for ts_file in search_dir.glob('*.ts'):
            if ts_file == filepath:
                continue
            base_content = ts_file.read_text()
            # 查找基类定义
            if re.search(rf'export class {base_class_name}\b', base_content):
                # 只提取目标基类的列，不是整个文件的列
                columns.extend(_extract_columns_from_content(base_content, base_class_name))
                # 递归查找更上层的基类
                columns.extend(_resolve_inherited_columns(ts_file, base_content))
                break

    return columns


def parse_typeorm_entity(filepath: Path) -> dict[str, Any] | None:
    """解析 TypeORM entity 文件。"""
    content = filepath.read_text()

    # 提取表名
    table_name = None
    table_comment = ''

    # 先检查带 comment 的 Entity
    entity_comment_match = ENTITY_RE_WITH_COMMENT.search(content)
    if entity_comment_match:
        table_name = entity_comment_match.group(1)
        table_comment = entity_comment_match.group(2)
    else:
        entity_match = ENTITY_RE_WITH_NAME.search(content)
        if entity_match:
            table_name = entity_match.group(1)
        else:
            entity_match = ENTITY_RE_WITHOUT_NAME.search(content)
            if entity_match:
                table_name = entity_match.group(1)
            elif ENTITY_RE_EMPTY.search(content):
                class_match = re.search(r'export class (\w+)', content)
                if class_match:
                    class_name = class_match.group(1)
                    table_name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()

    if not table_name:
        return None

    # 如果没有从 Entity 提取到 comment，尝试从 JSDoc 提取
    if not table_comment:
        jsdoc_match = JSDOC_RE.search(content)
        if jsdoc_match:
            jsdoc_content = jsdoc_match.group(1).strip()
            # 处理单行和多行 JSDoc
            if '\n' in jsdoc_content:
                # 多行 JSDoc
                jsdoc_lines = jsdoc_content.split('\n')
                comment_lines = []
                for line in jsdoc_lines:
                    line = line.strip()
                    if line.startswith('*'):
                        line = line[1:].strip()
                    if line:
                        comment_lines.append(line)
                if comment_lines:
                    table_comment = ' '.join(comment_lines)
            else:
                # 单行 JSDoc
                table_comment = jsdoc_content

    # 如果还没有 comment，尝试从单行注释提取
    if not table_comment:
        single_line_match = SINGLE_LINE_COMMENT_RE.search(content)
        if single_line_match:
            table_comment = single_line_match.group(1).strip()

    # 提取列（包括继承的基类）
    columns = _extract_columns_from_content(content)
    inherited_columns = _resolve_inherited_columns(filepath, content)

    # 合并继承的列（当前类的列优先）
    seen_fields = {col['name'] for col in columns}
    for col in inherited_columns:
        if col['name'] not in seen_fields:
            columns.append(col)
            seen_fields.add(col['name'])

    return {
        'table_name': table_name,
        'table_comment': table_comment,
        'columns': columns,
        'source_file': str(filepath),
    }


def _map_typeorm_type(typeorm_type: str) -> str:
    """TypeORM 类型映射。"""
    mapping = {
        'uuid': 'uuid',
        'varchar': 'varchar',
        'text': 'text',
        'int4': 'integer',
        'int8': 'bigint',
        'numeric': 'numeric',
        'decimal': 'numeric',
        'bool': 'boolean',
        'boolean': 'boolean',
        'json': 'json',
        'jsonb': 'jsonb',
        'timestamptz': 'timestamptz',
        'timestamp': 'timestamptz',
    }
    return mapping.get(typeorm_type, 'text')


# ---------------------------------------------------------------------------
# 数据库连接解析
# ---------------------------------------------------------------------------

def parse_database_connection(connection_string: str) -> list[dict[str, Any]]:
    """从数据库连接提取 schema。"""
    try:
        import psycopg2
    except ImportError:
        print("错误: 需要安装 psycopg2。运行: pip install psycopg2-binary")
        sys.exit(1)

    conn = psycopg2.connect(connection_string)
    cursor = conn.cursor()

    # 查询所有表
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    table_names = [row[0] for row in cursor.fetchall()]

    tables = []
    for table_name in table_names:
        # 查询表注释
        cursor.execute("""
            SELECT pgd.description
            FROM pg_catalog.pg_statio_all_tables st
            LEFT JOIN pg_catalog.pg_description pgd
                ON pgd.objoid = st.relid AND pgd.objsubid = 0
            WHERE st.schemaname = 'public' AND st.relname = %s
        """, (table_name,))
        table_comment_row = cursor.fetchone()
        table_comment = table_comment_row[0] if table_comment_row else ''

        # 查询列信息
        cursor.execute("""
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                pgd.description
            FROM information_schema.columns c
            LEFT JOIN pg_catalog.pg_statio_all_tables st
                ON c.table_schema = st.schemaname AND c.table_name = st.relname
            LEFT JOIN pg_catalog.pg_description pgd
                ON pgd.objoid = st.relid AND pgd.objsubid = c.ordinal_position
            WHERE c.table_schema = 'public' AND c.table_name = %s
            ORDER BY c.ordinal_position
        """, (table_name,))

        columns = []
        for row in cursor.fetchall():
            col_name, data_type, is_nullable, description = row
            columns.append({
                'name': col_name,
                'type': _normalize_sql_type(data_type),
                'nullable': is_nullable == 'YES',
                'description': description or '',
            })

        tables.append({
            'table_name': table_name,
            'table_comment': table_comment,
            'columns': columns,
        })

    cursor.close()
    conn.close()

    return tables


# ---------------------------------------------------------------------------
# 生成 Python 注册文件
# ---------------------------------------------------------------------------

PYTHON_RESERVED = {'type', 'class', 'return', 'import', 'from', 'if', 'else', 'for', 'while', 'def', 'pass', 'None', 'True', 'False', 'col_type', 'nullable', 'sensitive', 'foreign_key', 'enum_values', 'original_name'}
RENAME_MAP = {'type': 'type_field', 'col_type': 'col_type_field'}


def generate_python_file(table_name: str, columns: list[dict], output_dir: Path, table_comment: str = '') -> Path:
    """生成 Python 注册文件。"""
    class_name = ''.join(word.capitalize() for word in table_name.split('_'))

    # 处理表注释
    description = table_comment.replace('"', '\\"') if table_comment else ''

    lines = [
        f'"""自动提取的 {table_name} 表 schema。"""',
        "from finance_agent.metadata.table_registry import register_table",
        "",
        "",
        f'@register_table(name="{table_name}", description="{description}")',
        f"class {class_name}:",
    ]

    if not columns:
        lines.append("    pass")
    else:
        lines.append("    COLUMNS = {")
        for col in columns:
            col_name = col['name']
            col_type = col['type']
            nullable = col['nullable']
            desc = col.get('description', '').replace('"', '\\"')

            meta_parts = [f'"type": "{col_type}"']
            if not nullable:
                meta_parts.append('"nullable": False')
            if desc:
                meta_parts.append(f'"description": "{desc}"')

            meta_str = ', '.join(meta_parts)
            lines.append(f'        "{col_name}": {{{meta_str}}},')
        lines.append("    }")

    lines.append("")
    output_path = output_dir / f"{table_name}.py"
    output_path.write_text('\n'.join(lines))
    return output_path


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='数据库 Schema 提取工具')
    parser.add_argument('--from-sql', type=str, help='从 SQL DDL 文件提取')
    parser.add_argument('--from-db', type=str, help='从数据库连接提取')
    parser.add_argument('--from-entity', type=str, help='从 TypeORM entity 提取')
    parser.add_argument('--output', type=str, default=None, help='输出目录')
    parser.add_argument('--tables', type=str, default=None, help='只提取指定表（逗号分隔）')

    args = parser.parse_args()

    if not any([args.from_sql, args.from_db, args.from_entity]):
        parser.print_help()
        print("\n错误: 请指定输入源 (--from-sql, --from-db, 或 --from-entity)")
        sys.exit(1)

    # 输出目录
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path(__file__).parent.parent / 'src' / 'finance_agent' / 'metadata' / 'tables'
    output_dir.mkdir(parents=True, exist_ok=True)

    # 指定表过滤
    filter_tables = None
    if args.tables:
        filter_tables = set(args.tables.split(','))

    tables = []

    # 从 SQL DDL 提取
    if args.from_sql:
        sql_path = Path(args.from_sql)
        if sql_path.is_file():
            content = sql_path.read_text()
            tables = parse_sql_ddl(content)
        elif sql_path.is_dir():
            for sql_file in sorted(sql_path.glob('*.sql')):
                content = sql_file.read_text()
                tables.extend(parse_sql_ddl(content))
        else:
            print(f"错误: 路径不存在: {sql_path}")
            sys.exit(1)

    # 从数据库连接提取
    elif args.from_db:
        tables = parse_database_connection(args.from_db)

    # 从 TypeORM entity 提取
    elif args.from_entity:
        entity_path = Path(args.from_entity)
        if not entity_path.exists():
            print(f"错误: 路径不存在: {entity_path}")
            sys.exit(1)

        for ts_file in entity_path.rglob('*.repo.ts'):
            result = parse_typeorm_entity(ts_file)
            if result:
                tables.append(result)

    # 过滤
    if filter_tables:
        tables = [t for t in tables if t['table_name'] in filter_tables]

    # 生成文件
    print(f"找到 {len(tables)} 个表:")
    for table in sorted(tables, key=lambda x: x['table_name']):
        output_path = generate_python_file(
            table['table_name'],
            table['columns'],
            output_dir,
            table.get('table_comment', ''),
        )
        print(f"  {table['table_name']:30s} ({len(table['columns']):2d} 列) → {output_path.name}")

    print(f"\n输出目录: {output_dir}")
    print("请手动添加业务元数据（description、foreign_key、sensitive 等）。")


if __name__ == '__main__':
    main()
