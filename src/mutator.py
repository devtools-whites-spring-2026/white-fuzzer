import copy
import json
import random
from typing import Any

from typing import Self


class Mutator:
    def mutate(self: Self, arg: str) -> str:
        raise NotImplementedError()


class RandomCharMutator(Mutator):
    def mutate(self: Self, arg: str) -> str:
        n = random.randint(0, len(arg))
        c = random.randint(32, 126)
        return arg[:n] + chr(c) + arg[n + 1 :]


class DeleteCharMutator(Mutator):
    def mutate(self: Self, arg: str) -> str:
        if len(arg) == 0:
            return arg
        n = random.randint(0, len(arg) - 1)
        return arg[:n] + arg[n + 1 :]


class InsertCharMutator(Mutator):
    def mutate(self: Self, arg: str) -> str:
        n = random.randint(0, len(arg))
        c = random.randint(32, 126)
        return arg[:n] + chr(c) + arg[n:]


class SelectionMutator(Mutator):
    def __init__(self, mutators: list[Mutator]):
        self.mutators = mutators

    def mutate(self: Self, arg: str) -> str:
        random_mutator = random.choice(self.mutators)
        return random_mutator.mutate(arg)


class RepeatMutator(Mutator):
    def __init__(self: Self, inner: Mutator, max_times: int = 10) -> None:
        self.inner = inner
        self.max_times = max_times

    def mutate(self: Self, arg: str) -> str:
        times = random.randint(1, self.max_times)
        result = arg
        for _ in range(times):
            result = self.inner.mutate(result)
        return result


def create_generic_mutator() -> Mutator:
    mutators: list[Mutator] = [
        RandomCharMutator(),
        DeleteCharMutator(),
        InsertCharMutator(),
    ]
    selection_mutator = SelectionMutator(mutators)
    return RepeatMutator(selection_mutator)
    
class LeafMutator:
    """Apply a base string mutator only to flagged leaves.

    The mutator looks up each leaf by its :class:`LeafLocation` path and
    mutates the value in-place. Non-string leaves are coerced to a
    string for mutation and then converted back to the original type
    when possible. If the original was an int and the mutated form
    cannot be parsed, we keep the mutated string so the fuzzer can
    explore type-confusion failures.
    """

    def __init__(self, inner: Mutator, rng: random.Random | None = None) -> None:
        self.inner = inner
        self.rng = rng or random.Random()

    def mutate(self, test_case: Any) -> Any:
        """Return a new test case with leaves mutated.

        ``test_case`` is the dataclass produced by
        :func:`src.generator.generator.generate_test_case`. We deep-copy
        the data sections so the original remains untouched.
        """
        new = copy.deepcopy(test_case)
        for loc in new.leaves:
            if loc.section == "path_params":
                container = new.path_params
            elif loc.section == "query":
                container = new.query
            elif loc.section == "body":
                container = new.body  # may be a dict, list, or scalar
            else:
                continue
            self._mutate_at_path(container, loc.path, new=new)
        # Re-render URL because path params may have changed.
        new.url = _render_url(new.url_template, new.path_params)
        return new

    def _mutate_at_path(self, container: Any, path: list[Any], new: Any) -> None:
        if not path:
            # Whole body is itself a leaf — uncommon but possible.
            if isinstance(new.body, (str, int, float, bool)):
                new.body = self._mutate_value(new.body)
            return
        # Walk to the parent of the leaf.
        parent = container
        for seg in path[:-1]:
            parent = parent[seg]
        last = path[-1]
        parent[last] = self._mutate_value(parent[last])

    def _mutate_value(self, value: Any) -> Any:
        # Mutate via the string base mutator, then try to recover the type.
        as_str = json.dumps(value) if isinstance(value, bool) else str(value)
        mutated = self.inner.mutate(as_str)
        if isinstance(value, bool):
            # Booleans stay booleans only if the mutated string still parses;
            # otherwise we deliberately let the type drift.
            try:
                return json.loads(mutated)
            except (ValueError, TypeError):
                return mutated
        if isinstance(value, int):
            try:
                return int(mutated)
            except ValueError:
                return mutated
        if isinstance(value, float):
            try:
                return float(mutated)
            except ValueError:
                return mutated
        return mutated


def _render_url(template: str, path_params: dict) -> str:
    url = template
    for k, v in path_params.items():
        url = url.replace("{" + k + "}", str(v))
    return url
