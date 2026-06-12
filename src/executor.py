from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar
from urllib.parse import urlencode

from src.mutatable_request import MutatableRestRequest
from src.mutator import Mutatable, MutatableString

_METHODS_WITH_BODY = {"POST", "PUT", "PATCH"}

T = TypeVar("T", bound=Mutatable)

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.coverage_tracker import CoverageTracker


@dataclass
class ExecutionResult:
    thrown_exception: Exception | None
    traceback_text: str | None
    new_coverage: int = 0
    status_code: int | None = None
    curl_command: str | None = None

    def to_dict(self) -> dict:
        exc = self.thrown_exception
        return {
            "exception_type": type(exc).__name__ if exc else None,
            "exception_message": str(exc) if exc else None,
            "traceback": self.traceback_text,
            "new_coverage": self.new_coverage,
            "status_code": self.status_code,
            "curl_command": self.curl_command,
        }


class Executor(Generic[T]):
    def execute(
        self, argument: T, coverage_collector: CoverageTracker
    ) -> ExecutionResult:
        raise NotImplementedError()


class FunctionExecutor(Executor[MutatableString]):
    def __init__(self, target: Callable[[str], None]) -> None:
        self._target = target

    def execute(
        self, argument: MutatableString, coverage_collector: CoverageTracker
    ) -> ExecutionResult:
        try:
            self._target(argument.arg)
            return ExecutionResult(None, None)
        except Exception as ex:
            return ExecutionResult(ex, traceback.format_exc())


def _build_curl_command(method: str, base_url: str, params_str: str | None, body_str: str | None) -> str:
    url = base_url
    if params_str:
        try:
            import json as _json
            params_dict = _json.loads(params_str)
            url = f"{base_url}?{urlencode(params_dict)}"
        except Exception:
            url = f"{base_url}?{params_str}"

    parts = ["curl", "-X", method, f'"{url}"']
    if body_str:
        parts += ["-H", '"Content-Type: application/json"', "-d", f"'{body_str}'"]
    return " ".join(parts)


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

    def _is_django_healthy(self) -> bool:
        if not self._is_initialized:
            return True
        from django.db import connections

        for conn in connections.all():
            if conn.errors_occurred:
                return False
            if conn.connection is not None and not conn.is_usable():
                return False
        return True

    def _reset_client(self) -> None:
        from django.db import connections

        for conn in connections.all():
            conn.close()
        self._client = None
        self._is_initialized = False

    def execute(
        self, argument: MutatableRestRequest, coverage_collector: CoverageTracker
    ) -> ExecutionResult:
        if not self._is_django_healthy():
            self._reset_client()

        try:
            method = argument.type.upper()
            path = argument.url
            client = self._ensure_client()
            request_method = getattr(client, method.lower(), None)
            if request_method is None:
                raise ValueError(f"Unsupported HTTP method for fuzzing: {method}")

            import json

            kwargs: dict[str, Any] = {}
            params_str = argument.params.to_string() if argument.params else None
            body_str = argument.data.to_string() if argument.data else None

            if params_str:
                kwargs["data"] = json.loads(params_str)
            if method in _METHODS_WITH_BODY and body_str:
                kwargs["data"] = body_str
                kwargs["content_type"] = "application/json"

            curl = _build_curl_command(method, path, params_str, body_str)

            logger = logging.getLogger("django.request")
            previous_disabled = logger.disabled
            logger.disabled = True
            try:
                response = request_method(path, **kwargs)
            finally:
                logger.disabled = previous_disabled

            return ExecutionResult(None, None, status_code=response.status_code, curl_command=curl)
        except Exception as ex:
            return ExecutionResult(ex, traceback.format_exc())


def run_target(
    target: Callable[[str], None],
    argument: str,
    coverage_collector: CoverageTracker,
) -> ExecutionResult:
    return FunctionExecutor(target).execute(
        MutatableString(argument), coverage_collector
    )
