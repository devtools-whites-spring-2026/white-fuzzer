from pathlib import Path

from src.django_example.django_apps.demo_one.views import parse_quantity_view
from src.django_example.django_apps.demo_two.views import coupon_check_view
from src.executor import DjangoClientExecutor
from src.fuzzer_coordinator import FuzzingResult, orchestrate_fuzzing
from src.mutator import (
    DeleteCharMutator,
    InsertCharMutator,
    Mutator,
    RandomCharMutator,
    RepeatMutator,
    SelectionMutator,
)


def print_fuzzing_result(result: FuzzingResult) -> None:
    cr = result.coverage_report
    fc, ft, fp = result.function_coverage
    findings = {
        k: v
        for k, v in result.tests_to_report.items()
        if not isinstance(v.thrown_exception, ValueError)
    }

    print("=== Fuzzing Report ===")
    print()
    covered = cr["covered"]
    total = cr["total"]
    percent = cr["percent"]
    print(f"Coverage:          {covered}/{total} lines ({percent}%)")
    print(f"Function coverage: {fc}/{ft} lines ({fp}%)")
    print()
    print(f"Findings: {len(findings)}")
    for i, (input_str, exec_result) in enumerate(findings.items(), start=1):
        print(f"  [{i}] Input:     {input_str!r}")
        name = type(exec_result.thrown_exception).__name__
        print(f"      Exception: {name}: {exec_result.thrown_exception}")
        if exec_result.traceback_text:
            print("      Traceback:")
            for line in exec_result.traceback_text.rstrip().splitlines():
                print(f"        {line}")
    print()
    print("=====================")


def _build_mutator() -> Mutator:
    mutators: list[Mutator] = [
        RandomCharMutator(),
        DeleteCharMutator(),
        InsertCharMutator(),
    ]
    selection_mutator = SelectionMutator(mutators)
    return RepeatMutator(selection_mutator)


def run_demo_one() -> None:
    result = orchestrate_fuzzing(
        target=parse_quantity_view,
        initial_corpus=[
            "12",
            "-5",
            "",
            "abc",
        ],
        mutator=_build_mutator(),
        iterations=20,
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
        mutator=_build_mutator(),
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
    run_demo_two()


if __name__ == "__main__":
    main()
