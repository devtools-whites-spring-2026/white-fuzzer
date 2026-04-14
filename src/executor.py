from collections.abc import Callable
from dataclasses import dataclass

from coverage import Coverage


@dataclass
class ExecutionResult:
    thrown_exception: Exception | None


def run_target(target: Callable[[str], None], argument: str) -> ExecutionResult:
    coverage_collector: Coverage = Coverage()
    coverage_collector.reset()
    coverage_collector.start()

    try:
        target(argument)

        coverage_collector.stop()
        coverage_report = coverage_collector.get_stats()

        print(
            f"Coverage report: {coverage_report['covered']}"
            f"/{coverage_report['total']} lines "
            f"({coverage_report['percent']}%)"
        )

        return ExecutionResult(None)
    except Exception as ex:
        return ExecutionResult(ex)
    finally:
        coverage_collector.stop()
