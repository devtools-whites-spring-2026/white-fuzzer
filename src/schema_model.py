from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaNode:

    name: str
    kind: str
    mutable: bool = True
    required: bool = True
    enum_values: list[Any] | None = None
    properties: dict[str, "SchemaNode"] = field(default_factory=dict)
    items: "SchemaNode | None" = None