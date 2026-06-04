import inspect
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, NamedTuple, TypeVar, cast

from src.coverage_tracker import CoverageTracker
from src.executor import ExecutionResult, Executor, FunctionExecutor
from src.mutator import Mutatable, Mutator

T = TypeVar("T", bound=Mutatable)


@dataclass
class FuzzingResult(Generic[T]):
    tests_to_report: dict[T, ExecutionResult]
    coverage_report: dict
    function_coverage: tuple[int, int, float]
    corpus: list[T]
    coverage_collector: CoverageTracker | None = None


class CoveredLine(NamedTuple):
    filename: str
    line_number: int


@dataclass
class CorpusEntry(Generic[T]):
    value: T
    energy: int = 1


def _get_target_function_coverage(
    target: Callable[[str], Any], coverage_collector: CoverageTracker
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
        file_coverage = coverage_collector.get_coverage_of(target_path)
        function_covered_lines = file_coverage & function_total_lines

    function_total = len(function_total_lines)
    function_covered = len(function_covered_lines)
    function_percent = (
        round(function_covered / function_total * 100, 2) if function_total else 0.0
    )

    return function_covered, function_total, function_percent


def _make_coverage_collector(
    target: Callable[[str], Any], include_paths: list[str] | None = None
) -> CoverageTracker:
    if include_paths is not None:
        return CoverageTracker(include_paths=include_paths)

    target_file = inspect.getsourcefile(target)
    include_paths = [str(Path(target_file))] if target_file is not None else None
    return CoverageTracker(include_paths=include_paths)


def _target_coverage(
    target: Callable[[str], Any], coverage_collector: CoverageTracker
) -> set[CoveredLine]:
    target_file = inspect.getsourcefile(target)
    if target_file is None:
        return set()

    target_path = str(Path(target_file))
    file_coverage = coverage_collector.get_coverage_of(target_path)
    return {CoveredLine(target_path, line_number) for line_number in file_coverage}


def _energy_for_new_coverage(new_lines: set[CoveredLine]) -> int:
    return min(32, 1 + len(new_lines) * 4)


def _run_with_coverage_tracking(
    target: Callable[[str], Any],
    test_input: T,
    coverage_collector: CoverageTracker,
    known_target_coverage: set[CoveredLine],
    executor: Executor[T],
) -> tuple[ExecutionResult, set[CoveredLine]]:
    before = _target_coverage(target, coverage_collector)
    exec_result = executor.execute(test_input, coverage_collector)
    after = _target_coverage(target, coverage_collector)
    new_lines = after - before - known_target_coverage
    if new_lines:
        exec_result.new_coverage = len(new_lines)
    return exec_result, new_lines


def orchestrate_fuzzing(
    target: Callable[[str], Any],
    initial_corpus: list[T],
    mutator: Mutator,
    iterations: int = 1000,
    seed: int | None = None,
    executor: Executor[T] | None = None,
    coverage_include_paths: list[str] | None = None,
) -> FuzzingResult[T]:
    coverage_collector = _make_coverage_collector(target, coverage_include_paths)
    coverage_collector.reset()
    active_executor: Executor[T] = executor or cast(
        "Executor[T]", FunctionExecutor(target)
    )

    if seed is not None:
        random.seed(seed)

    corpus = initial_corpus
    tests_to_report: dict[T, ExecutionResult] = {}
    for i in range(iterations):
        print(f"\rFuzzing progress: {i + 1}/{iterations}", end="")

        test = random.choice(corpus)
        mutated_test = test.apply_mutator(mutator)
        exec_result = active_executor.execute(mutated_test, coverage_collector)

        if exec_result.thrown_exception is not None:
            tests_to_report[mutated_test] = exec_result
            if random.randint(0, 1000):
                corpus.append(mutated_test)

    print(f"\rFuzzing progress: {iterations}/{iterations}")

    coverage_report = coverage_collector.get_stats()
    function_coverage = _get_target_function_coverage(target, coverage_collector)
    return FuzzingResult(
        tests_to_report,
        coverage_report,
        function_coverage,
        corpus,
        coverage_collector=coverage_collector,
    )


def orchestrate_greybox_fuzzing(
    target: Callable[[str], Any],
    initial_corpus: list[T],
    mutator: Mutator,
    iterations: int = 1000,
    seed: int | None = None,
    executor: Executor[T] | None = None,
    coverage_include_paths: list[str] | None = None,
) -> FuzzingResult[T]:
    coverage_collector = _make_coverage_collector(target, coverage_include_paths)
    coverage_collector.reset()
    active_executor: Executor[T] = executor or cast(
        "Executor[T]", FunctionExecutor(target)
    )

    if seed is not None:
        random.seed(seed)

    corpus: list[CorpusEntry[T]] = [CorpusEntry(value=item) for item in initial_corpus]
    tests_to_report: dict[T, ExecutionResult] = {}
    known_target_coverage: set[CoveredLine] = set()

    for item in initial_corpus:
        exec_result, new_lines = _run_with_coverage_tracking(
            target,
            item,
            coverage_collector,
            known_target_coverage,
            active_executor,
        )
        if new_lines:
            tests_to_report[item] = exec_result
        if exec_result.thrown_exception is not None:
            tests_to_report[item] = exec_result
        known_target_coverage |= new_lines

    for _ in range(iterations):
        weights = [entry.energy for entry in corpus]
        entry = random.choices(corpus, weights=weights, k=1)[0]
        mutated_test = entry.value.apply_mutator(mutator)

        exec_result, new_lines = _run_with_coverage_tracking(
            target,
            mutated_test,
            coverage_collector,
            known_target_coverage,
            active_executor,
        )

        if exec_result.thrown_exception is not None:
            tests_to_report[mutated_test] = exec_result

        if new_lines:
            tests_to_report[mutated_test] = exec_result
            known_target_coverage |= new_lines
            corpus.append(
                CorpusEntry(
                    value=mutated_test,
                    energy=_energy_for_new_coverage(new_lines),
                )
            )

    coverage_report = coverage_collector.get_stats()
    function_coverage = _get_target_function_coverage(target, coverage_collector)
    return FuzzingResult(
        tests_to_report,
        coverage_report,
        function_coverage,
        [entry.value for entry in corpus],
        coverage_collector=coverage_collector,
    )
