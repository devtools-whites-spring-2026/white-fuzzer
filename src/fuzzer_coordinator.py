import inspect
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.coverage import Coverage
from src.executor import ExecutionResult, run_target
from src.mutator import Mutator


@dataclass
class FuzzingResult:
    tests_to_report: dict[str, ExecutionResult]
    coverage_report: dict
    function_coverage: tuple[int, int, float]
    corpus_size: int = 0


@dataclass
class CorpusEntry:
    value: str
    energy: int = 1


def _get_target_function_coverage(
    target: Callable[[str], Any], coverage_collector: Coverage
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


def _make_coverage_collector(target: Callable[[str], Any]) -> Coverage:
    target_file = inspect.getsourcefile(target)
    include_paths = (
        [str(Path(target_file))] if target_file is not None else None
    )
    return Coverage(include_paths=include_paths)


def _target_coverage(
    target: Callable[[str], Any], coverage_collector: Coverage
) -> set[tuple[str, int]]:
    target_file = inspect.getsourcefile(target)
    if target_file is None:
        return set()

    target_path = str(Path(target_file))
    return {
        line
        for line in coverage_collector.get_coverage()
        if line[0] == target_path
    }


def _energy_for_new_coverage(new_lines: set[tuple[str, int]]) -> int:
    return min(32, 1 + len(new_lines) * 4)


def orchestrate_fuzzing(
    target: Callable[[str], Any],
    initial_corpus: list[str],
    mutator: Mutator,
    iterations: int = 1000,
    seed: int | None = None,
) -> FuzzingResult:
    coverage_collector = _make_coverage_collector(target)
    coverage_collector.reset()

    if seed is not None:
        random.seed(seed)

    corpus = initial_corpus
    tests_to_report: dict[str, ExecutionResult] = {}
    for _ in range(iterations):
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
    return FuzzingResult(
        tests_to_report, coverage_report, function_coverage, len(corpus)
    )


def orchestrate_greybox_fuzzing(
    target: Callable[[str], Any],
    initial_corpus: list[str],
    mutator: Mutator,
    iterations: int = 1000,
    seed: int | None = None,
) -> FuzzingResult:
    coverage_collector = _make_coverage_collector(target)
    coverage_collector.reset()

    if seed is not None:
        random.seed(seed)

    corpus = [CorpusEntry(value=item) for item in initial_corpus]
    tests_to_report: dict[str, ExecutionResult] = {}
    known_target_coverage: set[tuple[str, int]] = set()

    for item in initial_corpus:
        before = set(_target_coverage(target, coverage_collector))
        exec_result = run_target(target, item, coverage_collector)
        after = set(_target_coverage(target, coverage_collector))
        new_lines = after - before - known_target_coverage
        if new_lines:
            exec_result.new_coverage = len(new_lines)
            tests_to_report[item] = exec_result
        if exec_result.thrown_exception is not None:
            tests_to_report[item] = exec_result
        known_target_coverage |= new_lines

    for _ in range(iterations):
        weights = [entry.energy for entry in corpus]
        entry = random.choices(corpus, weights=weights, k=1)[0]
        mutated_test = mutator.mutate(entry.value)

        before = set(_target_coverage(target, coverage_collector))
        exec_result = run_target(target, mutated_test, coverage_collector)
        after = set(_target_coverage(target, coverage_collector))

        if exec_result.thrown_exception is not None:
            tests_to_report[mutated_test] = exec_result

        new_lines = after - before - known_target_coverage
        if new_lines:
            exec_result.new_coverage = len(new_lines)
            tests_to_report[mutated_test] = exec_result
            known_target_coverage |= new_lines
            corpus.append(
                CorpusEntry(
                    value=mutated_test,
                    energy=_energy_for_new_coverage(new_lines),
                )
            )

    coverage_report = coverage_collector.get_stats()
    function_coverage = _get_target_function_coverage(
        target, coverage_collector
    )
    return FuzzingResult(
        tests_to_report, coverage_report, function_coverage, len(corpus)
    )
