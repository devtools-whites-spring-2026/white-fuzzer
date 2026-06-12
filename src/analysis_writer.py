
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.fuzzer_coordinator import FuzzingResult
    from src.mutator import Mutatable


def _serialize_input(value: "Mutatable") -> dict:
    from src.mutator import MutatableString
    from src.mutatable_request import MutatableRestRequest

    if isinstance(value, MutatableRestRequest):
        return {"kind": "rest_request", **value.to_dict()}
    if isinstance(value, MutatableString):
        return {"kind": "string", "value": value.arg}
    return {"kind": "unknown", "repr": repr(value)}


def _deserialize_input(d: dict) -> "Mutatable":
    from src.mutator import MutatableString
    from src.mutatable_request import MutatableRestRequest

    kind = d.get("kind")
    if kind == "rest_request":
        return MutatableRestRequest.from_dict(d)
    if kind == "string":
        return MutatableString(d["value"])
    raise ValueError(f"Unknown input kind: {kind!r}")


def save_analysis(
    result: "FuzzingResult",
    path: str,
    seed: int | None = None,
    iterations: int | None = None,
    target: str | None = None,
    mode: str = "blackbox",
) -> None:

    fc, ft, fp = result.function_coverage

    findings = []
    for inp, exec_result in result.tests_to_report.items():
        findings.append({
            "input": _serialize_input(inp),
            "input_repr": repr(inp),
            "result": exec_result.to_dict(),
        })

    corpus = [_serialize_input(item) for item in result.corpus]

    snapshot: dict[str, Any] = {
        "metadata": {
            "seed": seed,
            "iterations": iterations,
            "target": target,
            "mode": mode,
        },
        "coverage": result.coverage_report,
        "function_coverage": {
            "covered": fc,
            "total": ft,
            "percent": fp,
        },
        "findings": findings,
        "corpus": corpus,
    }

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def load_corpus_from_analysis(path: str) -> list["Mutatable"]:
    with open(path, encoding="utf-8") as f:
        snapshot = json.load(f)

    return [_deserialize_input(d) for d in snapshot.get("corpus", [])]
