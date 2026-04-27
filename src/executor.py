from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.coverage import Coverage


@dataclass
class ExecutionResult:
    thrown_exception: Exception | None
    traceback_text: str | None
    new_coverage: int = 0


class Executor:
    def execute(
        self, argument: str, coverage_collector: Coverage
    ) -> ExecutionResult:
        raise NotImplementedError()


class FunctionExecutor(Executor):
    def __init__(self, target: Callable[[str], None]) -> None:
        self._target = target

    def execute(
        self, argument: str, coverage_collector: Coverage
    ) -> ExecutionResult:
        coverage_collector.start()

        try:
            self._target(argument)
            return ExecutionResult(None, None)
        except Exception as ex:
            return ExecutionResult(ex, traceback.format_exc())
        finally:
            coverage_collector.stop()


class DjangoClientExecutor(Executor):
    def __init__(
        self,
        settings_module: str,
        request_builder: Callable[[str], tuple[str, str, dict[str, str]]],
    ) -> None:
        self._settings_module = settings_module
        self._request_builder = request_builder
        self._client = None
        self._is_initialized = False

    def _ensure_client(self) -> Any:
        if not self._is_initialized:
            import django
            from django.conf import settings
            from django.test import Client

            if not settings.configured:
                from os import environ

                environ.setdefault(
                    "DJANGO_SETTINGS_MODULE", self._settings_module
                )
                django.setup()
            self._client = Client()
            self._is_initialized = True
        if self._client is None:
            raise RuntimeError("Django test client is not initialized")
        return self._client

    def execute(
        self, argument: str, coverage_collector: Coverage
    ) -> ExecutionResult:
        coverage_collector.start()
        try:
            method, path, payload = self._request_builder(argument)
            client = self._ensure_client()
            request_method = getattr(client, method.lower(), None)
            if request_method is None:
                raise ValueError(
                    f"Unsupported HTTP method for fuzzing: {method}"
                )

            # Mute Django request tracebacks while fuzzing
            logger = logging.getLogger("django.request")
            previous_disabled = logger.disabled
            logger.disabled = True
            try:
                request_method(path, data=payload)
            finally:
                logger.disabled = previous_disabled

            return ExecutionResult(None, None)
        except Exception as ex:
            return ExecutionResult(ex, traceback.format_exc())
        finally:
            coverage_collector.stop()


def run_target(
    target: Callable[[str], None], argument: str, coverage_collector: Coverage
) -> ExecutionResult:
    return FunctionExecutor(target).execute(argument, coverage_collector)
