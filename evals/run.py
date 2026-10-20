"""Plan every test case in the five ways of the Impact page and summarize the results."""
from __future__ import annotations


def parse_seeds(text: str) -> list[int]:
    """'1-50' or '1-3,7': comma-separated seeds and inclusive ranges, sorted without duplicates."""
    if not text.strip():
        raise ValueError("no seeds")
    seeds: set[int] = set()
    for item in text.split(","):
        first, sep, last = item.strip().partition("-")
        start = int(first)
        end = int(last) if sep else start
        if end < start:
            raise ValueError(f"range ends before it starts: {item.strip()}")
        if start < 1:
            raise ValueError(f"seeds start at 1: {item.strip()}")
        seeds.update(range(start, end + 1))
    return sorted(seeds)
