from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from src.mutatable_request import MutatableRestRequest, MutatableRestScenario
from src.mutator import Mutatable, MutatableString

if TYPE_CHECKING:
    from src.openapi_schema import EndpointSchema

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


def _find_matching_endpoint(
    spec: list[EndpointSchema], path: str, method: str
) -> EndpointSchema | None:
    for endpoint in spec:
        if endpoint.get("path") == path and endpoint.get("method") == method.upper():
            return endpoint
    return None


class SpecMismatchException(Exception):
    def __init__(
        self,
        actual_code: int,
        data: Any,
        method: str,
        path: str,
        expected_codes: set[int],
    ) -> None:
        self.actual_code = actual_code
        self.method = method
        self.path = path
        self.expected_codes = expected_codes
        self.response_data = data
        message = (
            f"Unexpected status code {actual_code}  with data {data} "
            f"for {method} {path}; "
            f"expected one of {sorted(expected_codes)}"
        )
        super().__init__(message)


class DjangoClientExecutor(Executor[MutatableRestRequest]):
    def __init__(
        self,
        settings_module: str,
        generate_user: bool = False,
        openapi_spec: list[EndpointSchema] | None = None,
    ) -> None:
        self._generate_user = generate_user
        self._client = None
        self._is_initialized = False
        self.openapi_spec = openapi_spec

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
            if argument.params:
                kwargs["query_param"] = json.loads(argument.params.to_string())
                if method not in _METHODS_WITH_BODY:
                    kwargs["format"] = "json"
            if method in _METHODS_WITH_BODY:
                if argument.data:
                    kwargs["data"] = argument.data.to_string()
                else:
                    kwargs["data"] = {}
                kwargs["content_type"] = "application/json"

            logger = logging.getLogger("django.request")
            previous_disabled = logger.disabled
            logger.disabled = True
            try:
                response = request_method(path, **kwargs)
            finally:
                logger.disabled = previous_disabled

            if self.openapi_spec is not None:
                endpoint = _find_matching_endpoint(self.openapi_spec, path, method)
                if endpoint is not None:
                    expected_codes = set(endpoint.get("responses", {}).keys())
                    actual_code = response.status_code
                    if actual_code not in expected_codes:
                        raise SpecMismatchException(
                            actual_code=actual_code,
                            data=getattr(response, "data", None),
                            method=method,
                            path=path,
                            expected_codes=expected_codes,
                        )

            return ExecutionResult(None, None)
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


class DjangoScenarioExecutor(Executor[MutatableRestScenario]):
    def __init__(self, django_exec: DjangoClientExecutor):
        self._django_exec = django_exec

    def execute(
        self, argument: MutatableRestScenario, coverage_collector: CoverageTracker
    ) -> ExecutionResult:
        total_coverage = 0
        for request in argument.scenario_requests:
            intermediate_result = self._django_exec.execute(request, coverage_collector)
            total_coverage += intermediate_result.new_coverage
            if intermediate_result.thrown_exception is not None:
                return ExecutionResult(
                    intermediate_result.thrown_exception,
                    intermediate_result.traceback_text,
                    total_coverage,
                )
        return ExecutionResult(None, None, total_coverage)
