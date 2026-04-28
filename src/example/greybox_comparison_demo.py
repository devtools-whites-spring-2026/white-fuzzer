from src.example.complex_protocol import analyze_protocol_message
from src.example.parse_http_header import parse_http_header
from src.fuzzer_coordinator import (
    FuzzingResult,
    orchestrate_fuzzing,
    orchestrate_greybox_fuzzing,
)
from src.mutator import (
    create_generic_mutator,
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
        if exec_result.thrown_exception is None:
            print(f"      New coverage: +{exec_result.new_coverage} lines")
        else:
            name = type(exec_result.thrown_exception).__name__
            print(f"      Exception: {name}: {exec_result.thrown_exception}")
    print()
    print("=====================")


def main() -> None:
    mutator = create_generic_mutator()
    result = orchestrate_fuzzing(
        parse_http_header,
        [
            "Content-Type: text/html",
            "Authorization: Bearer token123",
            "X-Request-Id: abc",
        ],
        mutator,
        iterations=500000,
    )
    print_fuzzing_result(result)

    greybox_result = orchestrate_greybox_fuzzing(
        analyze_protocol_message,
        [
            "WFZ/1 token=greybox; mode=deep; stage=7; checksum=11; action=ping",
        ],
        mutator,
        iterations=1000,
    )
    print_fuzzing_result(greybox_result)


if __name__ == "__main__":
    main()
