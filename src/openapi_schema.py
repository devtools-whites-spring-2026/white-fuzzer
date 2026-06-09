from __future__ import annotations

import contextlib
import itertools
import json
from enum import Enum
from typing import Any, Literal, TypedDict, TypeVar

from src.mutatable_request import (
    MutatableField,
    MutatableRestRequest,
    StringWithMutablePlaceholders,
)


# later we will add more
class FieldType(str, Enum):
    STRING = "string"
    ARRAY = "array"
    OBJECT = "object"


# later we will add more
class FieldConstraints(TypedDict, total=False):
    required: bool


class SchemaField(TypedDict, total=False):
    name: str
    type: FieldType
    constraints: FieldConstraints
    items: SchemaField
    properties: dict[str, SchemaField]


class RequestSchema(TypedDict, total=True):
    content_type: Literal["application/json", "multipart/form-data"]
    schema: dict[str, SchemaField]


class ResponseInfo(TypedDict, total=True):
    status_code: int
    description: str


# maybe make me not a dict
class EndpointSchema(TypedDict, total=False):
    path: str
    method: Literal["GET", "POST", "PATCH", "PUT", "DELETE"]
    description: str
    request: RequestSchema
    responses: dict[int, ResponseInfo]
    parameters: list[SchemaField]


class SchemaFieldValue(TypedDict, total=False):
    name: str
    type: FieldType
    constraints: FieldConstraints
    value_placeholder: str
    array_elems: list[SchemaFieldValue]
    properties: dict[str, SchemaFieldValue]


def fresh_placeholder() -> str:
    return f"PLC{next_counter_fixed_width()}"


T = TypeVar("T")


def _flatmap(data: dict[str, list[T]]) -> list[dict[str, T]]:
    if not data:
        return [{}]
    keys = list(data)
    value_lists = [data[key] for key in keys]
    return [
        dict(zip(keys, values, strict=True))
        for values in itertools.product(*value_lists)
    ]


def _is_required(field: SchemaField) -> bool:
    return field.get("constraints", {}).get("required", False)


def _transform_object_properties(
    properties: dict[str, SchemaField],
) -> list[dict[str, SchemaFieldValue]]:
    required_fields = {
        name: field for name, field in properties.items() if _is_required(field)
    }
    optional_fields = {
        name: field for name, field in properties.items() if not _is_required(field)
    }

    required_variants = _flatmap(
        {name: transform(field) for name, field in required_fields.items()}
    )

    results = list(required_variants)
    for name, field in optional_fields.items():
        for required_variant in required_variants:
            for optional_variant in transform(field):
                results.append({**required_variant, name: optional_variant})
    return results


def transform(field: SchemaField) -> list[SchemaFieldValue]:
    field_type = field.get("type", FieldType.STRING)

    if field_type == FieldType.STRING:
        return [
            {
                "name": field["name"],
                "type": field_type,
                "constraints": field["constraints"],
                "value_placeholder": fresh_placeholder(),
                "array_elems": [],
                "properties": {},
            }
        ]

    if field_type == FieldType.ARRAY:
        items = field["items"]
        result: list[SchemaFieldValue] = [
            {
                "name": field["name"],
                "type": field_type,
                "constraints": field["constraints"],
                "value_placeholder": fresh_placeholder(),
                "array_elems": [],
                "properties": {},
            }
        ]
        for item_variant in transform(items):
            result.append(
                {
                    "name": field["name"],
                    "type": field_type,
                    "constraints": field["constraints"],
                    "value_placeholder": fresh_placeholder(),
                    "array_elems": [item_variant],
                    "properties": {},
                }
            )
        return result

    if field_type == FieldType.OBJECT:
        properties = field.get("properties", {})
        return [
            {
                "name": field["name"],
                "type": field_type,
                "constraints": field["constraints"],
                "value_placeholder": fresh_placeholder(),
                "array_elems": [],
                "properties": variant,
            }
            for variant in _transform_object_properties(properties)
        ]

    raise RuntimeError("Oh no")


statuses_post_endpoint: EndpointSchema = {
    "path": "/api/v2/statuses/",
    "method": "POST",
    "description": "",
    "request": {"content_type": "application/json", "schema": {}},
    "responses": {201: {"status_code": 201, "description": ""}},
    "parameters": [
        {
            "name": "data",
            "type": FieldType.OBJECT,
            "constraints": {"required": True},
            "properties": {
                "id": {"name": "id", "type": FieldType.STRING, "constraints": {}},
                "url": {"name": "url", "type": FieldType.STRING, "constraints": {}},
                "name": {"name": "name", "type": FieldType.STRING, "constraints": {}},
                "color": {"name": "color", "type": FieldType.STRING, "constraints": {}},
                "type": {"name": "type", "type": FieldType.STRING, "constraints": {}},
                "project": {
                    "name": "project",
                    "type": FieldType.STRING,
                    "constraints": {},
                },
            },
        }
    ],
}


def _resolve_ref(ref_obj: dict, schema_dict: dict) -> dict:
    if "$ref" not in ref_obj:
        return ref_obj
    ref_path = ref_obj["$ref"].lstrip("#/").split("/")
    resolved = schema_dict
    for part in ref_path:
        resolved = resolved.get(part, {})
    return resolved


def _parse_field(name: str, field_def: dict, schema_dict: dict) -> SchemaField:
    field_type = field_def.get("type", "string")
    if field_type not in {"string", "array", "object"}:
        field_type = "string"
        # raise RuntimeError("Oh no")
    field: SchemaField = {
        "name": name,
        "type": FieldType(field_type),
        "constraints": {},
    }
    if field_type == "array" and "items" in field_def:
        field["items"] = _parse_field(
            "items", _resolve_ref(field_def["items"], schema_dict), schema_dict
        )
    if field_type == "object" and "properties" in field_def:
        field["properties"] = {
            name: _parse_field(name, _resolve_ref(data, schema_dict), schema_dict)
            for name, data in field_def["properties"].items()
        }
    return field


def parse_openapi_schema(schema_dict: dict[str, Any]) -> list[EndpointSchema]:
    endpoints = []
    for path, path_item in schema_dict.get("paths", {}).items():
        for method in ("get", "post", "put", "patch", "delete"):
            if method not in path_item:
                continue
            operation = path_item[method]

            request: RequestSchema = {"content_type": "application/json", "schema": {}}
            if "requestBody" in operation:
                for content_type, content_def in (
                    operation["requestBody"].get("content", {}).items()
                ):
                    resolved = _resolve_ref(content_def.get("schema", {}), schema_dict)
                    if "json" in content_type:
                        request["content_type"] = "application/json"
                    elif "form-data" in content_type:
                        request["content_type"] = "multipart/form-data"
                    if resolved.get("type") == "object" and "properties" in resolved:
                        required = resolved.get("required", [])
                        for prop_name, prop_data in resolved["properties"].items():
                            field = _parse_field(
                                prop_name,
                                _resolve_ref(prop_data, schema_dict),
                                schema_dict,
                            )
                            field["constraints"]["required"] = prop_name in required
                            request["schema"][prop_name] = field

            responses: dict[int, ResponseInfo] = {}
            for code, resp_def in operation.get("responses", {}).items():
                with contextlib.suppress(ValueError, TypeError):
                    responses[int(code)] = {
                        "status_code": int(code),
                        "description": resp_def.get("description", ""),
                    }

            parameters = []
            for param in operation.get("parameters", []):
                field = _parse_field(
                    param.get("name", ""),
                    _resolve_ref(param.get("schema", {}), schema_dict),
                    schema_dict,
                )
                field["name"] = param.get("name", "")
                field["constraints"]["required"] = param.get("required", False)
                parameters.append(field)

            endpoints.append(
                EndpointSchema(
                    path=path,
                    method=method.upper(),
                    description=operation.get(
                        "description", operation.get("operationId", "")
                    ),
                    request=request,
                    responses=responses,
                    parameters=parameters,
                )
            )
    return endpoints


def _default_str(field: SchemaField) -> str:
    t = field.get("type", FieldType.STRING)
    if t == FieldType.ARRAY:
        return "[]"
    if t == FieldType.OBJECT:
        return "{}"
    return ""


counter = 0


def next_counter_fixed_width():
    global counter
    result = counter
    counter += 1
    return f"{result:03d}"


def _json_template(schema: dict[str, SchemaField]) -> tuple[str, list[MutatableField]]:
    placeholders: list[MutatableField] = []

    def walk(props: dict[str, SchemaField]) -> dict:
        obj: dict = {}
        for name, field in props.items():
            field_type = field.get("type", FieldType.STRING)
            if field_type == FieldType.ARRAY:
                items = field.get("items")
                if items is not None and items.get("type") == FieldType.OBJECT:
                    obj[name] = [walk(items.get("properties", {}))]
                elif items is not None:
                    placeholder = f"PLC{next_counter_fixed_width()}__"
                    obj[name] = [placeholder]
                    placeholders.append(
                        MutatableField(placeholder, _default_str(items))
                    )
                else:
                    obj[name] = []
            elif field_type == FieldType.OBJECT:
                obj[name] = walk(field.get("properties", {}))
            else:
                placeholder = f"PLC{next_counter_fixed_width()}__"
                obj[name] = placeholder
                placeholders.append(MutatableField(placeholder, _default_str(field)))
        return obj

    walked = walk(schema)
    return json.dumps(walked), placeholders


def request_schema_to_mutatable(request: EndpointSchema) -> list[MutatableRestRequest]:
    path = request.get("path", "/")
    method = request.get("method", "GET")
    body_schema = request.get("request", {}).get("schema", {})
    parameters = request.get("parameters", [])

    query_params = None
    if parameters:
        pc = itertools.count()
        params_placeholders: list[MutatableField] = []
        params_parts: list[str] = []
        for param in parameters:
            name = param.get("name", "")
            placeholder = f"PLC{next(pc)}__"
            params_parts.append(f'"{name}": "{placeholder}"')
            params_placeholders.append(MutatableField(placeholder, _default_str(param)))
        params_template = "{" + ", ".join(params_parts) + "}"
        if params_placeholders:
            query_params = StringWithMutablePlaceholders(
                params_template, params_placeholders
            )

    data = None
    if body_schema:
        template_str, placeholders = _json_template(body_schema)
        if placeholders:
            data = StringWithMutablePlaceholders(template_str, placeholders)

    return [MutatableRestRequest(method, path, query_params, data)]


def _render_field_value(
    field: SchemaFieldValue,
    placeholders: list[MutatableField],
) -> Any:
    field_type = field.get("type", FieldType.STRING)
    if field_type == FieldType.STRING:
        placeholder = field["value_placeholder"]
        placeholders.append(MutatableField(placeholder, ""))
        return placeholder
    if field_type == FieldType.ARRAY:
        return [
            _render_field_value(array_field, placeholders)
            for array_field in field.get("array_elems", [])
        ]
    if field_type == FieldType.OBJECT:
        return {
            name: _render_field_value(prop, placeholders)
            for name, prop in field.get("properties", {}).items()
        }
    raise RuntimeError("Oh no")


def _render_object_template(
    fields: dict[str, SchemaFieldValue],
) -> tuple[str, list[MutatableField]]:
    placeholders: list[MutatableField] = []
    rendered = {
        name: _render_field_value(field, placeholders) for name, field in fields.items()
    }
    return json.dumps(rendered), placeholders


def _transform_top_level_fields(
    fields: dict[str, SchemaField],
) -> list[dict[str, SchemaFieldValue]]:
    if not fields:
        return [{}]
    return _transform_object_properties(fields)


def _to_mutable_string(
    fields: dict[str, SchemaFieldValue],
    keep_empty: bool,
) -> StringWithMutablePlaceholders | None:
    if not fields and not keep_empty:
        return None
    template, placeholders = _render_object_template(fields)
    return StringWithMutablePlaceholders(template, placeholders)


def request_schema_to_mutatable_alternative(
    request: EndpointSchema,
) -> list[MutatableRestRequest]:
    path = request.get("path", "/")
    method = request.get("method", "GET")
    body_schema = request.get("request", {}).get("schema", {})
    parameters = request.get("parameters", [])

    parameter_fields = {
        param["name"]: param for param in parameters if param.get("name")
    }
    query_variants = _transform_top_level_fields(parameter_fields)
    body_variants = _transform_top_level_fields(body_schema)

    requests: list[MutatableRestRequest] = []
    for query_variant in query_variants:
        for body_variant in body_variants:
            requests.append(
                MutatableRestRequest(
                    method,
                    path,
                    params=_to_mutable_string(query_variant, keep_empty=False),
                    data=_to_mutable_string(body_variant, keep_empty=bool(body_schema)),
                )
            )
    return requests


def demo_openapi_parsing() -> None:
    example = {
        "openapi": "3.0.0",
        "info": {"title": "Demo API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "operationId": "listUsers",
                    "description": "Fetch all users",
                    "parameters": [
                        {
                            "name": "page",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {"200": {"description": "A list of users"}},
                },
                "post": {
                    "operationId": "createUser",
                    "description": "Create a new user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CreateUser"}
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "User created"},
                        "400": {"description": "Validation error"},
                    },
                },
            },
            "/users/{id}": {
                "get": {
                    "operationId": "getUser",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "User details"},
                        "404": {"description": "Not found"},
                    },
                }
            },
        },
        "components": {
            "schemas": {
                "CreateUser": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Full name"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "metadata": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string"},
                                "score": {"type": "number"},
                            },
                            "required": ["source"],
                        },
                    },
                    "required": ["name"],
                }
            }
        },
    }

    endpoints = parse_openapi_schema(example)
    import json

    print(json.dumps(endpoints, default=str, indent=2))


def demo2():
    endp: EndpointSchema = {
        "path": "/api/v2/statuses/",
        "method": "POST",
        "description": "",
        "request": {"content_type": "application/json", "schema": {}},
        "responses": {201: {"status_code": 201, "description": ""}},
        "parameters": [
            {
                "name": "data",
                "type": FieldType.OBJECT,
                "constraints": {"required": True},
                "properties": {
                    "id": {"name": "id", "type": FieldType.STRING, "constraints": {}},
                    "url": {"name": "url", "type": FieldType.STRING, "constraints": {}},
                    "name": {
                        "name": "name",
                        "type": FieldType.STRING,
                        "constraints": {},
                    },
                    "color": {
                        "name": "color",
                        "type": FieldType.STRING,
                        "constraints": {},
                    },
                    "type": {
                        "name": "type",
                        "type": FieldType.STRING,
                        "constraints": {},
                    },
                    "project": {
                        "name": "project",
                        "type": FieldType.STRING,
                        "constraints": {},
                    },
                },
            }
        ],
    }
    data = request_schema_to_mutatable(endp)
    print(data)


if __name__ == "__main__":
    demo2()
    # demo_openapi_parsing()
