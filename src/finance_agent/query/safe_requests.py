"""Allowlisted, parameterized query requests for the database test path.

The request contains a query identifier and values only. SQL lives in a
versioned server-side definition and is never accepted from the caller.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

ParameterType = Literal["text", "integer", "number", "boolean"]


class SafeQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    page: int = 1
    page_size: int = 20

    @field_validator("query_id")
    @classmethod
    def validate_query_id(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 128:
            raise ValueError("query_id must be 1-128 characters")
        if not all(char.isalnum() or char in {".", "_", "-"} for char in value):
            raise ValueError("query_id contains invalid characters")
        return value

    @field_validator("page")
    @classmethod
    def validate_page(cls, value: int) -> int:
        if isinstance(value, bool) or value < 1:
            raise ValueError("page must be at least 1")
        return value

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        if isinstance(value, bool) or value < 1 or value > 100:
            raise ValueError("page_size must be between 1 and 100")
        return value


class SafeQueryDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = ""
    sql: str
    allowed_params: dict[str, ParameterType] = Field(default_factory=dict)
    required_params: list[str] = Field(default_factory=list)
    max_page_size: int = 20

    @field_validator("max_page_size")
    @classmethod
    def validate_max_page_size(cls, value: int) -> int:
        if isinstance(value, bool) or value < 1 or value > 100:
            raise ValueError("max_page_size must be between 1 and 100")
        return value


class SafeQueryRegistry:
    def __init__(self, definitions: dict[str, SafeQueryDefinition]):
        self._definitions = definitions

    @classmethod
    def from_yaml(cls, path: Path) -> SafeQueryRegistry:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        definitions = {
            query_id: SafeQueryDefinition.model_validate(definition)
            for query_id, definition in (raw.get("queries") or {}).items()
        }
        if not definitions:
            raise ValueError("safe query registry must contain at least one query")
        return cls(definitions)

    def resolve(self, query_id: str) -> SafeQueryDefinition:
        definition = self._definitions.get(query_id)
        if definition is None:
            raise ValueError(f"query is not allowlisted: {query_id}")
        return definition

    def bind(self, request: SafeQueryRequest) -> tuple[SafeQueryDefinition, dict[str, Any]]:
        definition = self.resolve(request.query_id)
        unknown = set(request.params) - set(definition.allowed_params)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"query parameters are not allowlisted: {names}")
        missing = set(definition.required_params) - set(request.params)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"required query parameters are missing: {names}")

        params = dict(request.params)
        for name, kind in definition.allowed_params.items():
            value = params.get(name)
            if value is None:
                params[name] = None
                continue
            if kind == "text" and not isinstance(value, str):
                raise ValueError(f"query parameter {name} must be text")
            if kind == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
                raise ValueError(f"query parameter {name} must be an integer")
            if kind == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise ValueError(f"query parameter {name} must be a number")
            if kind == "boolean" and not isinstance(value, bool):
                raise ValueError(f"query parameter {name} must be boolean")

        if request.page_size > definition.max_page_size:
            raise ValueError(f"page_size cannot exceed {definition.max_page_size} for this query")
        params["page_size"] = request.page_size
        params["offset"] = (request.page - 1) * request.page_size
        return definition, params
