"""The whole decision when no model is set up, and the safety net when a model answer is missing or invalid."""
from __future__ import annotations

from contracts.models import NegotiationOption


def choose(options: list[NegotiationOption]) -> int:
    """Index of the cheapest option, the lower index on a tie; -1 when there is nothing to choose."""
    if not options:
        return -1
    return min(range(len(options)), key=lambda i: (options[i].cost_delta_inr, i))
