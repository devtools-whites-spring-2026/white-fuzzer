import json
import random
from dataclasses import dataclass
from typing import Any, Self

from src.mutator import Mutatable, Mutator


@dataclass
class MutatableField:
    placeholder: str
    value: str


class StringWithMutablePlaceholders(Mutatable):
    def __init__(self, data: str, placeholders: list[MutatableField]) -> None:
        self.data = data
        self.placeholders = placeholders

    def to_string(self) -> str:
        result = self.data
        for field in self.placeholders:
            escaped = json.dumps(field.value)[1:-1]
            result = result.replace(field.placeholder, escaped)
        return result

    def apply_mutator(self, mutator: Mutator) -> Self:
        if not self.placeholders:
            return type(self)(self.data, [])
        idx = random.randint(0, len(self.placeholders) - 1)
        new_placeholders = [
            MutatableField(
                f.placeholder, mutator.mutate(f.value) if i == idx else f.value
            )
            for i, f in enumerate(self.placeholders)
        ]
        return type(self)(self.data, new_placeholders)

    def __repr__(self) -> str:
        return self.to_string()


class MutatableRestRequest(Mutatable):
    def __init__(
        self,
        request_type: str,
        url: str,
        params: StringWithMutablePlaceholders | None = None,
        data: StringWithMutablePlaceholders | None = None,
    ) -> None:
        self.type = request_type
        self.url = url
        self.params = params
        self.data = data

    def apply_mutator(self, mutator: Mutator) -> Self:
        targets = [x for x in [self.params, self.data] if x is not None]
        if not targets:
            return type(self)(self.type, self.url, self.params, self.data)
        target = random.choice(targets)
        new_params = (
            target.apply_mutator(mutator) if target is self.params else self.params
        )
        new_data = target.apply_mutator(mutator) if target is self.data else self.data
        return type(self)(self.type, self.url, new_params, new_data)

    def __repr__(self) -> str:
        return f"{self.type} {self.url} params={self.params!r} data={self.data!r}"


def _drop_none_values(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _drop_none_values(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_drop_none_values(v) for v in obj]
    return obj


def extract_test_cases_from_dir(directory: str) -> list[MutatableRestRequest]:
    result = []
    from pathlib import Path

    for file in Path(directory).iterdir():
        with file.open() as f:
            tests = json.load(f)
            for test in tests:
                prp_params = PrpJson()
                params_template = prp_params.prepare_json(test["query_params"])
                params = StringWithMutablePlaceholders(
                    json.dumps(_drop_none_values(params_template)),
                    prp_params.placeholders,
                )

                prp_data = PrpJson()
                data_template = prp_data.prepare_json(test["data"])
                data = StringWithMutablePlaceholders(
                    json.dumps(_drop_none_values(data_template)), prp_data.placeholders
                )

                case = MutatableRestRequest(
                    request_type=test["method-type"],
                    url=test["url"],
                    params=params,
                    data=data,
                )
                result.append(case)
    return result


class PrpJson:
    def __init__(self) -> None:
        self.plc_counter = 0
        self.placeholders = []

    def prepare_json(self, data: Any) -> Any:
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                result[key] = self.prepare_json(value)
            return result
        if isinstance(data, list):
            result = []
            for value in data:
                result.append(self.prepare_json(value))
            return result
        if isinstance(data, str):
            placeholder = f"PLC{self.plc_counter:03d}"
            self.placeholders.append(MutatableField(placeholder, data))
            self.plc_counter += 1
            return placeholder
        return data
