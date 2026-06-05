from pathlib import Path

from src.django_example.django_apps.demo_one.views import parse_quantity_view
from src.django_example.django_apps.demo_three.views import transfer_view
from src.django_example.django_apps.demo_two.views import coupon_check_view
from src.executor import DjangoClientExecutor
from src.fuzzer_coordinator import orchestrate_fuzzing
from src.main import print_fuzzing_result
from src.mutatable_request import (
    MutatableField,
    MutatableRestRequest,
    StringWithMutablePlaceholders,
)
from src.mutator import create_generic_mutator

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
    result = orchestrate_fuzzing(
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
    print_fuzzing_result(result)


def run_demo_two() -> None:
    result = orchestrate_fuzzing(
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
    print_fuzzing_result(result)


def run_demo_three() -> None:
    result = orchestrate_fuzzing(
        target=transfer_view,
        initial_corpus=[
            MutatableRestRequest(
                request_type="POST",
                url="/transfer",
                data=StringWithMutablePlaceholders(
                    data='{"from": "<from>", "to": "<to>", "amount": "<amount>"}',
                    placeholders=[
                        MutatableField("<from>", "Alice"),
                        MutatableField("<to>", "Bob"),
                        MutatableField("<amount>", "100"),
                    ],
                ),
            ),
        ],
        mutator=create_generic_mutator(),
        iterations=200,
        executor=DjangoClientExecutor(settings_module=DEMO_SETTINGS),
        coverage_include_paths=[
            str(Path("src/django_example/django_apps/demo_three").resolve()),
        ],
    )
    print("Demo #3 (transfer - POST)")
    print_fuzzing_result(result)


def main() -> None:
    run_demo_one()
    run_demo_two()
    run_demo_three()


if __name__ == "__main__":
    main()
