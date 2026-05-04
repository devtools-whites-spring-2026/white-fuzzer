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
        generate_user: bool = False,
    ) -> None:
        self._request_builder = request_builder
        self._generate_user = generate_user
        self._client = None
        self._is_initialized = False

        import os

        import django

        os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
        django.setup()

    def _ensure_client(self) -> Any:
        if self._is_initialized:
            return self._client

        if self._generate_user:
            from django.contrib.auth import get_user_model
            from rest_framework.test import APIClient

            self._client = APIClient()
            User = get_user_model()
            user, _ = User.objects.get_or_create(username="fuzz")
            user.is_active = True
            user.set_password("fuzz")
            user.save()
            self._client.force_authenticate(user=user)
        else:
            from django.test import Client

            self._client = Client()

        self._is_initialized = True

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
