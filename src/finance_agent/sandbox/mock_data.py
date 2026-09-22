"""根据真实数据库 schema 生成 mock 数据。

为所有核心表生成符合业务逻辑的模拟数据，支持多表 JOIN 测试。
所有 UUID 字段使用 uuid5 生成确定性 UUID，确保外键一致性。
"""
from __future__ import annotations

# These fixtures intentionally use naive local datetimes and append +08:00 to
# serialized values so their generated output remains stable across hosts.
# ruff: noqa: DTZ001, DTZ005
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

CATALOG_MOCK_DATA_PATH = Path(__file__).resolve().parents[1] / "executor" / "mock_data.json"
CATALOG_MOCK_ROW_LIMIT = 20


def load_catalog_mock_data() -> dict[str, list[dict[str, Any]]]:
    """Load the bounded local test-environment snapshot when available.

    This is the application mock source. Synthetic relational fixtures from
    ``generate_mock_data`` are intentionally not merged here because they can
    invent entities that do not exist in the selected test snapshot.
    """
    if not CATALOG_MOCK_DATA_PATH.exists():
        return {}
    try:
        payload = json.loads(CATALOG_MOCK_DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(table_name): rows[:CATALOG_MOCK_ROW_LIMIT]
        for table_name, rows in payload.items()
        if isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
    }


def _mock_uuid(prefix: str, index: int) -> str:
    """生成确定性的 mock UUID（同一 prefix+index 总是产生相同 UUID）。"""
    seed = f"{prefix}:{index}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))


def generate_mock_data(
    row_count: int = 100,
    reference_time: datetime | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """生成所有表的 mock 数据。

    ``reference_time`` is injectable so relative-time tests stay deterministic;
    the default keeps local fixtures aligned with the current rolling window.
    """
    reference_time = _normalize_reference_time(reference_time)
    # 生成基础数据
    accounts = _generate_accounts(20)
    cards = _generate_cards(accounts, 35)
    balances = _generate_balances(accounts, 40)
    budgets = _generate_budgets(accounts, balances, 15)
    cdd_kyc = _generate_cdd_kyc(accounts, 25)
    cdd_kyb = _generate_cdd_kyb(accounts, 20)
    card_transactions = _generate_card_transactions(accounts, cards, row_count, reference_time)
    va_transactions = _generate_va_transactions(accounts, 80, reference_time)
    payout_transactions = _generate_payout_transactions(accounts, 60, reference_time)
    transactions = _generate_transactions(accounts, balances, 200, reference_time)

    # 生成新增的转账相关数据
    pay_transactions = _generate_pay_transactions(accounts, balances, transactions, 50, reference_time)
    funds_transfers = _generate_funds_transfers(accounts, balances, transactions, 30, reference_time)
    p2p_funds_transfers = _generate_p2p_funds_transfers(accounts, balances, transactions, 25, reference_time)
    funds_in = _generate_funds_in(accounts, balances, transactions, 35, reference_time)
    funds_out = _generate_funds_out(accounts, balances, transactions, 40, reference_time)
    account_transactions = _generate_account_transactions(accounts, cards, balances, transactions, 150, reference_time)

    return {
        "account": accounts,
        "card": cards,
        "balance": balances,
        "budget": budgets,
        "cdd_kyc": cdd_kyc,
        "cdd_kyb": cdd_kyb,
        "card_transaction": card_transactions,
        "va_transaction": va_transactions,
        "payout_transaction": payout_transactions,
        "transaction": transactions,
        "pay_transaction": pay_transactions,
        "funds_transfer": funds_transfers,
        "p2p_funds_transfer": p2p_funds_transfers,
        "funds_in": funds_in,
        "funds_out": funds_out,
        "account_transaction": account_transactions,
    }


def _normalize_reference_time(reference_time: datetime | None) -> datetime:
    """Return a naive local timestamp used by the fixture's +08:00 strings."""
    value = reference_time or datetime.now()
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value.replace(second=0, microsecond=0)


def _generate_accounts(count: int) -> list[dict[str, Any]]:
    """生成账户数据。"""
    statuses = ["active", "active", "active", "active", "ban", "deleted"]
    types = ["enterprise", "enterprise", "person", "person", "self_employed"]
    kyc_statuses = ["completed", "completed", "completed", "pending", "na"]
    sources = ["app", "website", "personal_invite", "agent_invite"]

    def _risk_level_from_score(score: float) -> str:
        """根据风险分数决定风险等级。"""
        if score >= 70:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"

    accounts = []
    for i in range(count):
        risk_score = round(10 + i * 3.7, 2)
        accounts.append({
            "id": _mock_uuid("account", i),
            "type": types[i % len(types)],
            "status": statuses[i % len(statuses)],
            "identifier_id": f"ID-{uuid.uuid4().hex[:8].upper()}",
            "legal_name": f"Company {i+1}" if types[i % len(types)] != "person" else f"Person {i+1}",
            "legal_name_en": f"Company {i+1}" if types[i % len(types)] != "person" else f"Person {i+1}",
            "kyc_status": kyc_statuses[i % len(kyc_statuses)],
            "aml_status": "success" if kyc_statuses[i % len(kyc_statuses)] == "completed" else "na",
            "card_kyb_status": kyc_statuses[i % len(kyc_statuses)],
            "cw_kyb_status": kyc_statuses[(i + 1) % len(kyc_statuses)],
            "va_kyb_status": kyc_statuses[(i + 2) % len(kyc_statuses)],
            "acquiring_kyb_status": kyc_statuses[(i + 3) % len(kyc_statuses)],
            "source": sources[i % len(sources)],
            "risk_level": _risk_level_from_score(risk_score),
            "risk_score": risk_score,
            "is_str": i % 15 == 0,
            "is_monitored": i % 10 == 0,
            "last_login_time": (datetime(2026, 7, 1) + timedelta(days=i)).isoformat() + "+08:00",
            "created_at": (datetime(2025, 1, 1) + timedelta(days=i * 10)).isoformat() + "+08:00",
        })
    return accounts


def _generate_cards(accounts: list[dict], count: int) -> list[dict[str, Any]]:
    """生成卡数据。"""
    channels = ["c_001_prepaid", "c_002_prepaid", "c_003_ota_prepaid", "c_005_prepaid", "c_007_prepaid", "c_009_prepaid"]
    statuses = ["active", "active", "active", "frozen", "opening", "expired"]
    types = ["virtual", "virtual", "physical"]
    currencies = ["USD", "USD", "USD", "EUR", "GBP", "HKD"]

    cards = []
    for i in range(count):
        account = accounts[i % len(accounts)]
        cards.append({
            "id": _mock_uuid("card", i),
            "account_id": account["id"],
            "card_channel": channels[i % len(channels)],
            "status": statuses[i % len(statuses)],
            "type": types[i % len(types)],
            "currency": currencies[i % len(currencies)],
            "last4": f"{1000 + i % 9000:04d}",
            "first8": f"{40000000 + i % 10000000:08d}",
            "label": f"Card {i+1}",
            "first_name": account["legal_name"].split()[-1] if account["legal_name"] else "",
            "last_name": account["legal_name"].split()[0] if account["legal_name"] else "",
            "created_at": (datetime(2025, 6, 1) + timedelta(days=i * 5)).isoformat() + "+08:00",
        })
    return cards


def _generate_balances(accounts: list[dict], count: int) -> list[dict[str, Any]]:
    """生成余额数据。"""
    types = ["ca", "card", "va", "budget", "commission"]
    currencies = ["USD", "USD", "USD", "EUR", "GBP"]

    balances = []
    for i in range(count):
        account = accounts[i % len(accounts)]
        balances.append({
            "id": _mock_uuid("balance", i),
            "account_id": account["id"],
            "currency": currencies[i % len(currencies)],
            "available": round(1000 + i * 150.5, 2),
            "pending": round(i * 25.3, 2),
            "frozen": round(i * 10.1, 2) if i % 5 == 0 else 0,
            "type": types[i % len(types)],
            "sub_type": "account",
            "status": "active",
            "created_at": (datetime(2025, 3, 1) + timedelta(days=i * 8)).isoformat() + "+08:00",
        })
    return balances


def _generate_budgets(accounts: list[dict], balances: list[dict], count: int) -> list[dict[str, Any]]:
    """生成预算数据。"""
    statuses = ["active", "active", "active", "frozen", "deleted"]

    budgets = []
    for i in range(count):
        account = accounts[i % len(accounts)]
        balance = balances[i % len(balances)]
        budgets.append({
            "id": _mock_uuid("budget", i),
            "account_id": account["id"],
            "balance_id": balance["id"],
            "name": f"Budget {i+1}",
            "status": statuses[i % len(statuses)],
            "total_limit": round(5000 + i * 1000, 2),
            "created_at": (datetime(2025, 4, 1) + timedelta(days=i * 12)).isoformat() + "+08:00",
        })
    return budgets


def _generate_cdd_kyc(accounts: list[dict], count: int) -> list[dict[str, Any]]:
    """生成 KYC 数据。"""
    statuses = ["completed", "completed", "pending", "na"]
    types = ["business", "person"]

    kyc_records = []
    for i in range(count):
        account = accounts[i % len(accounts)]
        kyc_records.append({
            "id": _mock_uuid("kyc", i),
            "account_id": account["id"],
            "type": types[i % len(types)],
            "status": statuses[i % len(statuses)],
            "is_last": True,
            "vendor": "sumsub" if i % 3 == 0 else "didit",
            "submit_time": (datetime(2025, 2, 1) + timedelta(days=i * 15)).isoformat() + "+08:00",
            "review_time": (datetime(2025, 2, 3) + timedelta(days=i * 15)).isoformat() + "+08:00" if statuses[i % len(statuses)] == "completed" else None,
            "created_at": (datetime(2025, 2, 1) + timedelta(days=i * 15)).isoformat() + "+08:00",
        })
    return kyc_records


def _generate_cdd_kyb(accounts: list[dict], count: int) -> list[dict[str, Any]]:
    """生成 KYB 数据。"""
    statuses = ["completed", "completed", "pending", "na"]
    types = ["business", "enterprise"]

    kyb_records = []
    for i in range(count):
        account = accounts[i % len(accounts)]
        kyb_records.append({
            "id": _mock_uuid("kyb", i),
            "account_id": account["id"],
            "type": types[i % len(types)],
            "status": statuses[i % len(statuses)],
            "is_last": True,
            "submit_time": (datetime(2025, 3, 1) + timedelta(days=i * 20)).isoformat() + "+08:00",
            "review_time": (datetime(2025, 3, 5) + timedelta(days=i * 20)).isoformat() + "+08:00" if statuses[i % len(statuses)] == "completed" else None,
            "created_at": (datetime(2025, 3, 1) + timedelta(days=i * 20)).isoformat() + "+08:00",
        })
    return kyb_records


def _generate_card_transactions(
    accounts: list[dict], cards: list[dict], count: int, reference_time: datetime
) -> list[dict[str, Any]]:
    """生成卡交易数据。"""
    statuses = ["completed", "completed", "completed", "completed", "completed",
                "completed", "completed", "completed", "pending", "failed", "reversed"]
    types = ["consumption", "consumption", "consumption", "consumption", "consumption",
             "refund", "refund", "reversal", "settlement_debit", "auth_fee"]
    currencies = ["USD", "USD", "USD", "EUR", "GBP", "HKD"]
    channels = ["c_001_prepaid", "c_002_prepaid", "c_003_ota_prepaid", "c_005_prepaid", "c_007_prepaid"]

    transactions = []

    for i in range(count):
        account = accounts[i % len(accounts)]
        card = cards[i % len(cards)]
        status = statuses[i % len(statuses)]
        tx_type = types[i % len(types)]
        sign = -1 if tx_type in ("refund", "reversal") else 1
        amount = sign * round(15.0 + ((i * 37) % 800) + ((i % 7) * 0.85), 2)
        tx_time = reference_time - timedelta(days=(i * 3) % 181, hours=(i * 5) % 24, minutes=(i * 7) % 60)

        transactions.append({
            "id": _mock_uuid("card_tx", i),
            "id_no": 1000000 + i,
            "account_id": account["id"],
            "card_id": card["id"],
            "card_channel": channels[i % len(channels)],
            "type": tx_type,
            "status": status,
            "process_status": status,
            "total_amount": amount,
            "settle_amount": round(amount * 0.998, 2),
            "origin_amount": amount,
            "fee": round(abs(amount) * 0.02, 2),
            "currency": currencies[i % len(currencies)],
            "origin_currency": currencies[i % len(currencies)],
            "local_trx_amount": amount,
            "local_trx_currency": currencies[i % len(currencies)],
            "order_num": f"ORD-{uuid.uuid4().hex[:12].upper()}",
            "transaction_at": tx_time.isoformat() + "+08:00",
            "complete_at": (tx_time + timedelta(minutes=2 + i % 10)).isoformat() + "+08:00" if status == "completed" else None,
            "channel_complete_at": (tx_time + timedelta(minutes=1 + i % 5)).isoformat() + "+08:00" if status == "completed" else None,
            "created_at": (tx_time - timedelta(minutes=1)).isoformat() + "+08:00",
        })

    return transactions


def _generate_va_transactions(
    accounts: list[dict], count: int, reference_time: datetime
) -> list[dict[str, Any]]:
    """生成 VA 交易数据。"""
    statuses = ["completed", "completed", "completed", "pending", "failed"]
    types = ["deposit", "deposit", "payment", "refund", "conversion"]
    channels = ["va_001", "va_002", "va_005", "va_007", "va_009"]
    currencies = ["USD", "USD", "EUR", "GBP"]

    transactions = []

    for i in range(count):
        account = accounts[i % len(accounts)]
        status = statuses[i % len(statuses)]
        tx_type = types[i % len(types)]
        sign = -1 if tx_type == "refund" else 1
        amount = sign * round(100 + ((i * 41) % 5000) + ((i % 5) * 0.5), 2)
        tx_time = reference_time - timedelta(days=(i * 4) % 181, hours=(i * 3) % 24)

        transactions.append({
            "id": _mock_uuid("va_tx", i),
            "id_no": 2000000 + i,
            "account_id": account["id"],
            "channel": channels[i % len(channels)],
            "type": tx_type,
            "status": status,
            "process_status": status,
            "total_amount": amount,
            "settle_amount": round(amount * 0.995, 2),
            "origin_amount": amount,
            "fee": round(abs(amount) * 0.015, 2),
            "currency": currencies[i % len(currencies)],
            "settle_currency": "USD",
            "origin_currency": currencies[i % len(currencies)],
            "transaction_at": tx_time.isoformat() + "+08:00",
            "complete_at": (tx_time + timedelta(minutes=5 + i % 15)).isoformat() + "+08:00" if status == "completed" else None,
            "created_at": (tx_time - timedelta(minutes=2)).isoformat() + "+08:00",
        })

    return transactions


def _generate_payout_transactions(
    accounts: list[dict], count: int, reference_time: datetime
) -> list[dict[str, Any]]:
    """生成付款交易数据。"""
    statuses = ["completed", "completed", "pending", "failed", "pending_review"]
    business_sources = ["va", "va", "cw", "ca"]
    payout_channels = ["bank_wire", "bank_wire", "swift", "local_transfer"]
    payee_currencies = ["USD", "EUR", "GBP", "HKD"]

    transactions = []

    for i in range(count):
        account = accounts[i % len(accounts)]
        status = statuses[i % len(statuses)]
        amount = round(500 + ((i * 53) % 10000) + ((i % 3) * 0.25), 2)
        tx_time = reference_time - timedelta(days=(i * 6) % 181, hours=(i * 4) % 24)

        transactions.append({
            "id": _mock_uuid("payout_tx", i),
            "id_no": 3000000 + i,
            "account_id": account["id"],
            "payee_id": _mock_uuid("payee", i % 15),
            "amount": amount,
            "payer_currency": "USD",
            "payee_currency": payee_currencies[i % len(payee_currencies)],
            "business_source": business_sources[i % len(business_sources)],
            "payout_channel": payout_channels[i % len(payout_channels)],
            "status": status,
            "process_status": status,
            "progress_status": "success" if status == "completed" else "pending",
            "comment": f"Payout {i+1}",
            "purpose": "business_payment",
            "base_fee": round(amount * 0.01, 2),
            "rate": 1.0,
            "complete_at": (tx_time + timedelta(hours=2 + i % 24)).isoformat() + "+08:00" if status == "completed" else None,
            "created_at": tx_time.isoformat() + "+08:00",
        })

    return transactions


def _generate_transactions(
    accounts: list[dict], balances: list[dict], count: int, reference_time: datetime
) -> list[dict[str, Any]]:
    """生成通用交易流水（余额变动）。"""
    types = ["card_debit", "card_refund", "account_recharge", "account_transfer_in",
             "account_transfer_out", "va_deposit", "va_payout", "commission_withdrawal"]
    statuses = ["completed", "completed", "completed", "pending", "failed"]

    transactions = []

    for i in range(count):
        account = accounts[i % len(accounts)]
        balance = balances[i % len(balances)]
        tx_type = types[i % len(types)]
        status = statuses[i % len(statuses)]
        amount = round(100 + ((i * 29) % 2000), 2)

        transactions.append({
            "id": _mock_uuid("trx", i),
            "account_id": account["id"],
            "balance_id": balance["id"],
            "type": tx_type,
            "sub_type": "na",
            "status": status,
            "amount": amount,
            "fee": round(amount * 0.01, 2),
            "currency": "USD",
            "before_balance": round(5000 + i * 100, 2),
            "after_balance": round(5000 + i * 100 - amount, 2) if "debit" in tx_type or "payout" in tx_type else round(5000 + i * 100 + amount, 2),
            "operation_type": tx_type,
            "transaction_at": (reference_time - timedelta(days=(i * 2) % 181)).isoformat() + "+08:00",
            "relation_id": _mock_uuid("relation", i),
            "created_at": (reference_time - timedelta(days=(i * 2) % 181)).isoformat() + "+08:00",
        })

    return transactions


def _generate_pay_transactions(
    accounts: list[dict],
    balances: list[dict],
    transactions: list[dict],
    count: int,
    reference_time: datetime,
) -> list[dict[str, Any]]:
    """生成支付交易数据。"""
    statuses = ["completed", "completed", "completed", "pending", "failed"]
    types = ["payment", "payment", "payment", "refund", "payment"]
    pay_channels = ["bank_card", "bank_card", "crypto", "bank_transfer", "e_wallet"]
    currencies = ["USD", "USD", "EUR", "GBP", "HKD"]

    pay_transactions = []

    for i in range(count):
        account = accounts[i % len(accounts)]
        balance = balances[i % len(balances)]
        trx = transactions[i % len(transactions)]
        status = statuses[i % len(statuses)]
        tx_type = types[i % len(types)]
        amount = round(200 + ((i * 47) % 5000) + ((i % 5) * 0.5), 2)
        tx_time = reference_time - timedelta(days=(i * 3) % 181, hours=(i * 7) % 24)

        pay_transactions.append({
            "id": _mock_uuid("pay_tx", i),
            "id_no": 4000000 + i,
            "account_id": account["id"],
            "amount": amount,
            "fee": round(amount * 0.02, 2),
            "total_amount": round(amount * 1.02, 2),
            "usd_rate": 1.0,
            "usd_amount": amount,
            "usd_fee_amount": round(amount * 0.02, 2),
            "currency": currencies[i % len(currencies)],
            "pay_currency": currencies[i % len(currencies)],
            "status": status,
            "process_status": status,
            "settle_status": "settled" if status == "completed" else "pending",
            "pay_channel": pay_channels[i % len(pay_channels)],
            "type": tx_type,
            "origin_pay_order_id": _mock_uuid("pay_tx", i - 1) if tx_type == "refund" and i > 0 else None,
            "call_id": f"call-{uuid.uuid4().hex[:8]}",
            "balance_id": balance["id"],
            "transaction_id": trx["id"],
            "source_id": _mock_uuid("source", i % 10),
            "success_url": "https://example.com/success",
            "failure_url": "https://example.com/failure",
            "extra_data": json.dumps({"source": "web", "device": "mobile"}),
            "raw_data": json.dumps({"gateway_response": "success", "transaction_id": f"gw-{i:06d}"}),
            "pay_channel_currency_id": None,
            "payer": _mock_uuid("payer", i % 15),
            "wait_amount_on_chain": None,
            "done_amount_on_chain": None,
            "address": None,
            "receive_address": None,
            "pay_type": "online",
            "expire_time": int((tx_time + timedelta(hours=24)).timestamp()),
            "customer_notes": f"Payment {i+1}",
            # PayTransaction 继承 TrxBaseV2 -> Base；mock 数据也必须保留
            # 继承字段，否则 SQL 沙箱会按行数据建临时表并丢失 created_at。
            "transaction_at": tx_time.isoformat() + "+08:00",
            "completed_at": (tx_time + timedelta(minutes=3 + i % 12)).isoformat() + "+08:00"
            if status == "completed" else None,
            "batch_id": f"pay-batch-{i // 10 + 1}",
            "created_at": (tx_time - timedelta(minutes=1)).isoformat() + "+08:00",
            "update_at": tx_time.isoformat() + "+08:00",
            "delete_at": None,
            "version": 1,
            "remarks": None,
        })

    return pay_transactions


def _generate_funds_transfers(
    accounts: list[dict],
    balances: list[dict],
    transactions: list[dict],
    count: int,
    reference_time: datetime,
) -> list[dict[str, Any]]:
    """生成内部转账数据。"""
    statuses = ["completed", "completed", "completed", "pending", "failed"]
    from_currencies = ["USD", "USD", "EUR", "GBP", "HKD"]
    to_currencies = ["EUR", "GBP", "USD", "USD", "USD"]
    business_types = ["exchange", "exchange", "transfer", "exchange", "transfer"]

    transfers = []

    for i in range(count):
        account = accounts[i % len(accounts)]
        from_balance = balances[i % len(balances)]
        to_balance = balances[(i + 10) % len(balances)]
        out_trx = transactions[(i * 2) % len(transactions)]
        in_trx = transactions[(i * 2 + 1) % len(transactions)]
        status = statuses[i % len(statuses)]
        transfers.append({
            "id": _mock_uuid("funds_transfer", i),
            "id_no": 5000000 + i,
            "account_id": account["id"],
            "from_currency": from_currencies[i % len(from_currencies)],
            "to_currency": to_currencies[i % len(to_currencies)],
            "fee_currency": "USD",
            "from_balance_id": from_balance["id"],
            "from_balance_type": from_balance["type"],
            "business_type": business_types[i % len(business_types)],
            "external_id": f"ext-{uuid.uuid4().hex[:8]}",
            "to_balance_id": to_balance["id"],
            "to_balance_type": to_balance["type"],
            "status": status,
            "out_transaction_id": out_trx["id"],
            "out_trace_transaction_id": None,
            "in_transaction_id": in_trx["id"],
            "in_trace_transaction_id": None,
            "fx_id": _mock_uuid("fx", i),
            "process_status": status,
        })

    return transfers


def _generate_p2p_funds_transfers(
    accounts: list[dict],
    balances: list[dict],
    transactions: list[dict],
    count: int,
    reference_time: datetime,
) -> list[dict[str, Any]]:
    """生成 P2P 转账数据。"""
    statuses = ["completed", "completed", "completed", "pending", "failed"]
    from_currencies = ["USD", "USD", "EUR", "GBP", "HKD"]
    to_currencies = ["USD", "EUR", "USD", "USD", "USD"]
    business_types = ["p2p_transfer", "p2p_transfer", "p2p_payment", "p2p_transfer", "p2p_payment"]

    transfers = []

    for i in range(count):
        from_account = accounts[i % len(accounts)]
        to_account = accounts[(i + 5) % len(accounts)]
        from_balance = balances[i % len(balances)]
        to_balance = balances[(i + 15) % len(balances)]
        out_trx = transactions[(i * 2) % len(transactions)]
        in_trx = transactions[(i * 2 + 1) % len(transactions)]
        status = statuses[i % len(statuses)]
        transfers.append({
            "id": _mock_uuid("p2p_transfer", i),
            "id_no": 6000000 + i,
            "account_id": from_account["id"],
            "to_account_id": to_account["id"],
            "from_currency": from_currencies[i % len(from_currencies)],
            "to_currency": to_currencies[i % len(to_currencies)],
            "fee_currency": "USD",
            "from_balance_id": from_balance["id"],
            "from_balance_type": from_balance["type"],
            "business_type": business_types[i % len(business_types)],
            "external_id": f"ext-{uuid.uuid4().hex[:8]}",
            "to_balance_id": to_balance["id"],
            "to_balance_type": to_balance["type"],
            "status": status,
            "out_transaction_id": out_trx["id"],
            "out_trace_transaction_id": None,
            "in_transaction_id": in_trx["id"],
            "in_trace_transaction_id": None,
            "fx_id": _mock_uuid("fx", i),
            "process_status": status,
        })

    return transfers


def _generate_funds_in(
    accounts: list[dict],
    balances: list[dict],
    transactions: list[dict],
    count: int,
    reference_time: datetime,
) -> list[dict[str, Any]]:
    """生成入金数据。"""
    statuses = ["completed", "completed", "completed", "pending", "failed"]
    to_currencies = ["USD", "USD", "EUR", "GBP", "HKD"]
    business_types = ["deposit", "deposit", "top_up", "deposit", "top_up"]

    funds_in = []

    for i in range(count):
        account = accounts[i % len(accounts)]
        balance = balances[i % len(balances)]
        trx = transactions[i % len(transactions)]
        status = statuses[i % len(statuses)]
        funds_in.append({
            "id": _mock_uuid("funds_in", i),
            "id_no": 7000000 + i,
            "account_id": account["id"],
            "to_currency": to_currencies[i % len(to_currencies)],
            "fee_currency": "USD",
            "to_balance_id": balance["id"],
            "to_balance_type": balance["type"],
            "business_type": business_types[i % len(business_types)],
            "external_id": f"ext-{uuid.uuid4().hex[:8]}",
            "status": status,
            "in_transaction_id": trx["id"],
            "in_trace_transaction_id": None,
            "process_status": status,
        })

    return funds_in


def _generate_funds_out(
    accounts: list[dict],
    balances: list[dict],
    transactions: list[dict],
    count: int,
    reference_time: datetime,
) -> list[dict[str, Any]]:
    """生成出金数据。"""
    statuses = ["completed", "completed", "completed", "pending", "failed"]
    from_currencies = ["USD", "USD", "EUR", "GBP", "HKD"]
    to_currencies = ["EUR", "GBP", "USD", "USD", "USD"]
    business_types = ["withdrawal", "withdrawal", "payout", "withdrawal", "payout"]

    funds_out = []

    for i in range(count):
        account = accounts[i % len(accounts)]
        balance = balances[i % len(balances)]
        trx = transactions[i % len(transactions)]
        status = statuses[i % len(statuses)]
        funds_out.append({
            "id": _mock_uuid("funds_out", i),
            "id_no": 8000000 + i,
            "account_id": account["id"],
            "from_currency": from_currencies[i % len(from_currencies)],
            "to_currency": to_currencies[i % len(to_currencies)],
            "fee_currency": "USD",
            "from_balance_id": balance["id"],
            "from_balance_type": balance["type"],
            "business_type": business_types[i % len(business_types)],
            "external_id": f"ext-{uuid.uuid4().hex[:8]}",
            "status": status,
            "out_transaction_id": trx["id"],
            "out_trace_transaction_id": None,
            "fx_id": _mock_uuid("fx", i),
            "process_status": status,
        })

    return funds_out


def _generate_account_transactions(
    accounts: list[dict],
    cards: list[dict],
    balances: list[dict],
    transactions: list[dict],
    count: int,
    reference_time: datetime,
) -> list[dict[str, Any]]:
    """生成账户交易数据。"""
    statuses = ["completed", "completed", "completed", "pending", "failed"]
    types = ["card_payment", "card_refund", "transfer_in", "transfer_out", "payout"]
    actions = ["debit", "credit", "debit", "credit", "debit"]
    currencies = ["USD", "USD", "EUR", "GBP", "HKD"]
    tx_sources = ["card", "card", "transfer", "transfer", "payout"]

    account_transactions = []

    for i in range(count):
        account = accounts[i % len(accounts)]
        card = cards[i % len(cards)]
        balance = balances[i % len(balances)]
        trx = transactions[i % len(transactions)]
        status = statuses[i % len(statuses)]
        tx_type = types[i % len(types)]
        action = actions[i % len(actions)]
        amount = round(50 + ((i * 37) % 2000) + ((i % 7) * 0.5), 2)
        account_transactions.append({
            "id": _mock_uuid("acct_tx", i),
            "id_no": 9000000 + i,
            "account_id": account["id"],
            "order_num": f"ORD-{uuid.uuid4().hex[:8].upper()}",
            "balance_id": balance["id"],
            "source_id": _mock_uuid("source", i % 10),
            "transaction_id": trx["id"],
            "card_id": card["id"],
            "currency": currencies[i % len(currencies)],
            "transaction_currency": currencies[i % len(currencies)],
            "transaction_amount": amount,
            "fx_rate": 1.0,
            "fee": round(amount * 0.02, 2),
            "amount": round(amount * 0.98, 2) if action == "debit" else round(amount * 1.02, 2),
            "type": tx_type,
            "action": action,
            "status": status,
            "process_status": status,
            "tx_source": tx_sources[i % len(tx_sources)],
            "call_id": f"call-{uuid.uuid4().hex[:8]}",
            "customer_notes": f"Transaction {i+1}",
            "reference": f"REF-{i+1:06d}",
        })

    return account_transactions
