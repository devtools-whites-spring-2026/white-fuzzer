import random
from collections.abc import Callable
from typing import Any

from src.executor import ExecutionResult, run_target
from src.mutator import Mutator


def orchestrate_fuzzing(
    target: Callable[[str], Any],
    initial_corpus: list[str],
    mutator: Mutator,
) -> dict[(str, ExecutionResult)]:
    seeds = range(100)
    corpus = initial_corpus
    tests_to_report: dict[(str, ExecutionResult)] = {}
    for seed in seeds:
        random.seed(seed)
        test = random.choice(corpus)
        mutated_test = mutator.mutate(test)
        exec_result = run_target(target, mutated_test)
        if exec_result.thrown_exception is not None:
            tests_to_report[mutated_test] = exec_result
            corpus.append(mutated_test)
    return tests_to_report
