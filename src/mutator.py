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
