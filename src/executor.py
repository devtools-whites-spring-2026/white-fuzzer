from collections.abc import Callable
from dataclasses import dataclass

from src.coverage import BaseCoverage


@dataclass
class ExecutionResult:
    thrown_exception: Exception | None


def run_target(
    target: Callable[[str], None],
    argument: str,
    coverage_collector: BaseCoverage,
) -> ExecutionResult:
    coverage_collector.start()

    try:
        target(argument)

        coverage_collector.stop()

        return ExecutionResult(None)
    except Exception as ex:
        return ExecutionResult(ex)
    finally:
        coverage_collector.stop()
