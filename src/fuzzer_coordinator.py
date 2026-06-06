import inspect
import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Generic, NamedTuple, TypeVar, cast

from src.coverage_tracker import CoverageTracker
from src.executor import ExecutionResult, Executor, FunctionExecutor
from src.mutator import Mutatable, Mutator
from src.openapi_schema import EndpointSchema, request_schema_to_mutatable

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


def _input_fingerprint(value: Mutatable) -> str:
    return repr(value)


def _deduplicate_inputs(values: Iterable[T]) -> tuple[list[T], set[str]]:
    deduplicated: list[T] = []
    fingerprints: set[str] = set()
    for value in values:
        fingerprint = _input_fingerprint(value)
        if fingerprint in fingerprints:
            continue
        deduplicated.append(value)
        fingerprints.add(fingerprint)
    return deduplicated, fingerprints


def _record_test_to_report(
    tests_to_report: dict[T, ExecutionResult],
    reported_fingerprints: set[str],
    test_input: T,
    exec_result: ExecutionResult,
    run_coverage: set[CoveredLine],
) -> None:
    fingerprint = _finding_fingerprint(exec_result, run_coverage)
    if fingerprint in reported_fingerprints:
        return
    tests_to_report[test_input] = exec_result
    reported_fingerprints.add(fingerprint)


def _target_run_coverage(
    target: Callable[[str], Any], coverage_collector: CoverageTracker
) -> set[CoveredLine]:
    target_file = inspect.getsourcefile(target)
    if target_file is None:
        return set()

    target_path = str(Path(target_file))
    covered_lines = coverage_collector.get_last_run_coverage().get(target_path)
    if covered_lines is None:
        return set()
    return {CoveredLine(target_path, line_number) for line_number in covered_lines}


def _exception_signature(exec_result: ExecutionResult) -> tuple[str, ...]:
    exception = exec_result.thrown_exception
    if exception is None:
        return ("no-exception",)

    exception_type = type(exception)
    frames = (
        line.strip()
        for line in (exec_result.traceback_text or "").splitlines()
        if line.strip().startswith("File ")
    )
    return (
        f"{exception_type.__module__}.{exception_type.__qualname__}",
        *frames,
    )


def _finding_fingerprint(
    exec_result: ExecutionResult, run_coverage: set[CoveredLine]
) -> str:
    payload = "\n".join(
        (
            *_exception_signature(exec_result),
            *(
                f"{covered_line.filename}:{covered_line.line_number}"
                for covered_line in sorted(run_coverage)
            ),
        )
    )
    return sha256(payload.encode()).hexdigest()


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
    target: Callable[[str], Any],
    include_paths: list[str] | None = None,
    branch: bool = False,
) -> CoverageTracker:
    if include_paths is not None:
        return CoverageTracker(include_paths=include_paths, branch=branch)

    target_file = inspect.getsourcefile(target)
    include_paths = [str(Path(target_file))] if target_file is not None else None
    return CoverageTracker(include_paths=include_paths, branch=branch)


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
) -> tuple[ExecutionResult, set[CoveredLine], set[CoveredLine]]:
    before = _target_coverage(target, coverage_collector)
    coverage_collector.start()
    exec_result = executor.execute(test_input, coverage_collector)
    coverage_collector.stop()
    after = _target_coverage(target, coverage_collector)
    new_lines = after - before - known_target_coverage
    if new_lines:
        exec_result.new_coverage = len(new_lines)
    return exec_result, new_lines, _target_run_coverage(target, coverage_collector)


def orchestrate_fuzzing(
    target: Callable[[str], Any],
    initial_corpus: list[T],
    mutator: Mutator,
    iterations: int = 1000,
    seed: int | None = None,
    executor: Executor[T] | None = None,
    coverage_include_paths: list[str] | None = None,
    branch: bool = False,
    specification: list[EndpointSchema] | None = None,
) -> FuzzingResult[T]:
    coverage_collector = _make_coverage_collector(
        target, coverage_include_paths, branch=branch
    )
    coverage_collector.reset()
    active_executor: Executor[T] = executor or cast(
        "Executor[T]", FunctionExecutor(target)
    )

    if seed is not None:
        random.seed(seed)

    corpus = initial_corpus
    if specification is not None:
        for endpoint_schema in specification:
            samples_from_spec = request_schema_to_mutatable(endpoint_schema)
            corpus += cast("list[T]", samples_from_spec)

    corpus, corpus_fingerprints = _deduplicate_inputs(corpus)
    tests_to_report: dict[T, ExecutionResult] = {}
    reported_fingerprints: set[str] = set()
    for i in range(iterations):
        print(f"\rFuzzing progress: {i + 1}/{iterations}", end="")

        test = random.choice(corpus)
        mutated_test = test.apply_mutator(mutator)
        coverage_collector.start()
        exec_result = active_executor.execute(mutated_test, coverage_collector)
        coverage_collector.stop()
        run_coverage = _target_run_coverage(target, coverage_collector)

        if exec_result.thrown_exception is not None:
            _record_test_to_report(
                tests_to_report,
                reported_fingerprints,
                mutated_test,
                exec_result,
                run_coverage,
            )
            fingerprint = _input_fingerprint(mutated_test)
            if fingerprint not in corpus_fingerprints and random.randint(0, 1000):
                corpus.append(mutated_test)
                corpus_fingerprints.add(fingerprint)

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
    branch: bool = False,
) -> FuzzingResult[T]:
    coverage_collector = _make_coverage_collector(
        target, coverage_include_paths, branch=branch
    )
    coverage_collector.reset()
    active_executor: Executor[T] = executor or cast(
        "Executor[T]", FunctionExecutor(target)
    )

    if seed is not None:
        random.seed(seed)

    deduplicated_initial_corpus, corpus_fingerprints = _deduplicate_inputs(
        initial_corpus
    )
    corpus: list[CorpusEntry[T]] = [
        CorpusEntry(value=item) for item in deduplicated_initial_corpus
    ]
    tests_to_report: dict[T, ExecutionResult] = {}
    reported_fingerprints: set[str] = set()
    known_target_coverage: set[CoveredLine] = set()

    for item in deduplicated_initial_corpus:
        exec_result, new_lines, run_coverage = _run_with_coverage_tracking(
            target,
            item,
            coverage_collector,
            known_target_coverage,
            active_executor,
        )
        if new_lines:
            _record_test_to_report(
                tests_to_report,
                reported_fingerprints,
                item,
                exec_result,
                run_coverage,
            )
        if exec_result.thrown_exception is not None:
            _record_test_to_report(
                tests_to_report,
                reported_fingerprints,
                item,
                exec_result,
                run_coverage,
            )
        known_target_coverage |= new_lines

    for _ in range(iterations):
        weights = [entry.energy for entry in corpus]
        entry = random.choices(corpus, weights=weights, k=1)[0]
        mutated_test = entry.value.apply_mutator(mutator)

        exec_result, new_lines, run_coverage = _run_with_coverage_tracking(
            target,
            mutated_test,
            coverage_collector,
            known_target_coverage,
            active_executor,
        )

        if exec_result.thrown_exception is not None:
            _record_test_to_report(
                tests_to_report,
                reported_fingerprints,
                mutated_test,
                exec_result,
                run_coverage,
            )

        if new_lines:
            _record_test_to_report(
                tests_to_report,
                reported_fingerprints,
                mutated_test,
                exec_result,
                run_coverage,
            )
            known_target_coverage |= new_lines
            fingerprint = _input_fingerprint(mutated_test)
            if fingerprint not in corpus_fingerprints:
                corpus.append(
                    CorpusEntry(
                        value=mutated_test,
                        energy=_energy_for_new_coverage(new_lines),
                    )
                )
                corpus_fingerprints.add(fingerprint)

    coverage_report = coverage_collector.get_stats()
    function_coverage = _get_target_function_coverage(target, coverage_collector)
    return FuzzingResult(
        tests_to_report,
        coverage_report,
        function_coverage,
        [entry.value for entry in corpus],
        coverage_collector=coverage_collector,
    )
