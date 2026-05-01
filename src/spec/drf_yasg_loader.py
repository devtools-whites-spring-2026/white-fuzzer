"""Statically extract operations from drf-yasg embedded DSL.

The TestY swagger module ships its specification as Python files that
build ``swagger_auto_schema(...)`` objects. We can't import those files
because they pull in Django, models, app config and so on. Instead, we
parse them as text via :mod:`ast` and reconstruct the same normalised
:class:`ApiSpec` shape that :mod:`src.spec.loader` produces.

What we recognise:

* ``openapi.Schema(type=openapi.TYPE_OBJECT, properties={...}, ...)`` —
  including arrays, primitives, format and description.
* ``openapi.Parameter(name, openapi.IN_QUERY|IN_PATH|IN_HEADER, type=...,
  items=..., description=...)``.
* ``swagger_auto_schema(request_body=..., manual_parameters=[...])``.
* ``method_decorator(name='list', decorator=swagger_auto_schema(...))``
  — used in cases.py.

Anything that resolves to a serializer class (e.g. ``ProjectSerializer``)
we cannot statically dereference; we record it as an
:class:`OpaqueSchema` with a hint, which still lets the grammar builder
treat it as a single mutable leaf.

We don't try to recover HTTP method/path here — those live in Django
URL routers, which are outside the swagger archive. Each variable
binding (e.g. ``project_create_schema``) becomes an ``Operation`` whose
operation_id is the variable name and whose method/path are inferred
from the variable name conventions (``*_create_schema`` -> POST ``/``,
``*_update_schema`` -> PUT, ``*_list_schema`` -> GET, etc.). This is
sufficient for grammar construction and unit tests.
"""
import ast
from pathlib import Path
from typing import Any

from src.spec.types import (
    ApiSpec,
    ArraySchema,
    BooleanSchema,
    IntegerSchema,
    NumberSchema,
    ObjectSchema,
    OpaqueSchema,
    Operation,
    Parameter,
    SchemaNode,
    StringSchema,
)


# Mapping from drf-yasg openapi.TYPE_* constants to schema classes.
_TYPE_MAP = {
    "TYPE_STRING": "string",
    "TYPE_INTEGER": "integer",
    "TYPE_NUMBER": "number",
    "TYPE_BOOLEAN": "boolean",
    "TYPE_ARRAY": "array",
    "TYPE_OBJECT": "object",
    "TYPE_FILE": "string",  # treat file uploads as opaque strings
}

_LOC_MAP = {
    "IN_QUERY": "query",
    "IN_PATH": "path",
    "IN_HEADER": "header",
    "IN_FORM": "query",  # close enough for fuzzing
    "IN_BODY": "body",
}


# --- public API -----------------------------------------------------------


def load_drf_yasg_module(source: str | Path) -> ApiSpec:
    """Parse a single ``swagger/*.py`` file and produce an ApiSpec."""
    text = Path(source).read_text(encoding="utf-8")
    return load_drf_yasg_source(text, filename=str(source))


def load_drf_yasg_source(text: str, filename: str = "<string>") -> ApiSpec:
    tree = ast.parse(text, filename=filename)

    # First pass: collect simple variable bindings so we can resolve
    # references like `_NAME = 'name'` and re-used Parameter objects.
    bindings: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            bindings[node.targets[0].id] = node.value

    operations: list[Operation] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        var_name = node.targets[0].id
        op = _try_build_operation(var_name, node.value, bindings)
        if op is not None:
            operations.append(op)

    return ApiSpec(operations=operations, base_path="")


# --- operation extraction -------------------------------------------------


def _try_build_operation(
    var_name: str, value: ast.AST, bindings: dict[str, ast.AST]
) -> Operation | None:
    auto = _unwrap_swagger_auto_schema(value, bindings)
    if auto is None:
        return None

    parameters: list[Parameter] = []
    body: SchemaNode | None = None

    for kw in auto.keywords:
        if kw.arg == "manual_parameters":
            parameters.extend(_extract_parameters(kw.value, bindings))
        elif kw.arg == "request_body":
            body = _build_schema_from_node(kw.value, bindings)

    method, path = _infer_method_and_path(var_name)
    return Operation(
        operation_id=var_name,
        method=method,
        path=path,
        parameters=parameters,
        request_body=body,
    )


def _unwrap_swagger_auto_schema(
    value: ast.AST, bindings: dict[str, ast.AST]
) -> ast.Call | None:
    """Find an inner ``swagger_auto_schema(...)`` call.

    Handles two shapes used in the codebase:

    * ``swagger_auto_schema(...)`` directly,
    * ``method_decorator(name=..., decorator=swagger_auto_schema(...))``.
    """
    if not isinstance(value, ast.Call):
        return None
    func_name = _callable_name(value.func)
    if func_name == "swagger_auto_schema":
        return value
    if func_name == "method_decorator":
        for kw in value.keywords:
            if kw.arg == "decorator" and isinstance(kw.value, ast.Call):
                if _callable_name(kw.value.func) == "swagger_auto_schema":
                    return kw.value
    return None


def _infer_method_and_path(var_name: str) -> tuple[str, str]:
    suffix_map = {
        "_list_schema": ("GET", ""),
        "_create_schema": ("POST", ""),
        "_update_schema": ("PUT", "{id}/"),
        "_partial_update_schema": ("PATCH", "{id}/"),
        "_retrieve_schema": ("GET", "{id}/"),
        "_destroy_schema": ("DELETE", "{id}/"),
    }
    for suffix, (method, tail) in suffix_map.items():
        if var_name.endswith(suffix):
            base = var_name[: -len(suffix)]
            return method, f"/{base}/{tail}"
    # Custom action: assume POST on /{base}/{action}/
    base = var_name.removesuffix("_schema")
    return "POST", f"/{base}/"


# --- parameter / schema extraction ---------------------------------------


def _extract_parameters(
    node: ast.AST, bindings: dict[str, ast.AST]
) -> list[Parameter]:
    out: list[Parameter] = []
    if isinstance(node, ast.Name):
        node = bindings.get(node.id, node)
    if not isinstance(node, ast.List):
        return out
    for elt in node.elts:
        param = _build_parameter(elt, bindings)
        if param is not None:
            out.append(param)
    return out


def _build_parameter(
    node: ast.AST, bindings: dict[str, ast.AST]
) -> Parameter | None:
    if isinstance(node, ast.Name):
        node = bindings.get(node.id, node)
    if isinstance(node, ast.Call) and _callable_name(node.func) == "openapi.Parameter":
        # signature: Parameter(name, in_, description=None, required=None, schema=None,
        #                       type=None, format=None, enum=None, items=None, ...)
        args = node.args
        kwargs = {kw.arg: kw.value for kw in node.keywords}
        name = _literal(args[0]) if args else _literal(kwargs.get("name"))
        location_node = args[1] if len(args) > 1 else kwargs.get("in_")
        location = _drf_constant(location_node, _LOC_MAP) or "query"
        type_const = _drf_constant(kwargs.get("type"), _TYPE_MAP) or "string"
        items_node = kwargs.get("items")
        items_schema: SchemaNode | None = None
        if isinstance(items_node, ast.Call) and _callable_name(items_node.func) == "openapi.Items":
            items_schema = _build_inline_schema(items_node, bindings)

        schema = _primitive_schema(
            type_const,
            description=_literal(kwargs.get("description")),
            fmt=_literal(kwargs.get("format")),
            enum=_literal(kwargs.get("enum")),
            items=items_schema,
        )
        # If still no name (e.g. Parameter built dynamically) use repr.
        if not isinstance(name, str):
            name = "param"
        required = bool(_literal(kwargs.get("required"))) or location == "path"
        return Parameter(
            name=name,
            location=location,
            schema=schema,
            required=required,
            description=_literal(kwargs.get("description")),
        )
    # Factory calls like ordering_param_factory('id', 'name') -> we don't
    # know their internals here, but represent them as a single string
    # query parameter named after the function.
    if isinstance(node, ast.Call):
        fn = _callable_name(node.func)
        if fn.endswith("ordering_param_factory"):
            return Parameter(
                name="ordering",
                location="query",
                schema=StringSchema(description="Ordering field"),
                required=False,
            )
        if fn.endswith("search_param_factory"):
            return Parameter(
                name="search",
                location="query",
                schema=StringSchema(description="Search query"),
                required=False,
            )
    return None


def _build_schema_from_node(
    node: ast.AST, bindings: dict[str, ast.AST]
) -> SchemaNode:
    if isinstance(node, ast.Name):
        # Either a local Schema binding or a Serializer class we can't resolve.
        bound = bindings.get(node.id)
        if bound is not None and bound is not node:
            return _build_schema_from_node(bound, bindings)
        return OpaqueSchema(hint=f"serializer:{node.id}")
    if isinstance(node, ast.Call):
        fn = _callable_name(node.func)
        if fn == "openapi.Schema":
            return _build_inline_schema(node, bindings)
        # Serializer instantiation: ProjectSerializer() / FooSerializer(many=True)
        if fn.endswith("Serializer"):
            many = any(
                kw.arg == "many" and _literal(kw.value) is True for kw in node.keywords
            )
            inner = OpaqueSchema(hint=f"serializer:{fn}")
            if many:
                return ArraySchema(items=inner)
            return inner
    return OpaqueSchema(hint="unknown-request-body")


def _build_inline_schema(
    call: ast.Call, bindings: dict[str, ast.AST]
) -> SchemaNode:
    kwargs = {kw.arg: kw.value for kw in call.keywords}
    type_const = _drf_constant(kwargs.get("type"), _TYPE_MAP) or "string"
    description = _literal(kwargs.get("description"))
    fmt = _literal(kwargs.get("format"))
    enum = _literal(kwargs.get("enum"))

    if type_const == "object":
        properties: dict[str, SchemaNode] = {}
        prop_node = kwargs.get("properties")
        if isinstance(prop_node, ast.Dict):
            for k, v in zip(prop_node.keys, prop_node.values):
                key = _literal(k)
                if isinstance(key, str):
                    properties[key] = _build_schema_from_node(v, bindings)
        required = _literal(kwargs.get("required")) or []
        return ObjectSchema(
            description=description,
            properties=properties,
            required=list(required) if isinstance(required, list) else [],
        )
    if type_const == "array":
        items_node = kwargs.get("items")
        items_schema: SchemaNode = OpaqueSchema(hint="array-without-items")
        if items_node is not None:
            items_schema = _build_schema_from_node(items_node, bindings)
        return ArraySchema(description=description, items=items_schema)
    return _primitive_schema(type_const, description=description, fmt=fmt, enum=enum)


def _primitive_schema(
    type_const: str,
    description: str | None = None,
    fmt: str | None = None,
    enum: Any = None,
    items: SchemaNode | None = None,
) -> SchemaNode:
    if type_const == "string":
        return StringSchema(description=description, fmt=fmt, enum=enum if isinstance(enum, list) else None)
    if type_const == "integer":
        return IntegerSchema(description=description, enum=enum if isinstance(enum, list) else None)
    if type_const == "number":
        return NumberSchema(description=description)
    if type_const == "boolean":
        return BooleanSchema(description=description)
    if type_const == "array":
        return ArraySchema(description=description, items=items or OpaqueSchema())
    return OpaqueSchema(description=description, hint=f"type={type_const!r}")


# --- AST helpers ----------------------------------------------------------


def _callable_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_callable_name(node.value)}.{node.attr}"
    return ""


def _drf_constant(node: ast.AST | None, mapping: dict[str, str]) -> str | None:
    if node is None:
        return None
    name = _callable_name(node)
    if "." in name:
        name = name.rsplit(".", 1)[-1]
    return mapping.get(name)


def _literal(node: ast.AST | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None
