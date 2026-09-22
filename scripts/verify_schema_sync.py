#!/usr/bin/env python3
"""Check that generated TableRegistry metadata matches upstream TypeORM entities.

Usage:
  python scripts/verify_schema_sync.py \
    --from-entity /path/to/wavepool-core/src/repository
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from extract_schema import parse_typeorm_entity

from finance_agent.metadata.table_registry import get_default_table_registry

# These are the business-critical mappings exercised by the current test data and
# recent production-like queries.  The full source/entity comparison below remains
# the authority; these anchors make regressions visible with a short, readable error.
REQUIRED_BUSINESS_COLUMNS = {
    "account": {
        "id": "uuid",
        "legal_name": "text",
        "legal_name_en": "text",
        "created_at": "timestamptz",
    },
    "payout_transaction": {
        "account_id": "uuid",
        "amount": "numeric",
        "status": "varchar",
        "complete_at": "timestamptz",
        "created_at": "timestamptz",
    },
    "card_transaction": {
        "account_id": "uuid",
        "status": "varchar",
        "total_amount": "numeric",
        "settle_amount": "numeric",
        "transaction_at": "timestamptz",
        "created_at": "timestamptz",
    },
}


def _verify_business_anchors(registry) -> list[str]:
    errors: list[str] = []
    for table_name, expected_columns in REQUIRED_BUSINESS_COLUMNS.items():
        table = registry.get(table_name)
        if table is None:
            errors.append(f"{table_name}: missing required business table")
            continue
        for column_name, expected_type in expected_columns.items():
            column = table.get_column(column_name)
            if column is None:
                errors.append(f"{table_name}: missing required business column {column_name}")
            elif column.type != expected_type:
                errors.append(
                    f"{table_name}.{column_name}: expected type={expected_type}, mapped={column.type}"
                )
    return errors


def verify(entity_root: Path) -> list[str]:
    registry = get_default_table_registry()
    errors: list[str] = _verify_business_anchors(registry)
    parsed_entities: dict[str, dict] = {}

    for entity_path in sorted(entity_root.rglob("*.repo.ts")):
        parsed = parse_typeorm_entity(entity_path)
        if not parsed:
            continue
        table_name = str(parsed["table_name"])
        if table_name in parsed_entities:
            errors.append(f"{table_name}: duplicate source entity mapping")
            continue
        parsed_entities[table_name] = parsed

    if not parsed_entities:
        errors.append(f"no TypeORM entities found under {entity_root}")
        return errors

    source_tables = set(parsed_entities)
    mapped_tables = set(registry.names())
    missing_tables = sorted(source_tables - mapped_tables)
    stale_tables = sorted(mapped_tables - source_tables)
    if missing_tables:
        errors.append(f"missing generated tables: {','.join(missing_tables)}")
    if stale_tables:
        errors.append(f"stale generated tables: {','.join(stale_tables)}")

    for table_name, parsed in sorted(parsed_entities.items()):
        mapped = registry.get(table_name)
        if not mapped:
            continue

        source_columns = {column["name"]: column for column in parsed["columns"]}
        mapped_columns = {column.name: column for column in mapped.columns}
        missing = sorted(set(source_columns) - set(mapped_columns))
        stale = sorted(set(mapped_columns) - set(source_columns))
        type_mismatches = []
        for column_name in sorted(set(source_columns) & set(mapped_columns)):
            source_column = source_columns[column_name]
            mapped_column = mapped_columns[column_name]
            if source_column.get("type", "text") != mapped_column.type:
                type_mismatches.append(
                    f"{column_name} (source={source_column.get('type', 'text')}, mapped={mapped_column.type})"
                )
            if bool(source_column.get("nullable", True)) != bool(mapped_column.nullable):
                type_mismatches.append(
                    f"{column_name}.nullable (source={source_column.get('nullable', True)}, mapped={mapped_column.nullable})"
                )

        if missing or stale or type_mismatches:
            details = []
            if missing:
                details.append(f"missing={','.join(missing)}")
            if stale:
                details.append(f"stale={','.join(stale)}")
            if type_mismatches:
                details.append(f"metadata_mismatch={';'.join(type_mismatches)}")
            errors.append(f"{table_name}: {'; '.join(details)}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="verify TypeORM schema extraction is in sync")
    parser.add_argument("--from-entity", required=True, type=Path, help="upstream repository directory")
    args = parser.parse_args()

    if not args.from_entity.is_dir():
        raise SystemExit(f"entity directory does not exist: {args.from_entity}")

    errors = verify(args.from_entity)
    if errors:
        print("Schema mapping is out of sync:")
        for error in errors:
            print(f"  - {error}")
        raise SystemExit(1)

    print("Schema mapping is in sync.")


if __name__ == "__main__":
    main()
