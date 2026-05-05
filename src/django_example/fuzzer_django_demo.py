from pathlib import Path

from src.django_example.django_apps.demo_one.views import parse_quantity_view
from src.django_example.django_apps.demo_two.views import coupon_check_view
from src.executor import DjangoClientExecutor
from src.fuzzer_coordinator import orchestrate_fuzzing
from src.main import print_fuzzing_result
from src.mutator import create_generic_mutator


def run_demo_one() -> None:
    result = orchestrate_fuzzing(
        target=parse_quantity_view,
        initial_corpus=[
            "12",
            "-5",
            "",
            "abc",
        ],
        mutator=create_generic_mutator(),
        iterations=100,
        executor=DjangoClientExecutor(
            settings_module="src.django_example.django_apps.demo_project.settings",
            request_builder=lambda input_str: (
                "GET",
                "/quantity",
                {"q": input_str},
            ),
        ),
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
            "SALE10",
            "WELCOME",
            "A/B",
            "LAST!",
        ],
        mutator=create_generic_mutator(),
        iterations=20,
        executor=DjangoClientExecutor(
            settings_module="src.django_example.django_apps.demo_project.settings",
            request_builder=lambda input_str: (
                "GET",
                "/coupon",
                {"coupon": input_str},
            ),
        ),
        coverage_include_paths=[
            str(Path("src/django_example/django_apps/demo_two").resolve()),
        ],
    )
    print("Demo #2 (coupon validator)")
    print_fuzzing_result(result)


def main() -> None:
    run_demo_one()
    # run_demo_two()


if __name__ == "__main__":
    main()
