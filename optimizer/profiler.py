import time
from collections import defaultdict
from functools import wraps


class Profiler:
    stats = defaultdict(lambda: {"calls": 0, "time": 0.0})

    @classmethod
    def record(cls, name: str, duration: float) -> None:
        cls.stats[name]["calls"] += 1
        cls.stats[name]["time"] += duration

    @classmethod
    def reset(cls) -> None:
        cls.stats.clear()

    @classmethod
    def report(cls) -> None:
        print("\n" + "=" * 65)
        print(f"{'REPORT DI PROFILAZIONE':^65}")
        print("=" * 65)
        print(f"{'Metodo':<34} | {'Chiamate':<9} | {'Tempo totale (s)':<15}")
        print("-" * 65)

        ordered = sorted(
            cls.stats.items(),
            key=lambda item: item[1]["time"],
            reverse=True,
        )

        for name, data in ordered:
            print(
                f"{name:<34} | {data['calls']:<9} | {data['time']:.6f}"
            )

        print("=" * 65)


def profile(name: str):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = function(*args, **kwargs)
            duration = time.perf_counter() - start
            Profiler.record(name, duration)
            return result

        return wrapper

    return decorator
