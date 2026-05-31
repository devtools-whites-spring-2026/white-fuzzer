import random
from typing import Self


class Mutator:
    def mutate(self: Self, arg: str) -> str:
        raise NotImplementedError()


class Mutatable:
    # returns a new object with mutated state
    def apply_mutator(self: Self, mutator: Mutator) -> Self:
        pass


class MutatableString(Mutatable):
    def __init__(self, arg: str) -> None:
        self.arg = arg

    def apply_mutator(self: Self, mutator: Mutator) -> Self:
        mutated_string = mutator.mutate(self.arg)
        return MutatableString(mutated_string)


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
