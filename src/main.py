import argparse
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.fuzzer_coordinator import (
    FuzzingResult,
    orchestrate_fuzzing,
    orchestrate_greybox_fuzzing,
)
from src.mutator import MutatableString, create_generic_mutator
from src.analysis_writer import save_analysis, load_corpus_from_analysis


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
        if exec_result.status_code is not None:
            print(f"       Status code: {exec_result.status_code}")
        if exec_result.curl_command is not None:
            print(f"       curl: {exec_result.curl_command}")
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
        default=["hello"],
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
        "--save-analysis",
        default=None,
        metavar="FILE",
        help="Save analysis to JSON file",
    )

    parser.add_argument(
        "--resume-from",
        default=None,
        metavar="FILE",
        help="Load analysis from JSON and continue",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    path = Path(args.target)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    module = load_module_from_path(str(path))
    target_func = resolve_target_function(module, args.function)

    mutator = create_generic_mutator()

    initial_corpus: list[MutatableString] = [MutatableString(s) for s in args.input]
    if args.resume_from:
        try:
            resumed = load_corpus_from_analysis(args.resume_from)
            initial_corpus = resumed + initial_corpus
            print(f"Loaded {len(resumed)} corpus entries from {args.resume_from}")
        except Exception as e:
            print(f"Warning: could not load corpus from {args.resume_from}: {e}")

    orchestrator = orchestrate_greybox_fuzzing if args.greybox else orchestrate_fuzzing
    results = orchestrator(
        target=target_func,
        initial_corpus=initial_corpus,
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

    if args.save_analysis:
        mode = "greybox" if args.greybox else "blackbox"
        save_analysis(
            results,
            args.save_analysis,
            seed=args.seed,
            iterations=args.iterations,
            target=str(path),
            mode=mode,
        )
        print(f"Analysis saved to {args.save_analysis}")


if __name__ == "__main__":
    main()
