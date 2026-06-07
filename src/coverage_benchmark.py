import inspect
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from src.coverage_tracker import CoverageTracker
from src.executor import run_target
from src.mutator import Mutator


@dataclass
class BenchmarkSample:
    iterations: int
    elapsed_seconds: float
    iters_per_second: float


def _make_collector(target: Callable[[str], Any]) -> CoverageTracker:
    target_file = inspect.getsourcefile(target)
    include_paths = [str(Path(target_file))] if target_file is not None else None
    return CoverageTracker(include_paths=include_paths, branch=False)


def _run_single_benchmark(
    target: Callable[[str], Any],
    initial_corpus: list[str],
    mutator: Mutator,
    iterations: int,
) -> float:
    coverage_collector = _make_collector(target)
    corpus = list(initial_corpus)

    coverage_collector.start()
    start = perf_counter()
    for index in range(iterations):
        sample = corpus[index % len(corpus)]
        mutated_test = mutator.mutate(sample)
        run_target(target, mutated_test, coverage_collector)
    end = perf_counter()
    coverage_collector.stop()

    return end - start


def run_coverage_benchmark(
    target: Callable[[str], Any],
    initial_corpus: list[str],
    mutator: Mutator,
    iteration_counts: list[int],
) -> list[BenchmarkSample]:
    samples: list[BenchmarkSample] = []

    for iterations in iteration_counts:
        elapsed_seconds = _run_single_benchmark(
            target=target,
            initial_corpus=initial_corpus,
            mutator=mutator,
            iterations=iterations,
        )
        iters_per_second = iterations / elapsed_seconds if elapsed_seconds else 0.0
        samples.append(
            BenchmarkSample(
                iterations=iterations,
                elapsed_seconds=elapsed_seconds,
                iters_per_second=iters_per_second,
            )
        )

    return samples
