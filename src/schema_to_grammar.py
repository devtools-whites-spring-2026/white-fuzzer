from __future__ import annotations

import json
from typing import Any

from src.grammar import Grammar, MutationPolicy, Symbol
from src.schema_model import SchemaNode


class SchemaBuilderError(ValueError):
    pass


def build_from_schema(
    schema: SchemaNode,
    *,
    start: Symbol = "<start>",
) -> tuple[Grammar, MutationPolicy, Symbol]:

    grammar: Grammar = {}
    policy: MutationPolicy = {}

    root_symbol = _symbol_for(schema, path=schema.name or "root")
    grammar[start] = [[root_symbol]]
    policy[start] = False

    _build_node(schema, path=schema.name or "root", grammar=grammar, policy=policy)
    return grammar, policy, start


def _build_node(
    node: SchemaNode,
    *,
    path: str,
    grammar: Grammar,
    policy: MutationPolicy,
) -> Symbol:
    symbol = _symbol_for(node, path)
    policy[symbol] = node.mutable

    if node.kind == "string":
        grammar[symbol] = [[json.dumps(v)] for v in _string_values(node.name)]
        return symbol

    if node.kind == "integer":
        grammar[symbol] = [[str(v)] for v in _integer_values(node.name)]
        return symbol

    if node.kind == "boolean":
        grammar[symbol] = [["true"], ["false"]]
        return symbol

    if node.kind == "enum":
        if not node.enum_values:
            raise SchemaBuilderError(f"Enum node {path!r} has no enum_values")
        grammar[symbol] = [[_render_scalar(v)] for v in node.enum_values]
        return symbol

    if node.kind == "array":
        if node.items is None:
            raise SchemaBuilderError(f"Array node {path!r} has no items")

        item_symbol = _build_node(
            node.items,
            path=f"{path}[]",
            grammar=grammar,
            policy=policy,
        )
        grammar[symbol] = [
            ["[", "]"],
            ["[", item_symbol, "]"],
            ["[", item_symbol, ",", item_symbol, "]"],
        ]
        return symbol

    if node.kind == "object":
        items = list(node.properties.items())
        child_symbols: list[tuple[str, Symbol]] = []
        for field_name, child in items:
            if not child.required:
                continue
            child_symbol = _build_node(
                child,
                path=f"{path}.{field_name}",
                grammar=grammar,
                policy=policy,
            )
            child_symbols.append((field_name, child_symbol))

        grammar[symbol] = [_object_expansion(child_symbols)]
        return symbol

    raise SchemaBuilderError(f"Unsupported node kind: {node.kind!r} at {path!r}")


def _object_expansion(children: list[tuple[str, Symbol]]) -> list[str]:
    parts: list[str] = ["{"]
    for index, (field_name, child_symbol) in enumerate(children):
        parts.append(json.dumps(field_name))
        parts.append(":")
        parts.append(child_symbol)
        if index < len(children) - 1:
            parts.append(",")
    parts.append("}")
    return parts


def _symbol_for(node: SchemaNode, path: str) -> Symbol:
    normalized = path.replace("[", "_").replace("]", "").replace(".", "_")
    return f"<{normalized}_{node.kind}>"


def _render_scalar(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _string_values(name: str) -> list[str]:
    base = name or "value"
    return [
        "",
        base,
        f"{base}_test",
        "AAAA",
        "special_!@#",
    ]


def _integer_values(name: str) -> list[int]:
    return [0, 1, -1, 100, 9999]