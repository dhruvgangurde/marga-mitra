"""The one rule for every number on the Impact page: the median and the 10th to 90th percentile range."""
from __future__ import annotations

import statistics

from contracts.models import Stat


def stat(values: list[float]) -> Stat:
    if not values:
        raise ValueError("no values")
    if len(values) == 1:
        v = round(float(values[0]), 1)
        return Stat(median=v, low=v, high=v)  # quantiles needs two points
    cuts = statistics.quantiles(values, n=10, method="inclusive")
    return Stat(median=round(statistics.median(values), 1), low=round(cuts[0], 1), high=round(cuts[-1], 1))
