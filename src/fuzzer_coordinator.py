import random
from collections.abc import Callable
from typing import Any

from src.coverage import Coverage
from src.executor import ExecutionResult, run_target
from src.mutator import Mutator


def orchestrate_fuzzing(
    target: Callable[[str], Any],
    initial_corpus: list[str],
    mutator: Mutator,
) -> dict[(str, ExecutionResult)]:
    coverage_collector = Coverage()
    coverage_collector.reset()

    seeds = range(100)
    corpus = initial_corpus
    tests_to_report: dict[(str, ExecutionResult)] = {}
    for seed in seeds:
        random.seed(seed)
        test = random.choice(corpus)
        mutated_test = mutator.mutate(test)
        exec_result = run_target(target, mutated_test, coverage_collector)
        if exec_result.thrown_exception is not None:
            tests_to_report[mutated_test] = exec_result
            corpus.append(mutated_test)

    coverage_report = coverage_collector.get_stats()
    print(
        f"Coverage report: {coverage_report['covered']}"
        f"/{coverage_report['total']} lines "
        f"({coverage_report['percent']}%)"
    )

    return tests_to_report
