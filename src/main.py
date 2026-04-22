import argparse
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.coverage_benchmark import run_coverage_benchmark
from src.fuzzer_coordinator import orchestrate_fuzzing
from src.mutator import RandomCharMutator


def load_module_from_path(path: str):
    spec = importlib.util.spec_from_file_location("target_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["target_module"] = module
    spec.loader.exec_module(module)
    return module


def resolve_target_function(
    module, function_name: str | None
) -> Callable[[str], Any]:
    if function_name:
        if not hasattr(module, function_name):
            raise ValueError(f"Function '{function_name}' not found in module")
        return getattr(module, function_name)

    # fuzz main by default
    if hasattr(module, "main"):
        return module.main

    raise ValueError("No function specified and no main() found")


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
        "--benchmark-coverage",
        action="store_true",
        help=(
            "Benchmark coverage collectors "
            "(sys.monitoring vs sys.settrace)"
        ),
    )

    parser.add_argument(
        "--benchmark-iterations",
        nargs="+",
        type=int,
        default=[100, 1000, 10000, 100000, 1000000],
        help="Iteration counts to use for coverage benchmark",
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

    return parser.parse_args()


def main():
    args = parse_args()

    path = Path(args.target)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    module = load_module_from_path(str(path))
    target_func = resolve_target_function(module, args.function)

    # We can extend this with multiple mutators in the future
    mutator = RandomCharMutator()

    if args.seed is not None:
        import random

        random.seed(args.seed)

    results = orchestrate_fuzzing(
        target=target_func,
        initial_corpus=list(args.input),
        mutator=mutator,
    )

    if not results:
        print("No crashes found")
    else:
        print(results)

    if args.benchmark_coverage:
        benchmark_samples = run_coverage_benchmark(
            target=target_func,
            initial_corpus=list(args.input),
            mutator=mutator,
            iteration_counts=args.benchmark_iterations,
        )
        print("\nCoverage benchmark:")
        print("iterations | monitoring    | settrace    | settrace/monitoring")
        for sample in benchmark_samples:
            print(
                f"{sample.iterations:10d} | "
                f"{sample.monitoring_seconds:13.6f} | "
                f"{sample.settrace_seconds:11.6f} | "
                f"{sample.slowdown_ratio:20.2f}x"
            )


if __name__ == "__main__":
    main()
