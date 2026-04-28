from __future__ import annotations

from src.fuzzer_coordinator import (
    orchestrate_fuzzing,
    orchestrate_greybox_fuzzing,
)
from src.mutator import Mutator


class PrefixStepMutator(Mutator):
    def mutate(self, arg: str) -> str:
        steps = {
            "": "A",
            "A": "AB",
            "AB": "ABC",
        }
        return steps.get(arg, arg)


def branching_target(value: str) -> None:
    if not value.startswith("A"):
        return

    if not value.startswith("AB"):
        return

    if not value.startswith("ABC"):
        return

    raise RuntimeError("deep branch reached")


def test_blackbox_does_not_retain_interesting_non_crashing_inputs() -> None:
    result = orchestrate_fuzzing(
        branching_target,
        [""],
        PrefixStepMutator(),
        iterations=20,
        seed=0,
    )

    assert not result.tests_to_report


def test_greybox_promotes_new_coverage_and_reaches_deep_branch() -> None:
    result = orchestrate_greybox_fuzzing(
        branching_target,
        [""],
        PrefixStepMutator(),
        iterations=20,
        seed=0,
    )

    assert "ABC" in result.tests_to_report
    assert any(
        item.new_coverage > 0 for item in result.tests_to_report.values()
    )
    assert len(result.corpus) > 1
