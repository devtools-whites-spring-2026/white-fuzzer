from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from src.coverage import MonitoringCoverage, SetTraceCoverage
from src.executor import run_target
from src.mutator import Mutator


@dataclass
class BenchmarkSample:
    iterations: int
    monitoring_seconds: float
    settrace_seconds: float
    slowdown_ratio: float


def _run_single_benchmark(
    target: Callable[[str], Any],
    initial_corpus: list[str],
    mutator: Mutator,
    iterations: int,
    collector_factory: Callable[[], MonitoringCoverage | SetTraceCoverage],
) -> float:
    coverage_collector = collector_factory()
    corpus = list(initial_corpus)

    start = perf_counter()
    for index in range(iterations):
        sample = corpus[index % len(corpus)]
        mutated_test = mutator.mutate(sample)
        run_target(target, mutated_test, coverage_collector)
    end = perf_counter()

    return end - start


def run_coverage_benchmark(
    target: Callable[[str], Any],
    initial_corpus: list[str],
    mutator: Mutator,
    iteration_counts: list[int],
) -> list[BenchmarkSample]:
    samples: list[BenchmarkSample] = []

    for iterations in iteration_counts:
        monitoring_seconds = _run_single_benchmark(
            target=target,
            initial_corpus=initial_corpus,
            mutator=mutator,
            iterations=iterations,
            collector_factory=MonitoringCoverage,
        )
        settrace_seconds = _run_single_benchmark(
            target=target,
            initial_corpus=initial_corpus,
            mutator=mutator,
            iterations=iterations,
            collector_factory=SetTraceCoverage,
        )
        slowdown_ratio = (
            (settrace_seconds / monitoring_seconds)
            if monitoring_seconds
            else 0.0
        )
        samples.append(
            BenchmarkSample(
                iterations=iterations,
                monitoring_seconds=monitoring_seconds,
                settrace_seconds=settrace_seconds,
                slowdown_ratio=slowdown_ratio,
            )
        )

    return samples
