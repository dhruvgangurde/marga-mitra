"""One agent per department: it picks among cost-checked options and says why in plain words."""
from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from agents import fallback
from agents.conflicts import cluster_conflicts, detect_conflicts
from agents.llm import get_llm
from agents.tools import current_state, day_label, days_label, options_for
from contracts import costs
from contracts.fakes import fake_naive_plan, tiny_scenario
from contracts.interfaces import LLMClient
from contracts.models import (
    Conflict,
    Dept,
    MessageType,
    Mode,
    NegotiationMessage,
    NegotiationOption,
    Plan,
    Scenario,
)

PROMPTS = Path(__file__).resolve().parent / "prompts"
DEPT_NAMES = {"water": "Water", "drainage": "Drainage", "gas": "Gas", "power": "Power", "telecom": "Telecom",
              "roads": "Roads"}
MAX_REASON = 160


class Pick(BaseModel):
    # a plain model, not contracts.models.Model, so both providers accept the schema; the code enforces the limits
    option: int
    reason: str


def system_prompt(dept: Dept) -> str:
    base = (PROMPTS / "base.md").read_text(encoding="utf-8").strip()
    own = (PROMPTS / f"{dept.value}.md").read_text(encoding="utf-8").strip()
    return f"{base}\n\n{own}"


def cost_words(amount: int) -> str:
    if amount < 0:
        return f"saves {costs.inr(-amount)}"
    if amount > 0:
        return f"costs {costs.inr(amount)} more"
    return "no extra cost"


def _cost_sentence(amount: int) -> str:
    words = cost_words(amount)
    return "No extra cost." if amount == 0 else f"{words[0].upper()}{words[1:]}."


def _clean_reason(reason: str) -> str:
    """The reason is shown as written, so it may hold no digit: every number on screen comes from the cost tables."""
    text = reason.strip().rstrip(".").strip()
    if not text or any(ch.isdigit() for ch in text):
        return ""
    return f"{text[: MAX_REASON - 1].strip()}."


def _user_text(conflict: Conflict, work_id: str, options: list[NegotiationOption], scenario: Scenario, plan: Plan,
               proposed: int) -> str:
    work = next(w for w in scenario.works if w.work_id == work_id)
    asked_end = work.requested_start + work.modes[0].duration_days - 1
    start, end, mode, _ = current_state(plan, work)
    method = "open cut" if mode == Mode.open_cut else "trenchless"
    lines = [
        f"Clash: {conflict.note}",
        f"Your work: {work.work_id} · {work.title}, {work.road_name} · {work.length_m:g} m"
        f" · asked for {days_label(scenario, work.requested_start, asked_end)}"
        f" · allowed {day_label(scenario, work.earliest_start)} to {day_label(scenario, work.latest_end)}"
        f" · priority {work.priority} of 5",
        f"Now planned: {days_label(scenario, start, end)} · {method}",
        "Options:",
        *(f"{i}. {o.label} · {cost_words(o.cost_delta_inr)}" for i, o in enumerate(options)),
        f"The coordinator proposes option {proposed}.",
        "Answer with the number of the option your department takes, or -1 if none of them can work,"
        " and one short reason without numbers.",
    ]
    return "\n".join(lines)


class DepartmentAgent:
    def __init__(self, dept: Dept, llm: LLMClient | None = None) -> None:
        self.dept = dept
        self.llm = llm or get_llm()

    async def respond(self, conflict: Conflict, work_id: str, options: list[NegotiationOption], scenario: Scenario,
                      plan: Plan, run_id: str, round_no: int, msg_id: str,
                      proposed: int = 0) -> tuple[NegotiationMessage, bool]:
        choice, reason, used = -1, "", False
        if options:
            pick = await self.llm.structured(system_prompt(self.dept), _user_text(conflict, work_id, options, scenario, plan, proposed),
                                             Pick, max_tokens=200)
            if pick is not None and -1 <= pick.option < len(options):
                choice, reason, used = pick.option, _clean_reason(pick.reason), True
            else:
                choice = fallback.choose(options)
        kind = MessageType.ESCALATE if choice == -1 else MessageType.ACCEPT if choice == proposed else MessageType.COUNTER
        body = self._body(kind, work_id, options[choice] if choice >= 0 else None, reason)
        message = NegotiationMessage(msg_id=msg_id, run_id=run_id, round=round_no, sender=self.dept.value,
                                     recipients=["coordinator"], type=kind, work_ids=[work_id], body=body,
                                     options=options, chosen_option=choice if choice >= 0 else None,
                                     ts=datetime.now(UTC))
        return message, used

    def _body(self, kind: MessageType, work_id: str, option: NegotiationOption | None, reason: str) -> str:
        name = DEPT_NAMES[self.dept.value]
        if option is None:
            body = f"{name} cannot take any of these options for {work_id}. The scheduler decides."
        else:
            letter, words = option.label.split(" · ", 1)
            verb = "accepts" if kind == MessageType.ACCEPT else "asks for"
            body = (f"{name} {verb} option {letter} for {work_id}: {words[0].lower()}{words[1:]}. "
                    f"{_cost_sentence(option.cost_delta_inr)}")
        return f"{body} {reason}" if reason else body


async def demo() -> None:
    scenario = tiny_scenario()
    plan = fake_naive_plan(scenario)
    works = {w.work_id: w for w in scenario.works}
    n = 0
    for cluster in cluster_conflicts(detect_conflicts(scenario, plan)):
        for clash in cluster:
            for work_id in clash.work_ids:
                n += 1
                options = options_for(clash, scenario, plan, work_id)
                message, used = await DepartmentAgent(works[work_id].dept).respond(
                    clash, work_id, options, scenario, plan, "RUN-DEMO", 1, f"M1{n}")
                print(f"{message.type.value} {message.body}{'' if used else ' (fallback)'}")
                if message.type == MessageType.COUNTER:
                    for o in options:
                        print(f"    {o.label} · {cost_words(o.cost_delta_inr)}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m agents.department")
    parser.add_argument("--demo", action="store_true", required=True, help="run one negotiation round on the tiny scenario")
    parser.parse_args(argv)
    asyncio.run(demo())


if __name__ == "__main__":
    main()
