from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from src.mutatable_request import MutatableRestRequest
from src.mutator import Mutatable, MutatableString

_METHODS_WITH_BODY = {"POST", "PUT", "PATCH"}

T = TypeVar("T", bound=Mutatable)

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.coverage import Coverage


@dataclass
class ExecutionResult:
    thrown_exception: Exception | None
    traceback_text: str | None
    new_coverage: int = 0


class Executor(Generic[T]):
    def execute(self, argument: T, coverage_collector: Coverage) -> ExecutionResult:
        raise NotImplementedError()


class FunctionExecutor(Executor[MutatableString]):
    def __init__(self, target: Callable[[str], None]) -> None:
        self._target = target

    def execute(
        self, argument: MutatableString, coverage_collector: Coverage
    ) -> ExecutionResult:
        coverage_collector.start()
        try:
            self._target(argument.arg)
            return ExecutionResult(None, None)
        except Exception as ex:
            return ExecutionResult(ex, traceback.format_exc())
        finally:
            coverage_collector.stop()


class DjangoClientExecutor(Executor[MutatableRestRequest]):
    def __init__(
        self,
        settings_module: str,
        generate_user: bool = False,
    ) -> None:
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
        self, argument: MutatableRestRequest, coverage_collector: Coverage
    ) -> ExecutionResult:
        coverage_collector.start()
        try:
            method = argument.type.upper()
            path = argument.url
            client = self._ensure_client()
            request_method = getattr(client, method.lower(), None)
            if request_method is None:
                raise ValueError(f"Unsupported HTTP method for fuzzing: {method}")

            import json

            kwargs: dict[str, Any] = {}
            if argument.params:
                kwargs["data"] = json.loads(argument.params.to_string())
            if method in _METHODS_WITH_BODY and argument.data:
                kwargs["data"] = argument.data.to_string()
                kwargs["content_type"] = "application/json"

            logger = logging.getLogger("django.request")
            previous_disabled = logger.disabled
            logger.disabled = True
            try:
                request_method(path, **kwargs)
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
    return FunctionExecutor(target).execute(
        MutatableString(argument), coverage_collector
    )
