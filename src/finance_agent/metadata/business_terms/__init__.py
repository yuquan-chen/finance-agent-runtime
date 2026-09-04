"""业务术语自动发现包。

在此目录下创建 .py 文件，使用 @register_business_term 装饰器即可自动注册。

示例 —— my_terms.py:

    from finance_agent.metadata.business_registry import register_business_term

    @register_business_term(
        name="退款",
        description="退款类交易。",
        aliases=["refund", "退回"],
        candidate_tables=["card_transaction"],
        filters=[{"field": "type", "op": "=", "value": "refund"}],
    )
    def _():
        pass
"""
