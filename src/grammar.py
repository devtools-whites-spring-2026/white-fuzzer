from __future__ import annotations

import random
from dataclasses import dataclass, field

Symbol = str
Expansion = list[Symbol]
Grammar = dict[Symbol, list[Expansion]]
MutationPolicy = dict[Symbol, bool]


def is_nonterminal(symbol: Symbol) -> bool:
    return symbol.startswith("<") and symbol.endswith(">")


@dataclass
class DerivationNode:
    symbol: Symbol
    children: list["DerivationNode"] | None = field(default=None)
    mutable: bool = True

    def is_terminal(self) -> bool:
        return self.children is None

    def __repr__(self) -> str:
        if self.is_terminal():
            return f"Leaf({self.symbol!r})"
        return f"Node({self.symbol!r}, mutable={self.mutable}, children={len(self.children)})"


class GrammarGenerator:
    def __init__(self, grammar: Grammar, max_depth: int = 10) -> None:
        self._grammar = grammar
        self._max_depth = max_depth
        self._min_cost: dict[Symbol, int] = {}
        self._compute_min_costs()

    def _compute_min_costs(self) -> None:
        costs: dict[Symbol, int] = {}
        changed = True
        while changed:
            changed = False
            for symbol, expansions in self._grammar.items():
                for expansion in expansions:
                    cost = self._expansion_cost(expansion, costs)
                    if cost is not None:
                        if symbol not in costs or costs[symbol] > cost:
                            costs[symbol] = cost
                            changed = True
        self._min_cost = costs

    def _expansion_cost(
        self, expansion: Expansion, costs: dict[Symbol, int]
    ) -> int | None:
        max_cost = 0
        for sym in expansion:
            if not is_nonterminal(sym):
                continue
            if sym not in costs:
                return None
            max_cost = max(max_cost, costs[sym] + 1)
        return max_cost

    def _cheap_expansions(self, symbol: Symbol) -> list[Expansion]:
        expansions = self._grammar[symbol]
        costs = [self._expansion_cost(e, self._min_cost) for e in expansions]
        known = [(e, c) for e, c in zip(expansions, costs) if c is not None]
        if not known:
            return expansions
        min_cost = min(c for _, c in known)
        return [e for e, c in known if c == min_cost]

    def generate_tree(
        self, start: Symbol = "<start>", _depth: int = 0
    ) -> DerivationNode:
        if not is_nonterminal(start):
            return DerivationNode(symbol=start, children=None)

        if start not in self._grammar:
            raise ValueError(f"Symbol {start!r} not found in grammar")

        expansions = (
            self._cheap_expansions(start)
            if _depth >= self._max_depth
            else self._grammar[start]
        )
        expansion = random.choice(expansions)
        children = [
            self.generate_tree(sym, _depth=_depth + 1) for sym in expansion
        ]
        return DerivationNode(symbol=start, children=children)

    def render(self, node: DerivationNode) -> str:
        if node.is_terminal():
            return node.symbol
        return "".join(self.render(child) for child in node.children)

    def generate(self, start: Symbol = "<start>") -> str:
        return self.render(self.generate_tree(start))


def annotate_tree(node: DerivationNode, policy: MutationPolicy) -> DerivationNode:
    node.mutable = policy.get(node.symbol, True)
    if node.children is not None:
        for child in node.children:
            annotate_tree(child, policy)
    return node


def collect_mutable_nodes(node: DerivationNode) -> list[DerivationNode]:
    result: list[DerivationNode] = []

    def _walk(n: DerivationNode) -> None:
        if n.mutable and not n.is_terminal():
            result.append(n)
        if n.children:
            for child in n.children:
                _walk(child)

    _walk(node)
    return result
