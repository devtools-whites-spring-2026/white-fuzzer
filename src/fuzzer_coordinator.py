import inspect
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.coverage import BaseCoverage, Coverage
from src.executor import ExecutionResult, run_target
from src.mutator import Mutator


@dataclass
class FuzzingResult:
    tests_to_report: dict[str, ExecutionResult]
    coverage_report: dict
    function_coverage: tuple[int, int, float]


def _get_target_function_coverage(
    target: Callable[[str], Any], coverage_collector: BaseCoverage
) -> tuple[int, int, float]:
    target_file = inspect.getsourcefile(target)
    source_lines, start_line = inspect.getsourcelines(target)
    function_total_lines = {
        start_line + index
        for index, line in enumerate(source_lines)
        if line.strip() and not line.strip().startswith("#")
    }
    function_covered_lines: set[int] = set()

    if target_file is not None:
        target_path = str(Path(target_file))
        function_covered_lines = {
            line_number
            for filename, line_number in coverage_collector.get_coverage()
            if filename == target_path and line_number in function_total_lines
        }

    function_total = len(function_total_lines)
    function_covered = len(function_covered_lines)
    function_percent = (
        round(function_covered / function_total * 100, 2)
        if function_total
        else 0.0
    )

    return function_covered, function_total, function_percent


def orchestrate_fuzzing(
    target: Callable[[str], Any],
    initial_corpus: list[str],
    mutator: Mutator,
    iterations: int = 1000,
    coverage_collector: BaseCoverage | None = None,
) -> FuzzingResult:
    coverage_collector = coverage_collector or Coverage()
    coverage_collector.reset()

    seeds = range(iterations)
    corpus = initial_corpus
    tests_to_report: dict[str, ExecutionResult] = {}
    for seed in seeds:
        random.seed(seed)
        test = random.choice(corpus)
        mutated_test = mutator.mutate(test)
        exec_result = run_target(target, mutated_test, coverage_collector)
        if exec_result.thrown_exception is not None:
            tests_to_report[mutated_test] = exec_result
            if random.randint(0, 1000):
                corpus.append(mutated_test)

    coverage_report = coverage_collector.get_stats()
    function_coverage = _get_target_function_coverage(
        target, coverage_collector
    )
    return FuzzingResult(tests_to_report, coverage_report, function_coverage)
