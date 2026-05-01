"""Load an OpenAPI / Swagger 2.0 document into the normalised AST.

The loader supports:
  * a plain ``dict`` (already-parsed JSON / YAML),
  * a path to a ``.json`` or ``.yaml`` / ``.yml`` file.

It accepts both Swagger 2.0 (``swagger: '2.0'``) and OpenAPI 3.x styled
documents in the limited subset that drf-yasg emits. ``$ref`` resolution
within the same document is supported for ``#/definitions/...`` and
``#/components/schemas/...``.

Anything we cannot resolve is materialised as :class:`OpaqueSchema`
rather than crashing — this matches the philosophy of fuzzing where it
is preferable to produce *some* values for an unknown structure.
"""
import json
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

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

# Hard cap to break cycles in `$ref` chains. Any node deeper than this
# becomes an OpaqueSchema (-> a single mutable string leaf in the grammar).
_MAX_SCHEMA_DEPTH = 12


# --- public API -----------------------------------------------------------


def load_spec(source: dict | str | Path) -> ApiSpec:
    """Load and normalise an OpenAPI/Swagger document.

    ``source`` may be a parsed dict or a filesystem path.
    """
    doc = _read_document(source)
    resolver = _RefResolver(doc)

    base_path = doc.get("basePath", "") or ""
    paths = doc.get("paths", {}) or {}

    operations: list[Operation] = []
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        path_level_params = item.get("parameters", []) or []
        for method, op in item.items():
            if method.lower() not in _HTTP_METHODS:
                continue
            if not isinstance(op, dict):
                continue
            operations.append(
                _build_operation(
                    method=method.upper(),
                    path=path,
                    op=op,
                    path_level_params=path_level_params,
                    resolver=resolver,
                )
            )

    return ApiSpec(operations=operations, base_path=base_path)


# --- internals ------------------------------------------------------------


def _read_document(source: dict | str | Path) -> dict:
    if isinstance(source, dict):
        return source
    p = Path(source)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("PyYAML is required to load YAML specs") from e
        return yaml.safe_load(text)
    return json.loads(text)


class _RefResolver:
    def __init__(self, doc: dict) -> None:
        self.doc = doc

    def resolve(self, ref: str) -> dict:
        # Only intra-document refs supported.
        if not ref.startswith("#/"):
            return {}
        node: Any = self.doc
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return {}
        return node if isinstance(node, dict) else {}


def _build_operation(
    method: str,
    path: str,
    op: dict,
    path_level_params: list,
    resolver: _RefResolver,
) -> Operation:
    op_id = op.get("operationId") or f"{method.lower()}_{path.strip('/').replace('/', '_').replace('{','').replace('}','')}"
    parameters: list[Parameter] = []

    raw_params = list(path_level_params) + list(op.get("parameters", []) or [])
    body_schema: SchemaNode | None = None

    for raw in raw_params:
        if "$ref" in raw:
            raw = resolver.resolve(raw["$ref"]) or raw
        location = raw.get("in")
        name = raw.get("name", "")
        if location == "body":
            # Swagger 2.0 body parameter
            body_schema = _build_schema(raw.get("schema") or {}, resolver, depth=0)
            continue
        if location not in {"path", "query", "header"}:
            continue
        # In swagger 2 non-body params have type at the top level.
        schema_dict = raw.get("schema")
        if not schema_dict:
            schema_dict = {k: raw[k] for k in raw if k in {"type", "enum", "items", "format", "minimum", "maximum", "minLength", "maxLength", "pattern"}}
        parameters.append(
            Parameter(
                name=name,
                location=location,
                schema=_build_schema(schema_dict, resolver, depth=0),
                required=bool(raw.get("required", location == "path")),
                description=raw.get("description"),
            )
        )

    # OpenAPI 3 style requestBody
    rb = op.get("requestBody")
    if rb and not body_schema:
        if "$ref" in rb:
            rb = resolver.resolve(rb["$ref"]) or rb
        content = rb.get("content", {}) or {}
        media = content.get("application/json") or next(iter(content.values()), None)
        if isinstance(media, dict) and "schema" in media:
            body_schema = _build_schema(media["schema"], resolver, depth=0)

    return Operation(
        operation_id=op_id,
        method=method,
        path=path,
        parameters=parameters,
        request_body=body_schema,
        description=op.get("description") or op.get("summary"),
    )


def _build_schema(node: dict, resolver: _RefResolver, depth: int = 0) -> SchemaNode:
    if depth >= _MAX_SCHEMA_DEPTH:
        return OpaqueSchema(hint="recursion-cap")
    if not isinstance(node, dict) or not node:
        return OpaqueSchema(hint="empty")

    if "$ref" in node:
        resolved = resolver.resolve(node["$ref"])
        if resolved:
            return _build_schema(resolved, resolver, depth + 1)
        return OpaqueSchema(hint=f"unresolved:{node['$ref']}")

    # Composition keywords: best-effort -> first concrete branch.
    for kw in ("allOf", "oneOf", "anyOf"):
        if kw in node and isinstance(node[kw], list) and node[kw]:
            return _build_schema(node[kw][0], resolver, depth + 1)

    # Enum without explicit type — infer from first value.
    explicit_type = node.get("type")
    if not explicit_type and "enum" in node and node["enum"]:
        sample = node["enum"][0]
        if isinstance(sample, bool):
            explicit_type = "boolean"
        elif isinstance(sample, int):
            explicit_type = "integer"
        elif isinstance(sample, float):
            explicit_type = "number"
        else:
            explicit_type = "string"

    common = dict(
        description=node.get("description"),
        nullable=bool(node.get("nullable") or node.get("x-nullable") or False),
        example=node.get("example"),
    )

    if explicit_type == "string":
        return StringSchema(
            **common,
            min_length=node.get("minLength"),
            max_length=node.get("maxLength"),
            pattern=node.get("pattern"),
            fmt=node.get("format"),
            enum=node.get("enum"),
        )
    if explicit_type == "integer":
        return IntegerSchema(
            **common,
            minimum=node.get("minimum"),
            maximum=node.get("maximum"),
            enum=node.get("enum"),
        )
    if explicit_type == "number":
        return NumberSchema(
            **common,
            minimum=node.get("minimum"),
            maximum=node.get("maximum"),
        )
    if explicit_type == "boolean":
        return BooleanSchema(**common)
    if explicit_type == "array":
        items = node.get("items") or {}
        return ArraySchema(
            **common,
            items=_build_schema(items, resolver, depth + 1),
            min_items=int(node.get("minItems", 0) or 0),
            max_items=int(node.get("maxItems", 5) or 5),
        )
    if explicit_type == "object" or "properties" in node:
        properties = {}
        for k, v in (node.get("properties") or {}).items():
            properties[k] = _build_schema(v if isinstance(v, dict) else {}, resolver, depth + 1)
        return ObjectSchema(
            **common,
            properties=properties,
            required=list(node.get("required") or []),
        )

    return OpaqueSchema(**common, hint=f"type={explicit_type!r}")
