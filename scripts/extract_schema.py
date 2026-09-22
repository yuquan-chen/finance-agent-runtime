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
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

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
            if table["table_name"] == table_name and not any(
                c["name"] == column_name for c in table["columns"]
            ):
                # 检查列是否已存在
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
    sql_type = sql_type.upper().strip()
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
        'DOUBLE PRECISION': 'numeric',
        'VARCHAR': 'varchar',
        'CHARACTER VARYING': 'varchar',
        'CHAR': 'varchar',
        'TEXT': 'text',
        'BOOLEAN': 'boolean',
        'BOOL': 'boolean',
        'UUID': 'uuid',
        'JSON': 'json',
        'JSONB': 'jsonb',
        'TIMESTAMP': 'timestamptz',
        'TIMESTAMPTZ': 'timestamptz',
        'TIMESTAMP WITH TIME ZONE': 'timestamptz',
        'TIMESTAMP WITHOUT TIME ZONE': 'timestamp',
        'DATE': 'date',
        'TIME': 'time',
    }

    for type_name in sorted(type_map, key=len, reverse=True):
        if sql_type.startswith(type_name):
            return type_map[type_name]

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
# TypeORM 的审计字段不是普通的 ``@Column``。这些字段经常定义在
# ``Base`` 基类中；如果不显式识别它们，所有继承该基类的表都会缺少
# created_at / update_at 等真实列。
AUDIT_COLUMN_RE = re.compile(
    r'@(?P<decorator>CreateDateColumn|UpdateDateColumn|DeleteDateColumn)'
    r'\(\s*(?:\{(?P<options>[^}]*)\})?\s*\)\s*\n\s*'
    r'(?P<field>\w+)[\?:]',
    re.MULTILINE,
)
VERSION_COLUMN_RE = re.compile(
    r'@VersionColumn\(\s*(?:\{(?P<options>[^}]*)\})?\s*\)\s*\n\s*'
    r'(?P<field>\w+)[\?:]',
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
        class_content = _class_block(content, class_name)
        if class_content is None:
            return columns
        content = class_content

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

    # 提取审计字段。它们使用 CreateDateColumn 等专用装饰器，不能被
    # COLUMN_RE 捕获；默认类型是 timestamptz。
    for col_match in AUDIT_COLUMN_RE.finditer(content):
        field_name = col_match.group('field')
        if field_name in seen_fields:
            continue
        col_body = col_match.group('options') or ''
        type_match = TYPE_RE.search(col_body)
        comment_match = COMMENT_RE.search(col_body)
        nullable_match = NULLABLE_RE.search(col_body)
        columns.append({
            'name': field_name,
            'type': _map_typeorm_type(type_match.group(1)) if type_match else 'timestamptz',
            'nullable': nullable_match.group(1) == 'true' if nullable_match else True,
            'description': comment_match.group(1) if comment_match else '',
        })
        seen_fields.add(field_name)

    # VersionColumn 同样是专用装饰器；没有显式 type 时按 TypeORM 默认
    # 的整型版本列处理。
    for col_match in VERSION_COLUMN_RE.finditer(content):
        field_name = col_match.group('field')
        if field_name in seen_fields:
            continue
        col_body = col_match.group('options') or ''
        type_match = TYPE_RE.search(col_body)
        columns.append({
            'name': field_name,
            'type': _map_typeorm_type(type_match.group(1)) if type_match else 'integer',
            'nullable': False,
            'description': '',
        })
        seen_fields.add(field_name)

    return columns


def _class_block(content: str, class_name: str) -> str | None:
    """返回目标类的源码块，避免把同一文件中另一个类的继承关系混入。"""
    class_pattern = re.compile(
        rf'export\s+(?:abstract\s+)?class\s+{re.escape(class_name)}\b',
        re.IGNORECASE,
    )
    class_match = class_pattern.search(content)
    if not class_match:
        return None

    next_class_pattern = re.compile(r'export\s+(?:abstract\s+)?class\s+\w+', re.IGNORECASE)
    end_pos = len(content)
    next_match = next_class_pattern.search(content, class_match.end())
    if next_match:
        end_pos = next_match.start()
    return content[class_match.start():end_pos]


def _base_class_name(content: str, class_name: str) -> str | None:
    """只读取指定类的 extends，而不是文件中的第一个 class。"""
    class_pattern = re.compile(
        rf'export\s+(?:abstract\s+)?class\s+{re.escape(class_name)}\s+extends\s+(\w+)',
        re.IGNORECASE,
    )
    match = class_pattern.search(content)
    return match.group(1) if match else None


def _find_class_file(filepath: Path, class_name: str) -> Path | None:
    """在上游 repository 的相邻目录中定位基类定义。"""
    search_dirs = [filepath.parent, filepath.parent.parent, filepath.parent.parent / "base"]
    checked: set[Path] = set()
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for ts_file in search_dir.rglob("*.ts"):
            # 多层基类（Base / TrxBase / TrxBaseV2）会定义在同一个文件。
            # 不能仅因文件相同而跳过，循环由 seen_classes 按“文件+类名”阻断。
            if ts_file in checked:
                continue
            checked.add(ts_file)
            try:
                candidate = ts_file.read_text()
            except UnicodeDecodeError:
                continue
            if re.search(rf'export\s+(?:abstract\s+)?class\s+{re.escape(class_name)}\b', candidate):
                return ts_file
    return None


def _resolve_inherited_columns(
    filepath: Path,
    content: str,
    class_name: str,
    seen_classes: set[tuple[Path, str]] | None = None,
) -> list[dict[str, Any]]:
    """递归解析指定实体的继承链，并保留 TypeORM 基类列。"""
    columns = []
    seen_classes = seen_classes or set()
    identity = (filepath.resolve(), class_name)
    if identity in seen_classes:
        return columns
    seen_classes.add(identity)

    base_class_name = _base_class_name(content, class_name)
    if not base_class_name:
        return columns

    base_file = _find_class_file(filepath, base_class_name)
    if not base_file:
        return columns

    base_content = base_file.read_text()
    # 基类自身的字段优先于其父类；最终由调用方用实体本身字段覆盖。
    columns.extend(_extract_columns_from_content(base_content, base_class_name))
    columns.extend(_resolve_inherited_columns(base_file, base_content, base_class_name, seen_classes))

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

    # 提取列（包括继承的基类）。必须把当前实体类名传给继承解析，
    # 否则一个文件存在多个 class 时会误从第一个 class 开始找 extends。
    entity_pos = content.find('@Entity')
    entity_class_match = re.search(
        r'export\s+(?:abstract\s+)?class\s+(\w+)',
        content[entity_pos:] if entity_pos >= 0 else content,
    )
    entity_class_name = entity_class_match.group(1) if entity_class_match else None
    columns = _extract_columns_from_content(content, entity_class_name)
    inherited_columns = (
        _resolve_inherited_columns(filepath, content, entity_class_name)
        if entity_class_name else []
    )

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
    try:
        with conn.cursor() as cursor:
            # Read directly from PostgreSQL system catalogs. This avoids the
            # information_schema join plus per-column description function
            # lookup that is expensive on the remote RDS instance.
            cursor.execute("""
                SELECT
                    cls.relname,
                    COALESCE(table_description.description, ''),
                    attr.attname,
                    format_type(attr.atttypid, attr.atttypmod),
                    NOT attr.attnotnull,
                    COALESCE(description.description, '')
                FROM pg_catalog.pg_class AS cls
                JOIN pg_catalog.pg_namespace AS ns
                    ON ns.oid = cls.relnamespace
                JOIN pg_catalog.pg_attribute AS attr
                    ON attr.attrelid = cls.oid
                   AND attr.attnum > 0
                   AND NOT attr.attisdropped
                LEFT JOIN pg_catalog.pg_description AS description
                    ON description.objoid = cls.oid
                   AND description.objsubid = attr.attnum
                LEFT JOIN pg_catalog.pg_description AS table_description
                    ON table_description.objoid = cls.oid
                   AND table_description.objsubid = 0
                WHERE ns.nspname = 'public'
                  AND cls.relkind IN ('r', 'p', 'v', 'm')
                ORDER BY cls.relname, attr.attnum
            """)
            column_rows = cursor.fetchall()

            cursor.execute("""
                SELECT
                    child_cls.relname AS child_table,
                    child_attr.attname AS child_column,
                    parent_cls.relname AS parent_table,
                    parent_attr.attname AS parent_column
                FROM pg_catalog.pg_constraint AS con
                JOIN pg_catalog.pg_class AS child_cls
                    ON child_cls.oid = con.conrelid
                JOIN pg_catalog.pg_namespace AS child_ns
                    ON child_ns.oid = child_cls.relnamespace
                JOIN pg_catalog.pg_class AS parent_cls
                    ON parent_cls.oid = con.confrelid
                JOIN pg_catalog.pg_namespace AS parent_ns
                    ON parent_ns.oid = parent_cls.relnamespace
                JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS child_key(attnum, position)
                    ON TRUE
                JOIN LATERAL unnest(con.confkey) WITH ORDINALITY AS parent_key(attnum, position)
                    ON parent_key.position = child_key.position
                JOIN pg_catalog.pg_attribute AS child_attr
                    ON child_attr.attrelid = child_cls.oid
                   AND child_attr.attnum = child_key.attnum
                JOIN pg_catalog.pg_attribute AS parent_attr
                    ON parent_attr.attrelid = parent_cls.oid
                   AND parent_attr.attnum = parent_key.attnum
                WHERE con.contype = 'f'
                  AND child_ns.nspname = 'public'
                  AND parent_ns.nspname = 'public'
                ORDER BY child_cls.relname, child_attr.attnum
            """)
            foreign_key_rows = cursor.fetchall()
    finally:
        conn.close()

    tables_by_name: dict[str, dict[str, Any]] = {}
    for table_name, table_comment, col_name, data_type, nullable, description in column_rows:
        table = tables_by_name.setdefault(
            table_name,
            {
                'table_name': table_name,
                'table_comment': table_comment or '',
                'columns': [],
            },
        )
        table['columns'].append({
            'name': col_name,
            'type': _normalize_sql_type(data_type.split('(')[0]),
            'nullable': nullable,
            'description': description or '',
        })

    for child_table, child_column, parent_table, parent_column in foreign_key_rows:
        table = tables_by_name.get(child_table)
        if not table:
            continue
        for column in table['columns']:
            if column['name'] == child_column:
                column['foreign_key'] = f"{parent_table}.{parent_column}"
                break

    return list(tables_by_name.values())


# ---------------------------------------------------------------------------
# 生成 Python 注册文件
# ---------------------------------------------------------------------------

PYTHON_RESERVED = {'type', 'class', 'return', 'import', 'from', 'if', 'else', 'for', 'while', 'def', 'pass', 'None', 'True', 'False', 'col_type', 'nullable', 'sensitive', 'foreign_key', 'enum_values', 'original_name'}
RENAME_MAP = {'type': 'type_field', 'col_type': 'col_type_field'}


def _existing_business_metadata(output_path: Path) -> tuple[str, dict[str, str]]:
    """读取上一份快照中的人工/LLM 业务说明。

    ORM 是字段结构的事实源，但表级业务说明并不一定在 ORM 中。Schema
    同步时若直接覆盖生成文件，会把这层补充知识清空，所以只有在上游
    没有提供描述时才沿用已有描述。
    """
    if not output_path.exists():
        return "", {}

    content = output_path.read_text()
    table_match = re.search(r'@register_table\(name="[^"]+", description="([^"]*)"\)', content)
    table_description = table_match.group(1) if table_match else ""

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return table_description, {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if not (
                isinstance(statement, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "COLUMNS" for target in statement.targets)
            ):
                continue
            try:
                raw_columns = ast.literal_eval(statement.value)
            except (ValueError, TypeError):
                continue
            if not isinstance(raw_columns, dict):
                continue
            return table_description, {
                name: meta.get("description", "")
                for name, meta in raw_columns.items()
                if isinstance(name, str) and isinstance(meta, dict) and meta.get("description")
            }
    return table_description, {}


def generate_python_file(table_name: str, columns: list[dict], output_dir: Path, table_comment: str = '') -> Path:
    """生成 Python 注册文件。"""
    class_name = ''.join(word.capitalize() for word in table_name.split('_'))
    output_path = output_dir / f"{table_name}.py"
    existing_table_description, existing_column_descriptions = _existing_business_metadata(output_path)

    # 上游 ORM/DDL 的 comment 优先；没有时严格保留本地 LLM/人工补充。
    description = table_comment or existing_table_description

    def literal(value: Any) -> str:
        """生成可安全嵌入 Python 源文件的字符串字面量。"""
        return json.dumps(str(value), ensure_ascii=False)

    lines = [
        f'"""自动提取的 {table_name} 表 schema。"""',
        "from finance_agent.metadata.table_registry import register_table",
        "",
        "",
        f'@register_table(name={literal(table_name)}, description={literal(description)})',
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
            desc = col.get('description') or existing_column_descriptions.get(col_name, '')

            meta_parts = [f'"type": {literal(col_type)}']
            if not nullable:
                meta_parts.append('"nullable": False')
            if desc:
                meta_parts.append(f'"description": {literal(desc)}')

            meta_str = ', '.join(meta_parts)
            lines.append(f'        "{col_name}": {{{meta_str}}},')
        lines.append("    }")

    lines.append("")
    output_path.write_text('\n'.join(lines))
    return output_path


def generate_yaml_file(tables: list[dict[str, Any]], output_path: Path) -> Path:
    """Write a data-only schema snapshot; never writes business records."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1",
        "source": "database_metadata",
        "tables": [
            {
                "name": table["table_name"],
                "description": table.get("table_comment", ""),
                "columns": [
                    {
                        "name": column["name"],
                        "type": column.get("type", "text"),
                        "nullable": bool(column.get("nullable", True)),
                        **({"foreign_key": column["foreign_key"]} if column.get("foreign_key") else {}),
                        **({"description": column["description"]} if column.get("description") else {}),
                    }
                    for column in table.get("columns", [])
                ],
            }
            for table in sorted(tables, key=lambda item: item["table_name"])
        ],
    }
    output_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='数据库 Schema 提取工具')
    parser.add_argument('--from-sql', type=str, help='从 SQL DDL 文件提取')
    parser.add_argument('--from-db', type=str, help='从数据库连接提取')
    parser.add_argument('--from-entity', type=str, help='从 TypeORM entity 提取')
    parser.add_argument('--output', type=str, default=None, help='输出 YAML 文件路径')
    parser.add_argument('--tables', type=str, default=None, help='只提取指定表（逗号分隔）')

    args = parser.parse_args()

    if not any([args.from_sql, args.from_db, args.from_entity]):
        parser.print_help()
        print("\n错误: 请指定输入源 (--from-sql, --from-db, 或 --from-entity)")
        sys.exit(1)

    output_path = Path(args.output) if args.output else Path(__file__).parent.parent / 'schema_catalog' / 'schema.yaml'

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

    # 生成 YAML 文件
    print(f"找到 {len(tables)} 个表:")
    for table in sorted(tables, key=lambda x: x['table_name']):
        print(f"  {table['table_name']:30s} ({len(table['columns']):2d} 列)")

    generate_yaml_file(tables, output_path)
    print(f"\n输出文件: {output_path}")
    print("请在 config/table_metadata.yaml 和 schema_catalog/value_aliases.yaml 中补充业务元数据。")


if __name__ == '__main__':
    main()
