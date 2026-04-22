import argparse
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.coverage_benchmark import BenchmarkSample, run_coverage_benchmark
from src.fuzzer_coordinator import (
    FuzzingResult,
    orchestrate_fuzzing,
    orchestrate_greybox_fuzzing,
)
from src.mutator import MutatableString, create_generic_mutator


def load_module_from_path(path: str):
    spec = importlib.util.spec_from_file_location("target_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["target_module"] = module
    spec.loader.exec_module(module)
    return module


def resolve_target_function(module, function_name: str | None) -> Callable[[str], Any]:
    if function_name:
        if not hasattr(module, function_name):
            raise ValueError(f"Function '{function_name}' not found in module")
        return getattr(module, function_name)

    # fuzz main by default
    if hasattr(module, "main"):
        return module.main

    raise ValueError("No function specified and no main() found")


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
    if cr.get("branches_total"):
        bc = cr["branches_covered"]
        bt = cr["branches_total"]
        bp = cr["branches_percent"]
        print(f"Branch coverage:   {bc}/{bt} branches ({bp}%)")
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


def parse_args():
    parser = argparse.ArgumentParser(description="Fuzzer CLI")

    parser.add_argument("target", help="Path to python file to fuzz")

    parser.add_argument(
        "--function",
        help="Function name to fuzz (default: main)",
        default=None,
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--input",
        nargs="+",
        default=["Content-Type: text/html"],
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
    )

    parser.add_argument(
        "--greybox",
        action="store_true",
    )

    parser.add_argument(
        "--report",
        default=None,
        help="Comma-separated report formats: html,json,xml,lcov",
    )

    parser.add_argument(
        "--report-dir",
        default="./reports",
        help="Directory to write coverage reports to (default: ./reports)",
    )

    parser.add_argument(
        "--branch",
        action="store_true",
        help="Collect branch coverage in addition to line coverage",
    )

    parser.add_argument(
        "--benchmark-coverage",
        action="store_true",
        help="Run coverage collection benchmark at varying iteration counts",
    )

    parser.add_argument(
        "--benchmark-iterations",
        nargs="+",
        type=int,
        default=[100, 1000, 10000, 100000, 1000000],
        help="Iteration counts to use for coverage benchmark",
    )

    return parser.parse_args()


def print_benchmark_samples(samples: list[BenchmarkSample]) -> None:
    print()
    print("=== Coverage benchmark ===")
    print("iterations | seconds       | iters/sec")
    for sample in samples:
        print(
            f"{sample.iterations:10d} | "
            f"{sample.elapsed_seconds:13.6f} | "
            f"{sample.iters_per_second:12.1f}"
        )
    print("==========================")


def main():
    args = parse_args()

    path = Path(args.target)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    module = load_module_from_path(str(path))
    target_func = resolve_target_function(module, args.function)

    mutator = create_generic_mutator()

    orchestrator = orchestrate_greybox_fuzzing if args.greybox else orchestrate_fuzzing
    results = orchestrator(
        target=target_func,
        initial_corpus=[MutatableString(s) for s in args.input],
        mutator=mutator,
        iterations=args.iterations,
        seed=args.seed,
        branch=args.branch,
    )

    print_fuzzing_result(results)

    if args.report and results.coverage_collector is not None:
        formats = [f.strip() for f in args.report.split(",") if f.strip()]
        results.coverage_collector.export(args.report_dir, formats)
        print(f"Reports written to {args.report_dir}")

    if args.benchmark_coverage:
        samples = run_coverage_benchmark(
            target=target_func,
            initial_corpus=list(args.input),
            mutator=mutator,
            iteration_counts=args.benchmark_iterations,
        )
        print_benchmark_samples(samples)


if __name__ == "__main__":
    main()
