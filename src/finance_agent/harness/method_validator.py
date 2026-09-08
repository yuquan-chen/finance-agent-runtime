from __future__ import annotations

import ast
import re

from finance_agent.builder.sql_builder import assert_readonly_sql
from finance_agent.harness.analysis_schema import HarnessReview, MethodDraft
from finance_agent.metadata.catalog import Catalog
from finance_agent.metadata.policy import Policy
from finance_agent.operations.registry import OperationRegistry


FORBIDDEN_CODE_NAMES = {"open", "eval", "exec", "compile", "__import__", "print", "input"}
FORBIDDEN_IMPORTS = {"os", "sys", "socket", "subprocess", "pathlib", "requests", "httpx", "sqlalchemy"}


def validate_method_draft(
    method: MethodDraft,
    visible_catalog: Catalog,
    policy: Policy,
    operation_registry: OperationRegistry,
    table_registry=None,
) -> HarnessReview:
    errors: list[str] = []
    warnings: list[str] = []

    operation = operation_registry.get(method.operation)
    if operation is None:
        warnings.append(f"operation is not in registry yet and should be distilled: {method.operation}")
    elif method.method_type not in operation.execution_modes:
        errors.append(f"operation {method.operation} does not allow method type {method.method_type}")

    # Dependent methods (data_source=result_ref) operate on prior results, not catalog tables.
    # Skip catalog/field validation; still do SQL safety and code safety checks below.
    if method.data_source == "result_ref":
        if not method.result_ref:
            errors.append("dependent method requires result_ref")
    else:
        # 构建所有可见表的字段集合（支持多表查询）
        all_visible_fields: dict[str, set[str]] = {}
        for table in visible_catalog.tables:
            all_visible_fields[table.name] = table.column_names

        # 如果有 table_registry，用它来验证多表查询
        if table_registry:
            for table_name in table_registry.names():
                table_meta = table_registry.get(table_name)
                if table_meta and table_name not in all_visible_fields:
                    all_visible_fields[table_name] = table_meta.column_names

        # 检查主表
        if method.table not in all_visible_fields:
            errors.append(f"table is not visible: {method.table}")

        # 检查所有引用的字段
        for qualified in method.required_fields:
            if "." not in qualified:
                errors.append(f"required field must be qualified as table.field: {qualified}")
                continue
            table_name, field = qualified.split(".", 1)
            # 跳过 * 通配符（SELECT * 或 SELECT table.*）
            if field == "*":
                continue
            # 检查表是否可见
            if table_name not in all_visible_fields:
                errors.append(f"required field references unknown table: {qualified}")
                continue
            # 检查字段是否可见
            if field not in all_visible_fields[table_name]:
                # 未在 schema 中出现的字段一律阻止。把错误留给沙箱会导致
                # 用户看到无效候选 SQL，也让自动修复链路晚了一步。
                errors.append(f"required field is not visible: {qualified}")
                continue
            # 检查字段是否敏感
            table = visible_catalog.table(table_name)
            if table:
                column = table.get_column(field)
                if column and (column.sensitive or policy.is_sensitive_column_name(column.name)):
                    errors.append(f"required field is sensitive: {qualified}")

    if method.method_type == "sql":
        if not method.sql_template:
            errors.append("sql method requires sql_template")
        else:
            errors.extend(_validate_sql_parameter_bindings(method.sql_template, method.params))
            try:
                assert_readonly_sql(_strip_parameters(method.sql_template), policy)
            except Exception as exc:
                errors.append(f"sql validation failed: {type(exc).__name__}: {exc}")
            # 检查 SQL 语义合理性
            sql_errors = _validate_sql_semantics(
                method.sql_template,
                visible_catalog,
                table_registry,
                allow_prior_result=method.data_source == "result_ref",
            )
            errors.extend(sql_errors)
            errors.extend(_validate_sql_column_references(method.sql_template, visible_catalog, table_registry))
    elif method.method_type == "code":
        if not method.code:
            errors.append("code method requires code")
        else:
            errors.extend(_validate_code(method.code))

    return HarnessReview(allowed=not errors, errors=errors, warnings=warnings)


def _strip_parameters(sql: str) -> str:
    return re.sub(r":[A-Za-z_][A-Za-z0-9_]*", "NULL", sql)


def _validate_sql_parameter_bindings(sql: str, params: dict[str, object]) -> list[str]:
    """Ensure user values can only enter a query through declared SQL placeholders."""
    placeholders = set(re.findall(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", sql))
    bound_names = set(params)
    errors: list[str] = []

    missing = sorted(placeholders - bound_names)
    unused = sorted(bound_names - placeholders)
    if missing:
        errors.append(f"sql placeholders have no bound value: {', '.join(missing)}")
    if unused:
        errors.append(f"bound input values are not referenced by SQL: {', '.join(unused)}")

    # The SQL planner receives no input values. If a value nevertheless appears as a
    # string literal, reject it instead of relying on prompt compliance.
    string_literals = [match.group(1).replace("''", "'") for match in re.finditer(r"'((?:''|[^'])*)'", sql)]
    for name, value in params.items():
        if isinstance(value, str) and value.strip():
            normalized_value = re.sub(r"\s+", " ", value.strip()).casefold()
            for literal in string_literals:
                normalized_literal = re.sub(r"\s+", " ", literal.strip()).casefold()
                if normalized_literal == normalized_value:
                    errors.append(f"user input value must use a placeholder, not a SQL literal: {name}")
                    break

    # A planner may still invent a business filter such as
    # ``type = 'payment'`` even when no input slot exists. That is more
    # dangerous than a validation error: the query can return plausible but
    # semantically wrong data. Filter literals must therefore be parameterized
    # as well; SQL function literals such as DATE_TRUNC('month', ...) do not
    # match this predicate and remain allowed.
    filter_literal_pattern = re.compile(
        r"(?:\s*(?:<>|!=|>=|<=|=|>|<)\s*|\b(?:NOT\s+)?(?:LIKE|ILIKE)\s*|\bIN\s*\(\s*)"
        r"'((?:''|[^'])*)'",
        re.IGNORECASE,
    )
    for match in filter_literal_pattern.finditer(sql):
        literal = match.group(1).replace("''", "'").strip()
        errors.append(
            "unbound SQL filter literal is not allowed; use a declared input placeholder"
            + (f" (literal: {literal})" if literal else "")
        )
    return errors


# 状态类字段（字符串类型，不能用于数值计算）
STATUS_FIELDS = {
    "kyc_status", "aml_status", "card_kyb_status", "cw_kyb_status",
    "va_kyb_status", "acquiring_kyb_status", "status", "type",
    "risk_level", "source", "identifier_id", "legal_name", "legal_name_en",
}

# 数值聚合函数
NUMERIC_AGGREGATE_FUNCTIONS = {"SUM", "AVG", "COUNT", "MIN", "MAX"}


def _validate_sql_semantics(
    sql: str,
    visible_catalog: Catalog,
    table_registry=None,
    *,
    allow_prior_result: bool = False,
) -> list[str]:
    """检查 SQL 语义是否合理。

    主要检查：
    1. 是否对字符串字段使用了数值聚合函数（如 SUM(status)）
    2. 其他语义错误
    """
    errors = []
    sql_upper = sql.upper()

    # 检查是否对状态字段使用了数值聚合函数
    for func in NUMERIC_AGGREGATE_FUNCTIONS:
        # 匹配 SUM(field), AVG(field), COUNT(field) 等模式
        pattern = rf"{func}\s*\(\s*(?:COALESCE\s*\(\s*)?(\w+)"
        matches = re.finditer(pattern, sql_upper, re.IGNORECASE)
        for match in matches:
            field_name = match.group(1).lower()
            if field_name in STATUS_FIELDS:
                errors.append(
                    f"SQL 语义错误：不能对字符串字段 '{field_name}' 使用 {func}() 函数。"
                    f"字符串字段只能用于 WHERE/GROUP BY/ORDER BY，不能用于数值计算。"
                )

    # 检查 FROM 子句中的表是否存在
    from_match = re.search(r"FROM\s+(\w+)", sql, re.IGNORECASE)
    if from_match:
        table_name = from_match.group(1).lower()
        # 检查是否是已知的表
        known_tables = set()
        if visible_catalog:
            known_tables.update(t.name.lower() for t in visible_catalog.tables)
        if table_registry:
            known_tables.update(n.lower() for n in table_registry.names())

        # 常见的错误表名
        invalid_tables = {"customers", "users", "client", "customer"}
        if not allow_prior_result:
            invalid_tables.add("prior_result")
        if table_name in invalid_tables:
            errors.append(
                f"SQL 表名错误：'{table_name}' 表不存在。"
                f"KYC/KYB 查询应使用 'account' 表。"
            )

    return errors


def _validate_sql_column_references(sql: str, visible_catalog: Catalog, table_registry=None) -> list[str]:
    """在进入沙箱前检查 SQL 所引用表的字段，避免把数据库错误交给用户。"""
    all_tables: dict[str, set[str]] = {}
    if visible_catalog:
        all_tables.update({table.name.lower(): table.column_names for table in visible_catalog.tables})
    if table_registry:
        all_tables.update(
            {
                name.lower(): table_registry.get(name).column_names
                for name in table_registry.names()
                if table_registry.get(name) is not None
            }
        )

    # 命名参数不是字段。参数名即使恰好与其它表的列同名，
    # 也不能把它误判为本次查询引用了错误字段。
    sql_without_parameters = _strip_parameters(sql)

    referenced_tables = [match.lower() for match in re.findall(r"(?:FROM|JOIN)\s+(\w+)", sql_without_parameters, re.IGNORECASE)]
    known_referenced = {name: all_tables[name] for name in referenced_tables if name in all_tables}
    if not known_referenced:
        return []

    errors: list[str] = []
    sql_keywords = {
        "select", "from", "where", "join", "on", "and", "or", "as", "group", "by", "order", "asc", "desc",
        "limit", "offset", "having", "distinct", "count", "sum", "avg", "min", "max", "coalesce", "date_trunc",
        "current_date", "interval", "null", "is", "not", "in", "like", "case", "when", "then", "else", "end",
    }
    select_aliases = {alias.lower() for alias in re.findall(r"\bAS\s+(\w+)", sql_without_parameters, re.IGNORECASE)}
    # 所有已知的列名，只要出现在 SQL 中，就必须属于本次 FROM/JOIN 的任一表。
    available_columns = set().union(*known_referenced.values())
    all_known_columns = set().union(*all_tables.values()) if all_tables else set()
    for field in sorted(all_known_columns - available_columns - sql_keywords - select_aliases):
        if re.search(rf"\b{re.escape(field)}\b", sql_without_parameters, re.IGNORECASE):
            errors.append(
                f"SQL 字段错误：'{field}' 不属于本次查询的表 "
                f"({', '.join(referenced_tables)})。"
            )
    return errors


def _validate_code(code: str) -> list[str]:
    errors: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"code syntax error: {exc}"]

    function_defs = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(function_defs) != 1 or len(function_defs) != len(tree.body):
        errors.append("code method must contain exactly one function definition")

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name.split(".", 1)[0] for alias in node.names]
            forbidden = sorted(set(names) & FORBIDDEN_IMPORTS)
            if forbidden:
                errors.append(f"forbidden imports: {', '.join(forbidden)}")
            else:
                errors.append("imports are not allowed in pure method draft")
        if isinstance(node, ast.Call):
            called = _call_name(node.func)
            if called in FORBIDDEN_CODE_NAMES:
                errors.append(f"forbidden call in pure method draft: {called}")
        if isinstance(node, ast.Attribute) and node.attr in {"connect", "request", "getenv", "system", "popen"}:
            errors.append(f"forbidden attribute access in pure method draft: {node.attr}")
    return errors


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""
