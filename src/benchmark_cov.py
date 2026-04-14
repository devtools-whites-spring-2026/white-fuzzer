import time
import random
from executor import run_target


def target(a):
    rand = random.randint(-10, 10)
    x = rand

    if x < 0:
        return "negative"
    elif x == 0:
        return "zero"
    elif x < 10:
        if x % 2 == 0:
            return "small even"
        else:
            return "small odd"
    else:
        return "large"


def benchmark(iterations=1000):
    start = time.time()
    for i in range(iterations):
        target(i % 20 - 10)
    baseline = time.time() - start

    start = time.time()
    for i in range(iterations):
        run_target(target=target, argument="")
    with_cov = time.time() - start

    print(f"Baseline: {baseline:.4f}s")
    print(f"With coverage: {with_cov:.4f}s")
    print(f"Slowdown: x{with_cov / baseline:.2f}")


if __name__ == "__main__":
    benchmark()