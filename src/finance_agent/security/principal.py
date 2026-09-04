from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass

_IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True)
class Principal:
    """The authenticated resource owner used by the API boundary.

    The current local runtime receives these values from request headers. A
    production auth proxy should overwrite the same headers after validating
    the caller rather than allowing arbitrary client supplied identities.
    """

    user_id: str
    workspace_id: str


DEFAULT_PRINCIPAL = Principal(user_id="local", workspace_id="local")


def _identity(value: str | None, fallback: str) -> str:
    candidate = (value or fallback).strip()
    if not _IDENTITY_PATTERN.fullmatch(candidate):
        raise ValueError("identity must be 1-128 ASCII characters: letters, digits, '.', '_', ':' or '-'")
    return candidate


def _decode_bearer(token: str, secret: str) -> Principal:
    parts = token.split(".")
    if len(parts) != 3 or not secret:
        raise ValueError("a signed bearer token is required")
    encoded_header, encoded_payload, encoded_signature = parts
    try:
        header = json.loads(
            base64.urlsafe_b64decode(encoded_header + "=" * (-len(encoded_header) % 4)).decode("utf-8")
        )
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error, UnicodeEncodeError) as exc:
        raise ValueError("invalid bearer token header") from exc
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise ValueError("unsupported bearer token algorithm")
    if header.get("typ") is not None and str(header["typ"]).upper() != "JWT":
        raise ValueError("invalid bearer token type")
    expected = base64.urlsafe_b64encode(
        hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    ).rstrip(b"=").decode("ascii")
    if not hmac.compare_digest(expected, encoded_signature):
        raise ValueError("invalid bearer token signature")
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4)).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError("invalid bearer token payload") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid bearer token payload")
    expires_at = payload.get("exp")
    if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)) or not math.isfinite(expires_at):
        raise ValueError("bearer token expiration is required")
    if expires_at <= time.time():
        raise ValueError("bearer token has expired")
    return Principal(
        user_id=_identity(payload.get("sub") or payload.get("user_id"), ""),
        workspace_id=_identity(payload.get("workspace_id"), ""),
    )


def principal_from_headers(
    headers: Mapping[str, str],
    *,
    auth_mode: str = "local",
    auth_secret: str = "",
) -> Principal:
    if auth_mode == "required":
        authorization = headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ValueError("Authorization: Bearer token is required")
        return _decode_bearer(token.strip(), auth_secret)
    if auth_mode not in {"local", "development"}:
        raise ValueError(f"unsupported AUTH_MODE: {auth_mode}")
    return Principal(
        user_id=_identity(headers.get("x-user-id"), DEFAULT_PRINCIPAL.user_id),
        workspace_id=_identity(headers.get("x-workspace-id"), DEFAULT_PRINCIPAL.workspace_id),
    )
