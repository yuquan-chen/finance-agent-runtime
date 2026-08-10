from __future__ import annotations

from dataclasses import dataclass

from finance_agent.harness.plan_schema import Intent, QueryPlan
from finance_agent.metadata.catalog import Catalog
from finance_agent.metadata.policy import Policy


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]
    plan: QueryPlan | None = None


def validate_plan(plan: QueryPlan, visible_catalog: Catalog, policy: Policy) -> ValidationResult:
    errors: list[str] = []
    table = visible_catalog.table(plan.table)
    if table is None:
        errors.append(f"table is not visible or does not exist in catalog: {plan.table}")
        return ValidationResult(ok=False, errors=errors)

    if plan.intent.value not in table.allowed_intents:
        errors.append(f"intent {plan.intent.value} is not allowed for table {plan.table}")

    if plan.limit > policy.max_rows:
        errors.append(f"limit {plan.limit} exceeds max_rows {policy.max_rows}")

    columns = table.column_names
    referenced_fields: list[str] = []
    if plan.group_by:
        referenced_fields.append(plan.group_by)
    referenced_fields.extend(metric.field for metric in plan.metrics)
    referenced_fields.extend(filter_.field for filter_ in plan.filters)
    metric_aliases = {metric.alias for metric in plan.metrics if metric.alias}
    referenced_fields.extend(order.field for order in plan.order_by if order.field not in metric_aliases)

    for field in referenced_fields:
        if field not in columns:
            errors.append(f"field is not visible on table {plan.table}: {field}")
            continue
        column = table.get_column(field)
        if column and (column.sensitive or policy.is_sensitive_column_name(column.name)):
            errors.append(f"field is sensitive and cannot be used: {field}")

    if plan.intent in {Intent.latest_by_group, Intent.count_distinct, Intent.aggregate_by_group} and not plan.group_by:
        errors.append(f"intent {plan.intent.value} requires group_by")

    if plan.intent in {Intent.top_n, Intent.aggregate_by_group} and not plan.metrics:
        errors.append(f"intent {plan.intent.value} requires at least one metric")

    if plan.intent == Intent.latest_by_group and not plan.order_by:
        errors.append("latest_by_group requires order_by")

    return ValidationResult(ok=not errors, errors=errors, plan=plan if not errors else None)
