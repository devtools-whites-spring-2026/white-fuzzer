import random
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
