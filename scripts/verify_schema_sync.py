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


def verify(entity_root: Path) -> list[str]:
    registry = get_default_table_registry()
    errors: list[str] = []
    entity_count = 0

    for entity_path in sorted(entity_root.rglob("*.repo.ts")):
        parsed = parse_typeorm_entity(entity_path)
        if not parsed:
            continue
        entity_count += 1
        table_name = parsed["table_name"]
        mapped = registry.get(table_name)
        if not mapped:
            errors.append(f"{table_name}: missing generated mapping")
            continue

        source_columns = {column["name"] for column in parsed["columns"]}
        mapped_columns = mapped.column_names
        missing = sorted(source_columns - mapped_columns)
        stale = sorted(mapped_columns - source_columns)
        if missing or stale:
            details = []
            if missing:
                details.append(f"missing={','.join(missing)}")
            if stale:
                details.append(f"stale={','.join(stale)}")
            errors.append(f"{table_name}: {'; '.join(details)}")

    if not entity_count:
        errors.append(f"no TypeORM entities found under {entity_root}")
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
