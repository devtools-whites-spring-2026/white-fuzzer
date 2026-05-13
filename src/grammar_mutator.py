from __future__ import annotations

import copy
import random
from dataclasses import dataclass

from src.grammar import (
    DerivationNode,
    Grammar,
    GrammarGenerator,
    MutationPolicy,
    Symbol,
    annotate_tree,
    collect_mutable_nodes,
)
from src.mutator import Mutator


@dataclass
class MutationReport:
    mutated_symbol: Symbol
    original_subtree: str
    mutated_subtree: str

    def summary(self) -> str:
        if not self.mutated_symbol:
            return "No mutation (all nodes frozen)"
        return f"{self.mutated_symbol!r}: {self.original_subtree!r} → {self.mutated_subtree!r}"


class GrammarMutator(Mutator):
    def __init__(
        self,
        grammar: Grammar,
        policy: MutationPolicy | None = None,
        start: Symbol = "<start>",
        max_depth: int = 10,
    ) -> None:
        self._generator = GrammarGenerator(grammar, max_depth=max_depth)
        self._policy: MutationPolicy = policy or {}
        self._start = start
        self._tree_cache: dict[str, DerivationNode] = {}

    def generate(self) -> str:
        tree = self._generator.generate_tree(self._start)
        rendered = self._generator.render(tree)
        self._tree_cache[rendered] = tree
        return rendered

    def mutate(self, arg: str) -> str:
        tree = self._get_or_generate_tree(arg)
        new_tree, _ = self._mutate_tree(tree)
        new_str = self._generator.render(new_tree)
        self._tree_cache[new_str] = new_tree
        return new_str

    def mutate_with_report(self, arg: str) -> tuple[str, MutationReport]:
        tree = self._get_or_generate_tree(arg)
        new_tree, report = self._mutate_tree(tree)
        new_str = self._generator.render(new_tree)
        self._tree_cache[new_str] = new_tree
        return new_str, report

    def _mutate_tree(
        self, tree: DerivationNode
    ) -> tuple[DerivationNode, MutationReport]:
        tree_copy = copy.deepcopy(tree)
        annotate_tree(tree_copy, self._policy)
        mutable_nodes = collect_mutable_nodes(tree_copy)
        original_str = self._generator.render(tree_copy)

        if not mutable_nodes:
            return tree_copy, MutationReport("", original_str, original_str)

        target = random.choice(mutable_nodes)
        original_subtree = self._generator.render(target)

        new_subtree = self._generator.generate_tree(target.symbol)
        target.symbol = new_subtree.symbol
        target.children = new_subtree.children

        return tree_copy, MutationReport(
            mutated_symbol=target.symbol,
            original_subtree=original_subtree,
            mutated_subtree=self._generator.render(target),
        )

    def _get_or_generate_tree(self, rendered: str) -> DerivationNode:
        if rendered in self._tree_cache:
            return self._tree_cache[rendered]
        tree = self._generator.generate_tree(self._start)
        key = self._generator.render(tree)
        self._tree_cache[key] = tree
        return tree