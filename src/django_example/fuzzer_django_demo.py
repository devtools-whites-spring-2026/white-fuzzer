from pathlib import Path

from src.django_example.django_apps.demo_one.views import parse_quantity_view
from src.django_example.django_apps.demo_three.views import transfer_view
from src.django_example.django_apps.demo_two.views import coupon_check_view
from src.executor import DjangoClientExecutor
from src.fuzzer_main import print_fuzzing_result_default_formatting, run_fuzzer
from src.mutatable_request import (
    MutatableField,
    MutatableRestRequest,
    StringWithMutablePlaceholders,
)
from src.mutator import create_generic_mutator
from src.openapi_schema import parse_openapi_schema

DEMO_SETTINGS = "src.django_example.django_apps.demo_project.settings"


def _make_single_param_get_request(
    path: str, param_name: str, value: str
) -> MutatableRestRequest:
    placeholder = f"<{param_name}>"
    return MutatableRestRequest(
        request_type="GET",
        url=path,
        params=StringWithMutablePlaceholders(
            data='{"' + param_name + '": "' + placeholder + '"}',
            placeholders=[MutatableField(placeholder, value)],
        ),
    )


def run_demo_one() -> None:
    result = run_fuzzer(
        target=parse_quantity_view,
        initial_corpus=[
            _make_single_param_get_request("/quantity", "q", v)
            for v in ["12", "-5", "", "abc"]
        ],
        mutator=create_generic_mutator(),
        iterations=100,
        executor=DjangoClientExecutor(settings_module=DEMO_SETTINGS),
        coverage_include_paths=[
            str(Path("src/django_example/django_apps/demo_one").resolve()),
        ],
    )
    print("Demo #1 (quantity parser)")
    print_fuzzing_result_default_formatting(result)


def run_demo_two() -> None:
    result = run_fuzzer(
        target=coupon_check_view,
        initial_corpus=[
            _make_single_param_get_request("/coupon", "coupon", v)
            for v in ["SALE10", "WELCOME", "A/B", "LAST!"]
        ],
        mutator=create_generic_mutator(),
        iterations=20,
        executor=DjangoClientExecutor(settings_module=DEMO_SETTINGS),
        coverage_include_paths=[
            str(Path("src/django_example/django_apps/demo_two").resolve()),
        ],
    )
    print("Demo #2 (coupon validator)")
    print_fuzzing_result_default_formatting(result)


def run_demo_three() -> None:
    openapi_spec_dict = {
        "openapi": "3.0.0",
        "info": {"title": "Transfer API", "version": "1.0.0"},
        "paths": {
            "/transfer": {
                "post": {
                    "operationId": "transfer",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "from": {"type": "string"},
                                        "to": {"type": "string"},
                                        "amount": {"type": "string"},
                                    },
                                    "required": ["from", "to", "amount"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Transfer succeeded"},
                        "400": {"description": "Bad Request"},
                        "405": {"description": "Method Not Allowed"},
                    },
                }
            }
        },
    }
    spec = parse_openapi_schema(openapi_spec_dict)
    result = run_fuzzer(
        target=transfer_view,
        initial_corpus=[],
        mutator=create_generic_mutator(),
        iterations=200,
        executor=DjangoClientExecutor(settings_module=DEMO_SETTINGS, openapi_spec=spec),
        coverage_include_paths=[
            str(Path("src/django_example/django_apps/demo_three").resolve()),
        ],
        specification=spec,
    )
    print("Demo #3 (transfer - POST)")
    print_fuzzing_result_default_formatting(result)


def run_demo_five_spec_based_corpus() -> None:
    openapi_spec_dict = {
        "openapi": "3.0.0",
        "info": {"title": "Demo", "version": "1.0.0"},
        "paths": {
            "/quantity": {
                "get": {
                    "operationId": "getQuantity",
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "201": {"description": "Created"},
                        "400": {"description": "Bad Request"},
                    },
                }
            }
        },
    }
    spec = parse_openapi_schema(openapi_spec_dict)
    result = run_fuzzer(
        target=parse_quantity_view,
        initial_corpus=[],
        mutator=create_generic_mutator(),
        iterations=5000,
        executor=DjangoClientExecutor(settings_module=DEMO_SETTINGS, openapi_spec=spec),
        coverage_include_paths=[
            str(Path("src/django_example/django_apps/demo_one").resolve()),
        ],
        specification=spec,
    )
    print_fuzzing_result_default_formatting(result)


def run_demo_four_openapi_mismatch() -> None:
    openapi_spec_dict = {
        "openapi": "3.0.0",
        "info": {"title": "Demo", "version": "1.0.0"},
        "paths": {
            "/quantity": {
                "get": {
                    "operationId": "getQuantity",
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Created"},
                        "400": {"description": "Bad Request"},
                    },
                }
            }
        },
    }
    spec = parse_openapi_schema(openapi_spec_dict)
    result = run_fuzzer(
        target=parse_quantity_view,
        initial_corpus=[
            _make_single_param_get_request("/quantity", "q", v)
            for v in ["12", "5", "3"]
        ],
        mutator=create_generic_mutator(),
        iterations=50,
        executor=DjangoClientExecutor(settings_module=DEMO_SETTINGS, openapi_spec=spec),
        coverage_include_paths=[
            str(Path("src/django_example/django_apps/demo_one").resolve()),
        ],
    )
    print("Demo #4 (OpenAPI status code mismatch)")
    print_fuzzing_result_default_formatting(result)


def main() -> None:
    run_demo_one()
    run_demo_two()
    run_demo_three()
    run_demo_four_openapi_mismatch()
    run_demo_five_spec_based_corpus()


if __name__ == "__main__":
    main()
