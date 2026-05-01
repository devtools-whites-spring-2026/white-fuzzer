"""Build grammar productions from a normalised :class:`ApiSpec`.

The builder is structural: every property name in the spec turns into a
fixed *terminal* in the resulting :class:`ObjectNode`, and only the
values turn into :class:`Leaf` nodes. Required/optional information is
preserved on the object so the generator can decide which optional
fields to emit.

For arrays we emit a :class:`Repeat` whose body is the schema of the
items — leaves nested deeper retain their mutable status.

Object / array nesting depth is capped (default 4) to avoid exponential
blowups on recursive schemas; any node deeper than the cap collapses
into a string leaf with the cut-off marker.
"""
from src.grammar.grammar import (
    LEAF_BOOLEAN,
    LEAF_ENUM,
    LEAF_INTEGER,
    LEAF_NUMBER,
    LEAF_STRING,
    EndpointGrammar,
    GrammarNode,
    Leaf,
    ObjectNode,
    Repeat,
)
from src.spec.types import (
    ApiSpec,
    ArraySchema,
    BooleanSchema,
    IntegerSchema,
    NumberSchema,
    ObjectSchema,
    OpaqueSchema,
    Operation,
    SchemaNode,
    StringSchema,
)

DEFAULT_MAX_DEPTH = 4


# --- public API -----------------------------------------------------------


def build_grammar(operation: Operation, max_depth: int = DEFAULT_MAX_DEPTH) -> EndpointGrammar:
    """Turn an :class:`Operation` into an :class:`EndpointGrammar`."""
    path_props: list[tuple[str, GrammarNode]] = []
    query_props: list[tuple[str, GrammarNode]] = []
    path_required: list[str] = []
    query_required: list[str] = []

    for param in operation.parameters:
        leaf = _schema_to_grammar(param.schema, max_depth, depth=0)
        if param.location == "path":
            path_props.append((param.name, leaf))
            path_required.append(param.name)  # path params are always required
        elif param.location == "query":
            query_props.append((param.name, leaf))
            if param.required:
                query_required.append(param.name)

    body: GrammarNode | None = None
    if operation.request_body is not None:
        body = _schema_to_grammar(operation.request_body, max_depth, depth=0)

    return EndpointGrammar(
        operation_id=operation.operation_id,
        method=operation.method,
        url_template=operation.path,
        path_params=ObjectNode(name="path", properties=path_props, required=path_required),
        query_params=ObjectNode(name="query", properties=query_props, required=query_required),
        body=body,
    )


def build_all(spec: ApiSpec, max_depth: int = DEFAULT_MAX_DEPTH) -> list[EndpointGrammar]:
    return [build_grammar(op, max_depth) for op in spec.operations]


# --- schema -> grammar ----------------------------------------------------


def _schema_to_grammar(
    schema: SchemaNode, max_depth: int, depth: int
) -> GrammarNode:
    if depth >= max_depth:
        return Leaf(
            type_hint=LEAF_STRING,
            example="<truncated>",
        )

    if isinstance(schema, StringSchema):
        if schema.enum:
            return Leaf(type_hint=LEAF_ENUM, enum=list(schema.enum), example=schema.enum[0])
        return Leaf(
            type_hint=LEAF_STRING,
            example=schema.example if schema.example is not None else _example_for_format(schema.fmt),
            min_length=schema.min_length,
            max_length=schema.max_length,
        )
    if isinstance(schema, IntegerSchema):
        if schema.enum:
            return Leaf(type_hint=LEAF_ENUM, enum=list(schema.enum), example=schema.enum[0])
        return Leaf(
            type_hint=LEAF_INTEGER,
            minimum=schema.minimum,
            maximum=schema.maximum,
            example=schema.example,
        )
    if isinstance(schema, NumberSchema):
        return Leaf(
            type_hint=LEAF_NUMBER,
            minimum=schema.minimum,
            maximum=schema.maximum,
            example=schema.example,
        )
    if isinstance(schema, BooleanSchema):
        return Leaf(type_hint=LEAF_BOOLEAN, example=schema.example)
    if isinstance(schema, ArraySchema):
        body = _schema_to_grammar(
            schema.items if schema.items is not None else OpaqueSchema(),
            max_depth,
            depth + 1,
        )
        return Repeat(
            body=body,
            min_times=schema.min_items,
            max_times=max(schema.min_items, min(schema.max_items, 5)),
        )
    if isinstance(schema, ObjectSchema):
        props: list[tuple[str, GrammarNode]] = []
        for key, child in schema.properties.items():
            props.append((key, _schema_to_grammar(child, max_depth, depth + 1)))
        return ObjectNode(properties=props, required=list(schema.required))
    if isinstance(schema, OpaqueSchema):
        # Unknown serializer / unresolved ref — treat as a single mutable string.
        return Leaf(
            type_hint=LEAF_STRING,
            example=f"<{schema.hint or 'opaque'}>",
        )

    return Leaf(type_hint=LEAF_STRING, example="<unknown>")


def _example_for_format(fmt: str | None) -> str:
    return {
        "email": "user@example.com",
        "uuid": "00000000-0000-0000-0000-000000000000",
        "date": "2024-01-01",
        "date-time": "2024-01-01T00:00:00Z",
        "uri": "https://example.com",
        "ipv4": "127.0.0.1",
    }.get(fmt or "", "string")
