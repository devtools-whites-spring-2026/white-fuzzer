import json
import unittest

from src.openapi_schema import (
    EndpointSchema,
    FieldType,
    request_schema_to_mutatable_alternative,
)


def _query_strings(requests):
    result = []
    for request in requests:
        if request.params is None:
            result.append(None)
        else:
            result.append(request.params.to_string())
    return result


def _data_strings(requests):
    result = []
    for request in requests:
        if request.data is None:
            result.append(None)
        else:
            result.append(request.data.to_string())
    return result


class RequestSchemaToMutatableAlternativeTest(unittest.TestCase):
    def test_expands_nested_query_params(self) -> None:
        endpoint: EndpointSchema = {
            "path": "/users",
            "method": "GET",
            "request": {"content_type": "application/json", "schema": {}},
            "responses": {},
            "parameters": [
                {
                    "name": "required",
                    "type": FieldType.STRING,
                    "constraints": {"required": True},
                },
                {
                    "name": "filter",
                    "type": FieldType.OBJECT,
                    "constraints": {},
                    "properties": {
                        "kind": {
                            "name": "kind",
                            "type": FieldType.STRING,
                            "constraints": {"required": True},
                        },
                        "status": {
                            "name": "status",
                            "type": FieldType.STRING,
                            "constraints": {},
                        },
                    },
                },
            ],
        }

        requests = request_schema_to_mutatable_alternative(endpoint)

        self.assertEqual(3, len(requests))
        queries = {
            json.dumps(json.loads(value), sort_keys=True)
            for value in _query_strings(requests)
            if value is not None
        }
        self.assertEqual(
            {
                json.dumps({"required": ""}, sort_keys=True),
                json.dumps(
                    {"required": "", "filter": {"kind": ""}},
                    sort_keys=True,
                ),
                json.dumps(
                    {
                        "required": "",
                        "filter": {"kind": "", "status": ""},
                    },
                    sort_keys=True,
                ),
            },
            queries,
        )
        self.assertTrue(all(request.data is None for request in requests))

    def test_expands_nested_body(self) -> None:
        endpoint: EndpointSchema = {
            "path": "/users",
            "method": "POST",
            "request": {
                "content_type": "application/json",
                "schema": {
                    "name": {
                        "name": "name",
                        "type": FieldType.STRING,
                        "constraints": {"required": True},
                    },
                    "profile": {
                        "name": "profile",
                        "type": FieldType.OBJECT,
                        "constraints": {},
                        "properties": {
                            "email": {
                                "name": "email",
                                "type": FieldType.STRING,
                                "constraints": {"required": True},
                            },
                            "nickname": {
                                "name": "nickname",
                                "type": FieldType.STRING,
                                "constraints": {},
                            },
                        },
                    },
                },
            },
            "responses": {},
            "parameters": [],
        }

        requests = request_schema_to_mutatable_alternative(endpoint)

        self.assertEqual(3, len(requests))
        bodies = {
            json.dumps(json.loads(value), sort_keys=True)
            for value in _data_strings(requests)
            if value is not None
        }
        self.assertEqual(
            {
                json.dumps({"name": ""}, sort_keys=True),
                json.dumps(
                    {"name": "", "profile": {"email": ""}},
                    sort_keys=True,
                ),
                json.dumps(
                    {"name": "", "profile": {"email": "", "nickname": ""}},
                    sort_keys=True,
                ),
            },
            bodies,
        )
        self.assertTrue(all(request.params is None for request in requests))

    def test_combines_query_and_body_variants(self) -> None:
        endpoint: EndpointSchema = {
            "path": "/users",
            "method": "POST",
            "request": {
                "content_type": "application/json",
                "schema": {
                    "payload": {
                        "name": "payload",
                        "type": FieldType.STRING,
                        "constraints": {"required": True},
                    }
                },
            },
            "responses": {},
            "parameters": [
                {
                    "name": "required",
                    "type": FieldType.STRING,
                    "constraints": {"required": True},
                },
                {
                    "name": "optional",
                    "type": FieldType.STRING,
                    "constraints": {},
                },
            ],
        }

        requests = request_schema_to_mutatable_alternative(endpoint)

        self.assertEqual(2, len(requests))
        query_bodies = {
            (
                None
                if request.params is None
                else json.dumps(json.loads(request.params.to_string()), sort_keys=True),
                None
                if request.data is None
                else json.dumps(json.loads(request.data.to_string()), sort_keys=True),
            )
            for request in requests
        }
        self.assertEqual(
            {
                (
                    json.dumps({"required": ""}, sort_keys=True),
                    json.dumps({"payload": ""}, sort_keys=True),
                ),
                (
                    json.dumps(
                        {"required": "", "optional": ""},
                        sort_keys=True,
                    ),
                    json.dumps({"payload": ""}, sort_keys=True),
                ),
            },
            query_bodies,
        )

    def test_expands_array_body(self) -> None:
        endpoint: EndpointSchema = {
            "path": "/users",
            "method": "POST",
            "request": {
                "content_type": "application/json",
                "schema": {
                    "tags": {
                        "name": "tags",
                        "type": FieldType.ARRAY,
                        "constraints": {"required": True},
                        "items": {
                            "name": "item",
                            "type": FieldType.STRING,
                            "constraints": {"required": True},
                        },
                    }
                },
            },
            "responses": {},
            "parameters": [],
        }

        requests = request_schema_to_mutatable_alternative(endpoint)

        self.assertEqual(2, len(requests))
        bodies = {
            json.dumps(json.loads(value), sort_keys=True)
            for value in _data_strings(requests)
            if value is not None
        }
        self.assertEqual(
            {
                json.dumps({"tags": []}, sort_keys=True),
                json.dumps({"tags": [""]}, sort_keys=True),
            },
            bodies,
        )


if __name__ == "__main__":
    unittest.main()
