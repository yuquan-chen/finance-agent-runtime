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
                # 对于自定义 SQL，字段不可见只是警告，不是错误
                # 因为 LLM 可能生成了使用不存在字段的 SQL，沙箱会捕获这个错误
                if method.name.startswith("llm_custom"):
                    warnings.append(f"required field is not visible (will be validated in sandbox): {qualified}")
                else:
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
    elif method.method_type == "code":
        if not method.code:
            errors.append("code method requires code")
        else:
            errors.extend(_validate_code(method.code))

    return HarnessReview(allowed=not errors, errors=errors, warnings=warnings)


def _strip_parameters(sql: str) -> str:
    return re.sub(r":[A-Za-z_][A-Za-z0-9_]*", "NULL", sql)


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
