from __future__ import annotations

import inspect
from pathlib import Path

from src.coverage_tracker import CoverageTracker
from src.executor import ExecutionResult
from src.fuzzer_coordinator import (
    CoveredLine,
    _finding_fingerprint,
    orchestrate_fuzzing,
    orchestrate_greybox_fuzzing,
)
from src.mutator import MutatableString, Mutator


class PrefixStepMutator(Mutator):
    def mutate(self, arg: str) -> str:
        steps = {
            "": "A",
            "A": "AB",
            "AB": "ABC",
        }
        return steps.get(arg, arg)


class IdentityMutator(Mutator):
    def mutate(self, arg: str) -> str:
        return arg


class SequentialMutator(Mutator):
    def __init__(self, values: list[str]) -> None:
        self._values = values
        self._index = 0

    def mutate(self, arg: str) -> str:
        del arg
        value = self._values[self._index]
        self._index += 1
        return value


def branching_target(value: str) -> None:
    if not value.startswith("A"):
        return

    if not value.startswith("AB"):
        return

    if not value.startswith("ABC"):
        return

    raise RuntimeError("deep branch reached")


def always_crashes(_value: str) -> None:
    raise RuntimeError("duplicate crash")


def crashes_with_input_in_message(value: str) -> None:
    raise RuntimeError(f"bad value: {value}")


def crashes_on_distinct_paths(value: str) -> None:
    if value == "left":
        raise RuntimeError("same exception type and message")

    if value == "right":
        raise RuntimeError("same exception type and message")


def last_run_coverage_target(value: str) -> str:
    if value == "left":
        return "left"
    return "right"


def _line_number_with_text(function, text: str) -> int:
    lines, start_line = inspect.getsourcelines(function)
    return next(start_line + index for index, line in enumerate(lines) if text in line)


def test_blackbox_does_not_retain_interesting_non_crashing_inputs() -> None:
    result = orchestrate_fuzzing(
        branching_target,
        [MutatableString("")],
        PrefixStepMutator(),
        iterations=20,
        seed=0,
    )

    assert not result.tests_to_report


def test_blackbox_deduplicates_reported_tests_and_corpus() -> None:
    result = orchestrate_fuzzing(
        always_crashes,
        [MutatableString("same"), MutatableString("same")],
        IdentityMutator(),
        iterations=10,
        seed=0,
    )

    assert [repr(item) for item in result.tests_to_report] == ["same"]
    assert [repr(item) for item in result.corpus] == ["same"]


def test_blackbox_deduplicates_semantically_equivalent_crashes() -> None:
    result = orchestrate_fuzzing(
        crashes_with_input_in_message,
        [MutatableString("")],
        SequentialMutator(["first", "second"]),
        iterations=2,
        seed=0,
    )

    assert [repr(item) for item in result.tests_to_report] == ["first"]


def test_blackbox_keeps_crashes_with_different_coverage() -> None:
    result = orchestrate_fuzzing(
        crashes_on_distinct_paths,
        [MutatableString("")],
        SequentialMutator(["left", "right"]),
        iterations=2,
        seed=0,
    )

    assert [repr(item) for item in result.tests_to_report] == ["left", "right"]


def test_coverage_tracker_reports_only_last_run_lines() -> None:
    tracker = CoverageTracker(include_paths=[__file__])
    path = str(Path(__file__).resolve())
    left_line = _line_number_with_text(last_run_coverage_target, 'return "left"')
    right_line = _line_number_with_text(last_run_coverage_target, 'return "right"')

    tracker.start()
    last_run_coverage_target("left")
    tracker.stop()

    left_run_lines = tracker.get_last_run_coverage()[path]

    tracker.start()
    last_run_coverage_target("right")
    tracker.stop()

    right_run_lines = tracker.get_last_run_coverage()[path]

    assert left_line in left_run_lines
    assert right_line not in left_run_lines
    assert right_line in right_run_lines
    assert left_line not in right_run_lines


def test_greybox_promotes_new_coverage_and_reaches_deep_branch() -> None:
    result = orchestrate_greybox_fuzzing(
        branching_target,
        [MutatableString("")],
        PrefixStepMutator(),
        iterations=20,
        seed=0,
    )

    assert any(repr(k) == "ABC" for k in result.tests_to_report)
    assert any(item.new_coverage > 0 for item in result.tests_to_report.values())
    assert len(result.corpus) > 1


def test_greybox_deduplicates_initial_corpus_and_reported_tests() -> None:
    result = orchestrate_greybox_fuzzing(
        always_crashes,
        [MutatableString("same"), MutatableString("same")],
        IdentityMutator(),
        iterations=5,
        seed=0,
    )

    assert [repr(item) for item in result.tests_to_report] == ["same"]
    assert [repr(item) for item in result.corpus] == ["same"]


def test_greybox_deduplicates_semantically_equivalent_crashes() -> None:
    result = orchestrate_greybox_fuzzing(
        crashes_with_input_in_message,
        [MutatableString("first"), MutatableString("second")],
        IdentityMutator(),
        iterations=0,
        seed=0,
    )

    assert [repr(item) for item in result.tests_to_report] == ["first"]


def test_finding_fingerprint_has_fixed_length() -> None:
    result = ExecutionResult(
        RuntimeError("x" * 10_000),
        "\n".join(
            (
                "Traceback (most recent call last):",
                '  File "/tmp/example.py", line 42, in target',
                f"RuntimeError: {'x' * 10_000}",
            )
        ),
    )
    coverage = {
        CoveredLine("/tmp/example.py", line_number) for line_number in range(10_000)
    }

    assert len(_finding_fingerprint(result, coverage)) == 64
