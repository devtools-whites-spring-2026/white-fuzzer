import json
import random
from dataclasses import dataclass
from typing import Self

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

    def to_dict(self) -> dict:
        return {
            "data": self.data,
            "placeholders": [
                {"placeholder": f.placeholder, "value": f.value}
                for f in self.placeholders
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StringWithMutablePlaceholders":
        placeholders = [MutatableField(**p) for p in d["placeholders"]]
        return cls(d["data"], placeholders)


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
        target = random.choice(targets)
        new_params = (
            target.apply_mutator(mutator) if target is self.params else self.params
        )
        new_data = target.apply_mutator(mutator) if target is self.data else self.data
        return type(self)(self.type, self.url, new_params, new_data)

    def __repr__(self) -> str:
        return f"{self.type} {self.url} params={self.params!r} data={self.data!r}"

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "url": self.url,
            "params": self.params.to_dict() if self.params else None,
            "data": self.data.to_dict() if self.data else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MutatableRestRequest":
        params = StringWithMutablePlaceholders.from_dict(
            d["params"]) if d.get("params") else None
        data = StringWithMutablePlaceholders.from_dict(
            d["data"]) if d.get("data") else None
        return cls(d["type"], d["url"], params, data)
