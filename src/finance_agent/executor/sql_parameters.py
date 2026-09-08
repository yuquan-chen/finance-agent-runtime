"""Shared SQL template normalization for every SQL execution backend."""
from __future__ import annotations

import re
from typing import Any


def normalize_sql_template(
    sql: str,
    params: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Apply user-facing parameter semantics without changing bound values.

    Both the sandbox and direct database executor must interpret customer-name
    filters and fuzzy text parameters identically. Placeholder conversion for
    a specific driver remains in that driver's executor.
    """
    prepared = sql.strip().rstrip(";")

    # Customer names are identifiers, not free-text search terms. Keep an
    # equality filter exact while making it case-insensitive and tolerant of
    # whitespace differences; a fuzzy match must be requested explicitly with
    # ILIKE in the planned SQL.
    prepared = re.sub(
        r"\b((?:[a-zA-Z_][a-zA-Z0-9_]*\.)?legal_name(?:_en)?)\s*=\s*:([a-zA-Z_][a-zA-Z0-9_]*)",
        r"LOWER(regexp_replace(\1, '\\s+', '', 'g')) = LOWER(regexp_replace(:\2, '\\s+', '', 'g'))",
        prepared,
        flags=re.IGNORECASE,
    )
    prepared = re.sub(
        r"\b((?:[a-zA-Z_][a-zA-Z0-9_]*\.)?legal_name(?:_en)?)\s+ILIKE\s+:([a-zA-Z_][a-zA-Z0-9_]*)",
        r"(\1 ILIKE :\2 OR regexp_replace(\1, '\\s+', '', 'g') ILIKE regexp_replace(:\2, '\\s+', '', 'g'))",
        prepared,
        flags=re.IGNORECASE,
    )

    fuzzy_parameter_names = set(
        re.findall(r"\bILIKE\s+:([a-zA-Z_][a-zA-Z0-9_]*)", prepared, re.IGNORECASE)
    )
    prepared_params = dict(params or {})
    for key in fuzzy_parameter_names:
        value = prepared_params.get(key)
        if not isinstance(value, str):
            continue
        value = value.strip()
        if "%" not in value and "_" not in value:
            prepared_params[key] = f"%{value}%"

    return prepared, prepared_params
