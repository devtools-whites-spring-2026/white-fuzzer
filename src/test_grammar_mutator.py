from __future__ import annotations

import json

from src.example_schema import schema
from src.grammar_mutator import GrammarMutator
from src.schema_to_grammar import build_from_schema


def test_build_from_schema() -> tuple[dict, dict, str]:
    grammar, policy, start = build_from_schema(schema)

    assert start == "<start>", f"unexpected start symbol: {start!r}"
    assert "<start>" in grammar, "start symbol missing in grammar"
    assert grammar["<start>"] == [["<request_object>"]], (
        f"unexpected start expansion: {grammar['<start>']!r}"
    )

    assert "<request_object>" in grammar, "root object symbol missing"
    assert "<request_title_string>" in grammar, "title symbol missing"
    assert "<request_status_enum>" in grammar, "status symbol missing"
    assert "<request_id_integer>" in grammar, "id symbol missing"

    assert policy["<start>"] is False, "<start> must be frozen"
    assert policy["<request_object>"] is False, "request object must be frozen"
    assert policy["<request_title_string>"] is True, "title must be mutable"
    assert policy["<request_status_enum>"] is True, "status must be mutable"
    assert policy["<request_id_integer>"] is False, "id must be frozen"

    print("[OK] build_from_schema produced grammar and policy")
    return grammar, policy, start


def test_generation(mutator: GrammarMutator) -> str:
    generated = mutator.generate()

    payload = json.loads(generated)
    assert isinstance(payload, dict), f"expected object, got {type(payload)}"
    assert set(payload.keys()) == {"title", "status", "id"}, (
        f"unexpected keys: {payload.keys()}"
    )
    assert payload["status"] in {"new", "done"}, (
        f"unexpected status: {payload['status']!r}"
    )
    assert isinstance(payload["id"], int), (
        f"id must be int, got {type(payload['id'])}"
    )

    print("[OK] generated payload is valid JSON object")
    print("     ", generated)
    return generated


def test_mutation(mutator: GrammarMutator, seed: str) -> None:
    mutated, report = mutator.mutate_with_report(seed)

    before = json.loads(seed)
    after = json.loads(mutated)

    assert set(after.keys()) == {"title", "status", "id"}, "structure changed"
    assert isinstance(after["id"], int), "id type changed"
    assert after["status"] in {"new", "done"}, "status left enum set"

    print("[OK] mutation preserves JSON structure")
    print("     before:", before)
    print("     after :", after)
    print("     report:", report.summary())


def test_all_frozen_schema() -> None:
    from src.schema_model import SchemaNode

    frozen_schema = SchemaNode(
        name="request",
        kind="object",
        mutable=False,
        properties={
            "title": SchemaNode(name="title", kind="string", mutable=False),
            "status": SchemaNode(
                name="status",
                kind="enum",
                mutable=False,
                enum_values=["new", "done"],
            ),
            "id": SchemaNode(name="id", kind="integer", mutable=False),
        },
    )

    grammar, policy, start = build_from_schema(frozen_schema)
    mutator = GrammarMutator(grammar, policy=policy, start=start)
    seed = mutator.generate()
    mutated, report = mutator.mutate_with_report(seed)

    assert seed == mutated, (
        f"all-frozen schema must not mutate: {seed!r} -> {mutated!r}"
    )
    assert report.mutated_symbol == "", (
        "mutated_symbol must be empty when all frozen"
    )

    print("[OK] all-frozen schema leaves payload unchanged")


def main() -> None:
    print("Running schema tests...\n")
    grammar, policy, start = test_build_from_schema()
    mutator = GrammarMutator(grammar, policy=policy, start=start)
    seed = test_generation(mutator)
    test_mutation(mutator, seed)
    test_all_frozen_schema()
    print("\nAll schema tests passed.")


if __name__ == "__main__":
    main()