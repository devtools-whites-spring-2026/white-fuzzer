# from typeguard import install_import_hook

# install_import_hook()
from src.fuzzer_coordinator import FuzzingResult, orchestrate_fuzzing
from src.mutator import (
    DeleteCharMutator,
    InsertCharMutator,
    Mutator,
    RandomCharMutator,
    RepeatMutator,
    SelectionMutator,
)
from src.parse_http_header import parse_http_header


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
    print()
    print("=====================")


def main() -> None:
    mutators: list[Mutator] = [
        RandomCharMutator(),
        DeleteCharMutator(),
        InsertCharMutator(),
    ]
    selection_mutator = SelectionMutator(mutators)
    repeat_mutator = RepeatMutator(selection_mutator)
    result = orchestrate_fuzzing(
        parse_http_header,
        [
            "Content-Type: text/html",
            "Authorization: Bearer token123",
            "X-Request-Id: abc",
        ],
        repeat_mutator,
        iterations=500000,
    )
    print_fuzzing_result(result)


if __name__ == "__main__":
    main()
