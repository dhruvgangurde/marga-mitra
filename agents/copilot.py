"""The copilot: one step at a time on the city API and the screen, chosen by a model or, without one, by fixed rules."""
from __future__ import annotations

import argparse
import asyncio
import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from agents import copilot_rules
from agents.copilot_tools import CAL, TOOLS, Next, ToolError, Turn, step
from agents.llm import get_llm, llm_settings
from agents.tools import days_label
from contracts.interfaces import Emit, LLMClient
from contracts.models import CopilotReply, WsEvent

SYSTEM = (Path(__file__).resolve().parent / "prompts" / "copilot.md").read_text(encoding="utf-8")
MAX_CALLS = 6
MAX_FINISH = 200
TODAY = 8
NO_ANSWER = "The plan service did not answer. Try again."
_reply_ids = itertools.count(1)


def _client(base: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base, timeout=10)


def user_text(message: str, context: dict[str, Any], results: list[str]) -> str:
    day = context.get("day", TODAY)
    screen = (f"{days_label(CAL, day, day)}, tab {context.get('tab') or 'negotiation'}, "
              f"selected {context.get('selected_work') or 'none'}")
    done = ("Done so far:\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(results, 1))
            if results else "Done so far: nothing yet")
    return f"Request: {message}\nScreen: {screen}\n{done}\nChoose the next step."


async def _run(t: Turn, n: Next) -> None:
    t.calls += 1
    t.results.append(await TOOLS[n.tool](t, n))


async def _run_rules(t: Turn, message: str) -> None:
    for n in copilot_rules.plan(message):
        if t.calls >= MAX_CALLS or t.failed:
            break
        await _run(t, n)


@dataclass
class _Said:
    """What the model contributed to a turn, kept outside the loop so a failed step cannot lose it."""
    used: bool = False
    finish: str | None = None


async def _run_model(t: Turn, llm: LLMClient, message: str, context: dict[str, Any], said: _Said) -> None:
    """Ask for one step at a time until the model finishes, goes quiet or the steps run out."""
    asked = False
    while t.calls < MAX_CALLS and not t.failed:
        n = await llm.structured(SYSTEM, user_text(message, context, t.results), Next,
                                 model=llm_settings().copilot_model, max_tokens=300)
        if n is None:
            if not asked:
                await _run_rules(t, message)  # no usable answer at all: the fixed rules take over
            return
        asked = said.used = True
        if n.tool == "finish":
            text = (n.text or "").strip()
            if text and len(text) <= MAX_FINISH and not any(c.isdigit() for c in text):
                said.finish = text
            return
        await _run(t, n)


async def _stalled(t: Turn) -> None:
    for s in list(t.steps):
        if s.status == "running":
            await step(t, s.text, NO_ANSWER, "needs", s.step_id)


async def run_copilot(message: str, context: dict[str, Any], api_base: str, emit: Emit) -> CopilotReply:
    reply_id = f"CP-{next(_reply_ids)}"
    said = _Said()
    async with _client(api_base) as client:
        t = Turn(reply_id=reply_id, emit=emit, client=client, plan_id=context.get("plan_id"))
        llm = get_llm()
        try:
            if llm.provider == "none":
                await _run_rules(t, message)
            else:
                await _run_model(t, llm, message, context, said)
        except ToolError:
            await _stalled(t)
            return CopilotReply(reply_id=reply_id, text="I could not finish: the plan service did not answer.",
                                steps=t.steps, actions=t.actions, used_llm=said.used)
    if t.calls >= MAX_CALLS and said.finish is None:
        text = f"I stopped after {MAX_CALLS} steps. {t.summary}".strip()
    else:
        text = said.finish or t.summary or copilot_rules.HELP
    return CopilotReply(reply_id=reply_id, text=text, steps=t.steps, actions=t.actions, used_llm=said.used)


async def _print_event(event: WsEvent) -> None:
    d = event.data
    if event.type == "copilot.step":
        print(f"STEP {d['status']} {d['text']}" + (f" · {d['detail']}" if d.get("detail") else ""))
    elif event.type == "ui.action":
        print(f"ACTION {d['action']} " + " ".join(f"{k}={v}" for k, v in d["args"].items()))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m agents.copilot")
    parser.add_argument("--ask", required=True, help="what to ask the copilot")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="where the city API answers")
    parser.add_argument("--day", type=int, default=TODAY, help="the day on screen")
    parser.add_argument("--tab", default="negotiation", help="the tab on screen")
    args = parser.parse_args(argv)
    context = {"day": args.day, "tab": args.tab, "selected_work": None, "plan_id": None}
    reply = asyncio.run(run_copilot(args.ask, context, args.api, _print_event))
    print(f"REPLY {reply.text}")
    print("(model)" if reply.used_llm else "(rules)")


if __name__ == "__main__":
    main()
