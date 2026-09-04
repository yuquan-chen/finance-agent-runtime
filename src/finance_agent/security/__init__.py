"""Resource ownership and request identity primitives."""

from finance_agent.security.principal import DEFAULT_PRINCIPAL, Principal, principal_from_headers

__all__ = ["DEFAULT_PRINCIPAL", "Principal", "principal_from_headers"]
