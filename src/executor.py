from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    thrown_exception: Exception | None


def run_target(target: Callable[[str], None], argument: str) -> ExecutionResult:
    try:
        target(argument)
        return ExecutionResult(None)
    except Exception as ex:
        return ExecutionResult(ex)
