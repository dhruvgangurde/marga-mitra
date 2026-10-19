import re
from typing import get_args

import pytest

from agents.copilot_tools import Tool
from agents.department import PROMPTS
from contracts.models import Dept

DEPARTMENT_FILES = [PROMPTS / f"{d.value}.md" for d in Dept]


def lines(path):
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


@pytest.mark.parametrize("path", DEPARTMENT_FILES, ids=lambda p: p.stem)
def test_department_prompts_hold_no_digit(path):
    assert not re.search(r"\d", path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", DEPARTMENT_FILES, ids=lambda p: p.stem)
def test_department_prompts_stay_short(path):
    assert 3 <= len(lines(path)) <= 6


def test_base_prompt_has_only_its_one_minus_one():
    text = (PROMPTS / "base.md").read_text(encoding="utf-8")
    assert text.count("-1") == 1
    assert not re.search(r"\d", text.replace("-1", ""))


@pytest.mark.parametrize("tool", get_args(Tool))
def test_the_copilot_prompt_names_every_step(tool):
    assert tool in (PROMPTS / "copilot.md").read_text(encoding="utf-8")
