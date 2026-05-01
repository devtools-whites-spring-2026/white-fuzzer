"""Normalised OpenAPI/Swagger type AST.

This is a deliberately small subset focused on what we need for grammar
construction and fuzz value generation. It is independent of the source
format (raw OpenAPI JSON/YAML, dict, or drf-yasg Python DSL).
"""
from dataclasses import dataclass, field
from typing import Any


# --- Schema nodes ---------------------------------------------------------


@dataclass
class SchemaNode:
    """Base class for all schema nodes."""

    description: str | None = None
    nullable: bool = False
    example: Any = None


@dataclass
class StringSchema(SchemaNode):
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    fmt: str | None = None  # email, uuid, date, date-time, ...
    enum: list[str] | None = None


@dataclass
class IntegerSchema(SchemaNode):
    minimum: int | None = None
    maximum: int | None = None
    enum: list[int] | None = None


@dataclass
class NumberSchema(SchemaNode):
    minimum: float | None = None
    maximum: float | None = None


@dataclass
class BooleanSchema(SchemaNode):
    pass


@dataclass
class ArraySchema(SchemaNode):
    items: SchemaNode | None = None
    min_items: int = 0
    max_items: int = 5


@dataclass
class ObjectSchema(SchemaNode):
    properties: dict[str, SchemaNode] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)


@dataclass
class OpaqueSchema(SchemaNode):
    """Used when we cannot resolve a referenced serializer; behaves as a string leaf."""

    hint: str = ""


# --- Operation / Parameter ------------------------------------------------


@dataclass
class Parameter:
    name: str
    location: str  # "path" | "query" | "header"
    schema: SchemaNode
    required: bool = False
    description: str | None = None


@dataclass
class Operation:
    operation_id: str
    method: str  # GET / POST / PUT / PATCH / DELETE
    path: str  # e.g. "/api/v1/cases/{id}/"
    parameters: list[Parameter] = field(default_factory=list)
    request_body: SchemaNode | None = None
    description: str | None = None


@dataclass
class ApiSpec:
    """A normalised view over an OpenAPI document."""

    operations: list[Operation] = field(default_factory=list)
    base_path: str = ""
