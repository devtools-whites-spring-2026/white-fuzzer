"""Grammar AST for API request fuzzing.

Design notes
------------
The grammar produced from an OpenAPI spec is a tree of *production* nodes.
Internal (non-terminal) nodes describe **structure** that must be preserved
for the request to remain syntactically valid (object keys, array brackets,
URL templates, etc.). Leaves carry **values** that can be safely mutated
without breaking the structural skeleton.

The mutator, given a generated test case, only ever touches values that
came from `Leaf` nodes. Every leaf value is generated together with a
*path* (a list of keys / indices) describing where it lives in the final
output, so the mutator can locate and replace it without re-walking the
grammar.

Node kinds
~~~~~~~~~~
* ``Terminal``   – fixed, unmutable text (slashes, structural separators).
* ``Leaf``       – mutable value of a primitive type. Leaves are the only
                   thing the mutator is allowed to change.
* ``Sequence``   – ordered concatenation of children.
* ``Choice``     – one of N alternatives is picked.
* ``Repeat``     – child repeated [min..max] times (used for arrays).
* ``Object``     – JSON object with named, ordered properties.
* ``Nonterminal``– named grouping with a single body (useful for naming).
"""
from dataclasses import dataclass, field
from typing import Any


# --- Leaf type hints ------------------------------------------------------

LEAF_STRING = "string"
LEAF_INTEGER = "integer"
LEAF_NUMBER = "number"
LEAF_BOOLEAN = "boolean"
LEAF_ENUM = "enum"


# --- AST nodes ------------------------------------------------------------


@dataclass
class GrammarNode:
    """Base class. All nodes optionally carry a ``name`` for debugging."""

    name: str | None = None


@dataclass
class Terminal(GrammarNode):
    """A literal piece of text or a structural value that must NOT be mutated.

    Examples: the ``/`` separators in a URL template, JSON object braces
    (implicit), required key names.
    """

    value: str = ""


@dataclass
class Leaf(GrammarNode):
    """A mutable value.

    ``type_hint`` constrains the kind of values the generator should emit
    initially. ``enum`` further restricts to a finite alphabet. The
    ``mutable`` flag is always ``True`` for leaves and exists to make the
    intent explicit when serialising.
    """

    type_hint: str = LEAF_STRING
    example: Any = None
    enum: list[Any] | None = None
    minimum: float | None = None
    maximum: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    mutable: bool = True


@dataclass
class Sequence(GrammarNode):
    children: list[GrammarNode] = field(default_factory=list)


@dataclass
class Choice(GrammarNode):
    alternatives: list[GrammarNode] = field(default_factory=list)


@dataclass
class Repeat(GrammarNode):
    body: GrammarNode | None = None
    min_times: int = 0
    max_times: int = 3


@dataclass
class ObjectNode(GrammarNode):
    """JSON object production.

    ``properties`` is an ordered mapping of ``key -> child production``.
    ``required`` is the subset of keys that MUST be emitted by the
    generator. Keys themselves are *terminals* (structure), values are
    whatever the child production produces.
    """

    properties: list[tuple[str, GrammarNode]] = field(default_factory=list)
    required: list[str] = field(default_factory=list)


@dataclass
class Nonterminal(GrammarNode):
    body: GrammarNode | None = None


# --- Top level ------------------------------------------------------------


@dataclass
class EndpointGrammar:
    """Grammar for one HTTP operation.

    The generator turns this into a concrete ``TestCase`` by walking each
    sub-grammar separately. Splitting URL / query / body keeps the leaf
    paths tractable: a leaf's ``location`` tells the mutator which part of
    the request it lives in.
    """

    operation_id: str
    method: str
    url_template: str  # path with `{name}` placeholders
    path_params: ObjectNode  # name -> Leaf
    query_params: ObjectNode  # name -> Leaf
    body: GrammarNode | None = None  # typically ObjectNode
