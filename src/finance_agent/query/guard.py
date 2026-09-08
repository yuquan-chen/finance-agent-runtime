from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from finance_agent.harness.method_validator import validate_method_draft
from finance_agent.metadata.catalog import Catalog
from finance_agent.metadata.policy import Policy
from finance_agent.operations.registry import OperationRegistry
from finance_agent.query.contracts import CompiledQuery, ValidationReport
from finance_agent.sandbox.mock_sandbox import run_mock_dry_run


class QueryGuard:
    """Single boundary for static SQL, authorization, and dry-run checks."""

    def __init__(
        self,
        visible_catalog: Catalog,
        policy: Policy,
        operation_registry: OperationRegistry,
        table_registry: Any = None,
    ) -> None:
        self.visible_catalog = visible_catalog
        self.policy = policy
        self.operation_registry = operation_registry
        self.table_registry = table_registry

    def validate(
        self,
        queries: Iterable[CompiledQuery],
        *,
        extra_tables: dict[str, list[dict[str, Any]]] | None = None,
    ) -> ValidationReport:
        compiled = list(queries)
        methods = [query.method for query in compiled]
        reviews = [
            validate_method_draft(
                method,
                self.visible_catalog,
                self.policy,
                self.operation_registry,
                self.table_registry,
            )
            for method in methods
        ]
        mock_results = [run_mock_dry_run(method, extra_tables=extra_tables) for method in methods]
        errors = [error for review in reviews for error in review.errors]
        errors.extend(error for result in mock_results for error in result.errors)
        warnings = [warning for review in reviews for warning in review.warnings]
        checks = [
            "readonly_sql",
            "visible_schema",
            "bound_parameters",
            "policy_fields",
            "mock_dry_run",
        ]
        return ValidationReport(
            status="passed" if not errors else "failed",
            allowed=not errors,
            errors=errors,
            warnings=warnings,
            checks=checks,
            harness_reviews=reviews,
            mock_results=mock_results,
        )
