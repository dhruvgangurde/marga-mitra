from sqlalchemy import text
from sqlalchemy.orm import Session

from contracts.models import Dept, Scenario

_DIGITS = {"RUN": 4, "A": 4, "E": 4, "V": 4, "CR": 4, "F": 4, "OV": 0, "EV": 0}
_LETTER = {Dept.water: "W", Dept.drainage: "D", Dept.gas: "G", Dept.power: "P", Dept.telecom: "T", Dept.roads: "R"}


def next_id(s: Session, prefix: str) -> str:
    if prefix not in _DIGITS:
        raise ValueError(f"unknown id prefix {prefix}")
    value = s.execute(text(
        "INSERT INTO id_counters (prefix, value) VALUES (:p, 1) "
        "ON CONFLICT (prefix) DO UPDATE SET value = id_counters.value + 1 RETURNING value"
    ), {"p": prefix}).scalar_one()
    return f"{prefix}-{str(value).zfill(_DIGITS[prefix])}"


def next_work_id(scenario: Scenario, dept: Dept) -> str:
    """New works start at 131 so they never collide with the generated ones."""
    letter = _LETTER[dept]
    nums = [int(n) for w in scenario.works if (n := w.work_id.removeprefix(f"{letter}-")).isdigit()]
    return f"{letter}-{max([130, *nums]) + 1}"
