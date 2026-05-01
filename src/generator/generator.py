"""Generate concrete test cases from an :class:`EndpointGrammar`.

Output contract
---------------
Each call to :func:`generate_test_case` returns a :class:`TestCase`
plus a list of :class:`LeafLocation` records pointing at every value
that came from a :class:`Leaf` production. The mutator uses these
locations to mutate *only* the leaf values, never the structural keys.

A leaf location is a tuple ``(section, path)`` where ``section`` is one
of ``"path_params"``, ``"query"``, or ``"body"``, and ``path`` is a
list of ``str | int`` segments addressable inside the corresponding
container (object key or list index). For path/query we always stay
flat (depth 1), for the body we descend the JSON tree.

Determinism: passing the same ``random.Random`` seeds yields the same
output.
"""
import random
import string
from dataclasses import dataclass, field
from typing import Any

from src.grammar.grammar import (
    LEAF_BOOLEAN,
    LEAF_ENUM,
    LEAF_INTEGER,
    LEAF_NUMBER,
    LEAF_STRING,
    EndpointGrammar,
    GrammarNode,
    Leaf,
    ObjectNode,
    Repeat,
    Sequence,
    Terminal,
)


# --- output shape ---------------------------------------------------------


@dataclass
class LeafLocation:
    """Pointer to a mutable value inside a generated test case."""

    section: str  # "path_params" | "query" | "body"
    path: list[Any] = field(default_factory=list)
    type_hint: str = LEAF_STRING


@dataclass
class TestCase:
    method: str
    url: str  # rendered URL with path params substituted
    url_template: str  # original template, kept for debugging
    path_params: dict[str, Any] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)
    body: Any = None
    leaves: list[LeafLocation] = field(default_factory=list)


# --- public API -----------------------------------------------------------


def generate_test_case(
    grammar: EndpointGrammar,
    rng: random.Random | None = None,
) -> TestCase:
    rng = rng or random.Random()
    leaves: list[LeafLocation] = []

    path_params = _generate_object(
        grammar.path_params,
        rng,
        section="path_params",
        path_prefix=[],
        leaves=leaves,
        force_all_required=True,
    )
    query_params = _generate_object(
        grammar.query_params,
        rng,
        section="query",
        path_prefix=[],
        leaves=leaves,
    )
    body: Any = None
    if grammar.body is not None:
        body = _generate(grammar.body, rng, section="body", path_prefix=[], leaves=leaves)

    url = _render_url(grammar.url_template, path_params)
    return TestCase(
        method=grammar.method,
        url=url,
        url_template=grammar.url_template,
        path_params=path_params,
        query=query_params,
        body=body,
        leaves=leaves,
    )


# --- internals ------------------------------------------------------------


def _generate(
    node: GrammarNode,
    rng: random.Random,
    section: str,
    path_prefix: list[Any],
    leaves: list[LeafLocation],
) -> Any:
    if isinstance(node, Leaf):
        leaves.append(LeafLocation(section=section, path=list(path_prefix), type_hint=node.type_hint))
        return _generate_leaf_value(node, rng)
    if isinstance(node, ObjectNode):
        return _generate_object(node, rng, section, path_prefix, leaves)
    if isinstance(node, Repeat):
        return _generate_array(node, rng, section, path_prefix, leaves)
    if isinstance(node, Sequence):
        return "".join(
            str(_generate(c, rng, section, path_prefix, leaves)) for c in node.children
        )
    if isinstance(node, Terminal):
        return node.value
    # Fallback — treat as opaque string leaf so we still record it.
    leaves.append(LeafLocation(section=section, path=list(path_prefix), type_hint=LEAF_STRING))
    return "x"


def _generate_object(
    node: ObjectNode,
    rng: random.Random,
    section: str,
    path_prefix: list[Any],
    leaves: list[LeafLocation],
    force_all_required: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    required = set(node.required)
    for key, child in node.properties:
        is_required = force_all_required or key in required
        if not is_required:
            # 75% chance to include optional fields — biased to richer cases.
            if rng.random() > 0.75:
                continue
        sub_path = path_prefix + [key]
        result[key] = _generate(child, rng, section, sub_path, leaves)
    return result


def _generate_array(
    node: Repeat,
    rng: random.Random,
    section: str,
    path_prefix: list[Any],
    leaves: list[LeafLocation],
) -> list[Any]:
    if node.body is None:
        return []
    n = rng.randint(node.min_times, max(node.min_times, node.max_times))
    items = []
    # Bias towards at least 1 element if min is 0 — gives the mutator something to work with.
    if n == 0 and node.max_times >= 1 and rng.random() < 0.5:
        n = 1
    for i in range(n):
        items.append(_generate(node.body, rng, section, path_prefix + [i], leaves))
    return items


def _generate_leaf_value(leaf: Leaf, rng: random.Random) -> Any:
    if leaf.example is not None and leaf.type_hint != LEAF_ENUM:
        # Use the example as-is on first generation; the mutator can
        # take it from here. This makes test cases close to the
        # documented happy path.
        return leaf.example
    if leaf.type_hint == LEAF_ENUM and leaf.enum:
        return rng.choice(leaf.enum)
    if leaf.type_hint == LEAF_INTEGER:
        lo = int(leaf.minimum) if leaf.minimum is not None else 0
        hi = int(leaf.maximum) if leaf.maximum is not None else 1000
        if hi < lo:
            hi = lo
        return rng.randint(lo, hi)
    if leaf.type_hint == LEAF_NUMBER:
        lo = float(leaf.minimum) if leaf.minimum is not None else 0.0
        hi = float(leaf.maximum) if leaf.maximum is not None else 1000.0
        if hi < lo:
            hi = lo
        return round(rng.uniform(lo, hi), 4)
    if leaf.type_hint == LEAF_BOOLEAN:
        return rng.choice([True, False])
    # default: string
    min_len = leaf.min_length or 3
    max_len = leaf.max_length or 8
    if max_len < min_len:
        max_len = min_len
    n = rng.randint(min_len, max_len)
    return "".join(rng.choices(string.ascii_letters, k=n))


def _render_url(template: str, path_params: dict[str, Any]) -> str:
    url = template
    for k, v in path_params.items():
        url = url.replace("{" + k + "}", str(v))
    return url
