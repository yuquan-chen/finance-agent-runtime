from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from finance_agent.harness.analysis_schema import MethodDraft, MockDryRunResult
from finance_agent.sandbox.mock_data import load_catalog_mock_data
from finance_agent.sandbox.runtime import run_method_in_sandbox


def build_simulated_card_transactions(row_count: int = 100) -> list[dict[str, Any]]:
    channels = ["visa", "mastercard", "amex", "unionpay", "virtual_card"]
    accounts = [f"acct_{index:03d}" for index in range(1, 21)]
    currencies = ["USD", "USD", "USD", "EUR", "GBP"]
    base_time = datetime(2026, 1, 1, 9, 0, 0)  # noqa: DTZ001 - deterministic fixture timestamp
    rows: list[dict[str, Any]] = []
    for index in range(row_count):
        status = _status_for_index(index)
        tx_type = "reversal" if status == "reversed" else ("refund" if index % 17 == 0 else "consumption")
        sign = -1 if tx_type in {"reversal", "refund"} else 1
        amount = sign * round(12.5 + ((index * 37) % 900) + ((index % 9) * 0.73), 2)
        transaction_at = base_time + timedelta(days=(index * 5) % 181, hours=(index * 7) % 24, minutes=(index * 11) % 60)
        rows.append(
            {
                "id": f"sim-tx-{index + 1:04d}",
                "id_no": index + 1,
                "card_channel": channels[index % len(channels)],
                "account_id": accounts[(index * 7) % len(accounts)],
                "card_id": f"card_{((index * 13) % 35) + 1:03d}",
                "status": status,
                "type": tx_type,
                "total_amount": amount,
                "settle_amount": round(amount * 0.998, 2),
                "origin_amount": amount,
                "currency": currencies[index % len(currencies)],
                "transaction_at": transaction_at.isoformat() + "+08:00",
                "complete_at": (transaction_at + timedelta(minutes=2 + (index % 8))).isoformat() + "+08:00",
                "created_at": (transaction_at - timedelta(minutes=1)).isoformat() + "+08:00",
            }
        )
    return rows


def _status_for_index(index: int) -> str:
    if index % 23 == 0:
        return "reversed"
    if index % 19 == 0:
        return "failed"
    if index % 11 == 0:
        return "pending"
    return "completed"


SIMULATED_REAL_CARD_TRANSACTIONS: list[dict[str, Any]] = build_simulated_card_transactions()

# 应用执行路径只使用测试环境快照。需要关系完整的合成数据时，测试应
# 显式调用 generate_mock_data()，不能让它隐式覆盖应用快照。
ALL_MOCK_DATA: dict[str, list[dict[str, Any]]] = load_catalog_mock_data()

# 模拟真实数据（用于测试）
SIMULATED_REAL_CARD_TRANSACTIONS: list[dict[str, Any]] = build_simulated_card_transactions()


def run_mock_dry_run(method: MethodDraft, extra_tables: dict[str, list[dict]] | None = None) -> MockDryRunResult:
    # 合并所有 mock 数据到 extra_tables
    all_tables = dict(ALL_MOCK_DATA)
    if extra_tables:
        all_tables.update(extra_tables)
    # 使用 card_transaction 表的数据作为主要数据
    card_txns = all_tables.get("card_transaction", [])
    return run_method_in_sandbox(method, card_txns, "MOCK_DATA", extra_tables=all_tables)


def run_simulated_real_execution(method: MethodDraft, extra_tables: dict[str, list[dict]] | None = None) -> MockDryRunResult:
    # 合并所有 mock 数据到 extra_tables
    all_tables = dict(ALL_MOCK_DATA)
    if extra_tables:
        all_tables.update(extra_tables)
    return run_method_in_sandbox(method, list(SIMULATED_REAL_CARD_TRANSACTIONS), "SIMULATED_REAL_CARD_TRANSACTIONS", extra_tables=all_tables)
