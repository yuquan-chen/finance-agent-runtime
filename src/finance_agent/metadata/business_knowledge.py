"""Structured business knowledge built from the table and term registries.

This module is deliberately independent from the graph runtime.  It provides
the mapping and disclosure contract that a router or an LLM can use later:

    table index -> selected table fields -> selected field details/relations

    Business terms resolve to tables first.  Fields are only disclosed after a
    table has been selected and are always qualified as ``table.field``.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from finance_agent.metadata.business_registry import BusinessTerm, BusinessTermRegistry
from finance_agent.metadata.table_registry import TableRegistry

DisclosureLevel = Literal["index", "fields", "detail"]


class FieldMapping(BaseModel):
    """A field with its owning table made explicit."""

    table: str
    field: str
    qualified_name: str
    type: str
    description: str = ""
    sensitive: bool = False


class TableMapping(BaseModel):
    """The table-level entry shown at the first disclosure level."""

    table: str
    description: str = ""
    field_count: int = 0
    relationship_count: int = 0


class RelationshipMapping(BaseModel):
    """A relationship whose source field is also fully qualified."""

    from_field: str
    to: str
    type: str


class BusinessTermMapping(BaseModel):
    """A configured business term and the tables it resolves to."""

    name: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    candidate_tables: list[str] = Field(default_factory=list)
    resolved_tables: list[str] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)


class BusinessKnowledgeDisclosure(BaseModel):
    """A bounded metadata payload for one disclosure level."""

    level: DisclosureLevel
    tables: list[TableMapping] = Field(default_factory=list)
    fields: list[FieldMapping] = Field(default_factory=list)
    relationships: list[RelationshipMapping] = Field(default_factory=list)
    business_terms: list[BusinessTermMapping] = Field(default_factory=list)


class BusinessKnowledge:
    """Resolve and disclose table/field knowledge without touching data.

    The class indexes every registered field once.  It does not tokenize user
    text or contain field-name heuristics.  A future LLM/router can first
    choose a term or table from the index and then ask for a narrower level.
    """

    def __init__(self, table_registry: TableRegistry, business_registry: BusinessTermRegistry):
        self.table_registry = table_registry
        self.business_registry = business_registry
        self._tables = {table.name: table for table in table_registry.all_tables()}
        self._fields = {
            f"{table.name}.{column.name}": FieldMapping(
                table=table.name,
                field=column.name,
                qualified_name=f"{table.name}.{column.name}",
                type=column.type,
                description=column.description,
                sensitive=column.sensitive,
            )
            for table in table_registry.all_tables()
            for column in table.columns
        }

    def table_index(self) -> list[TableMapping]:
        """Return table names and counts, without exposing any fields."""
        return [
            TableMapping(
                table=table.name,
                description=table.description,
                field_count=len(table.columns),
                relationship_count=len(table.get_relationships()),
            )
            for table in self.table_registry.all_tables()
        ]

    def field_index(self, table_names: list[str] | None = None) -> list[FieldMapping]:
        """Return qualified fields for selected, known tables."""
        allowed = set(table_names) if table_names is not None else set(self._tables)
        return [field for field in self._fields.values() if field.table in allowed]

    def resolve_field(self, reference: str, table_names: list[str] | None = None) -> list[FieldMapping]:
        """Resolve a qualified field or an unqualified field within a scope.

        Unqualified references intentionally return every matching table field;
        callers must resolve ambiguity instead of silently picking one table.
        """
        allowed = set(table_names) if table_names is not None else set(self._tables)
        if "." in reference:
            field = self._fields.get(reference)
            return [field] if field and field.table in allowed else []
        return [
            field
            for field in self._fields.values()
            if field.table in allowed and field.field == reference
        ]

    def resolve_term(self, name_or_alias: str, table_names: list[str] | None = None) -> BusinessTermMapping | None:
        """Resolve a configured term to candidate tables, never to fields."""
        term = self.business_registry.get(name_or_alias)
        if term is None:
            return None
        return self._map_term(term, table_names)

    def term_index(self, table_names: list[str] | None = None) -> list[BusinessTermMapping]:
        """Return configured terms with resolved table names."""
        return [self._map_term(term, table_names) for term in self.business_registry.all_terms()]

    def match_tables(self, query: str) -> list[TableMapping]:
        """Match configured business language to candidate tables.

        Matching is intentionally small and data-driven: a configured term or
        alias is looked up in the query, then only that term's candidate tables
        are returned.  Field discovery happens separately after this step.
        """
        matched_names: list[str] = []
        lowered = query.casefold()
        for term in self.business_registry.all_terms():
            labels = [term.name, *term.aliases]
            if any(label.casefold() in lowered for label in labels if label):
                mapping = self._map_term(term, None)
                matched_names.extend(mapping.resolved_tables)
        unique_names = list(dict.fromkeys(matched_names))
        return [table for table in self.table_index() if table.table in unique_names]

    def disclose(
        self,
        level: DisclosureLevel,
        *,
        table_names: list[str] | None = None,
        field_names: list[str] | None = None,
        term_names: list[str] | None = None,
    ) -> BusinessKnowledgeDisclosure:
        """Build one bounded disclosure payload.

        ``index`` exposes only table summaries.  ``fields`` adds fields for the
        selected tables.  ``detail`` adds relationships and configured term
        mappings.  Unknown table/field names are ignored so callers can safely
        pass model-generated candidates and validate the resulting payload.
        """
        known_tables = [name for name in (table_names or self._tables.keys()) if name in self._tables]
        tables = [item for item in self.table_index() if item.table in set(known_tables)]
        if level == "index":
            fields: list[FieldMapping] = []
        elif field_names is None:
            fields = self.field_index(known_tables)
        else:
            fields = [
                field
                for reference in field_names
                for field in self.resolve_field(reference, known_tables)
            ]
            fields = list({field.qualified_name: field for field in fields}.values())

        relationships = []
        if level == "detail":
            for table_name in known_tables:
                table = self._tables[table_name]
                for relation in table.get_relationships():
                    relationships.append(
                        RelationshipMapping(
                            from_field=f"{table.name}.{relation['from_field']}",
                            to=relation["to"],
                            type=relation["type"],
                        )
                    )

        terms = []
        if level == "detail" and term_names is not None:
            for name in term_names:
                mapping = self.resolve_term(name, known_tables)
                if mapping is not None:
                    terms.append(mapping)

        return BusinessKnowledgeDisclosure(
            level=level,
            tables=tables,
            fields=fields,
            relationships=relationships,
            business_terms=terms,
        )

    def _map_term(self, term: BusinessTerm, table_names: list[str] | None) -> BusinessTermMapping:
        allowed = set(table_names) if table_names is not None else set(self._tables)
        resolved = [table for table in term.candidate_tables if table in allowed]
        return BusinessTermMapping(
            name=term.name,
            description=term.description,
            aliases=term.aliases,
            candidate_tables=term.candidate_tables,
            resolved_tables=list(dict.fromkeys(resolved)),
            filters=term.filters,
        )
