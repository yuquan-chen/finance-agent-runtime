"""Schema-driven normalization of business filter values."""
from __future__ import annotations

from typing import Any

from finance_agent.graph.input_binding import normalize_relative_filter_values
from finance_agent.metadata.business_registry import BusinessTermRegistry
from finance_agent.metadata.table_registry import TableRegistry


def normalize_filter_values(
    params: dict[str, Any],
    filter_specs: list[dict[str, Any]],
    table_names: list[str],
    table_registry: TableRegistry,
) -> dict[str, Any]:
    """Map configured business aliases to canonical database values.

    The runtime does not know that a particular word means ``completed``.
    That relationship is read from the selected table schemas.  Ambiguous
    fields are left unchanged so a query cannot silently target the wrong
    status column.
    """
    specs_by_name = {
        str(spec.get("name")): spec
        for spec in filter_specs
        if isinstance(spec, dict) and spec.get("name")
    }
    normalized = dict(params)
    for source_name, value in params.items():
        if not isinstance(value, str) or not value.strip():
            continue
        spec = specs_by_name.get(str(source_name), {})
        if str(spec.get("value_type") or "text") not in {"text", "list"}:
            continue
        columns = _matching_alias_columns(str(source_name), table_names, table_registry)
        if len(columns) != 1:
            continue
        table_name, column_name = columns[0]
        canonical = table_registry.get(table_name).canonical_value(column_name, value)  # type: ignore[union-attr]
        if canonical is not None:
            normalized[source_name] = canonical
    return normalized


def normalize_filter_bindings(
    params: dict[str, Any],
    filter_specs: list[dict[str, Any]],
    table_names: list[str],
    table_registry: TableRegistry,
    business_registry: BusinessTermRegistry,
    goal: str = "",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Normalize values and remove model-inferred object filters safely.

    A table/business-term alias such as ``VA`` identifies the selected data
    object; it is not automatically a value for that table's ``type`` field.
    If the alias is not a configured value for the matched field, the filter
    is discarded before SQL slots are created.
    """
    normalized = normalize_relative_filter_values(params, filter_specs, goal)
    normalized = normalize_filter_values(normalized, filter_specs, table_names, table_registry)
    kept_specs: list[dict[str, Any]] = []
    selected = set(table_names)
    object_aliases = {
        _compact(label): _compact(f"{label}交易")
        for term in business_registry.all_terms()
        if selected.intersection(term.candidate_tables)
        for label in [term.name, *term.aliases]
        if label
    }
    for spec in filter_specs:
        name = str(spec.get("name") or "")
        value = normalized.get(name)
        alias_columns = _matching_alias_columns(name, table_names, table_registry)
        original_value = params.get(name)
        compact_value = _compact(value) if isinstance(value, str) else ""
        compact_original = _compact(original_value) if isinstance(original_value, str) else ""
        object_key = compact_original if compact_original in object_aliases else compact_value
        is_object_alias = object_key in object_aliases
        is_object_phrase = is_object_alias and bool(alias_columns) and object_aliases[object_key] in _compact(goal)
        canonical_mismatch = is_object_alias and bool(alias_columns) and all(
            table_registry.get(table_name).canonical_value(column_name, value) is None  # type: ignore[union-attr]
            for table_name, column_name in alias_columns
        )
        if canonical_mismatch or is_object_phrase:
            normalized.pop(name, None)
            continue
        kept_specs.append(spec)
    return normalized, kept_specs


def _matching_alias_columns(
    source_name: str,
    table_names: list[str],
    table_registry: TableRegistry,
) -> list[tuple[str, str]]:
    source = _compact(source_name)
    matches: list[tuple[str, str]] = []
    for table_name in table_names:
        table = table_registry.get(table_name)
        if table is None:
            continue
        for column in table.columns:
            if not column.value_aliases:
                continue
            field_text = _compact(f"{column.name} {column.description} {' '.join(column.semantic_aliases)}")
            if source == _compact(column.name) or source in field_text or field_text in source:
                matches.append((table_name, column.name))
    return matches


def _compact(value: str) -> str:
    return "".join(value.casefold().split())
