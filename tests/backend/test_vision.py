import pytest

from backend.app.verify import vision
from backend.app.verify.vision import RepairView, repair_check

BEFORE, AFTER = b"before-photo", b"after-photo"


class FakeLLM:
    provider = "fake"

    def __init__(self, answer: RepairView | None) -> None:
        self.answer = answer
        self.calls: list[dict] = []

    async def structured(self, system, user, schema, model=None, images=None, max_tokens=800):
        self.calls.append({"system": system, "schema": schema, "model": model, "images": images})
        return self.answer


def _view(closed=True, patched=True, debris=False, confidence=0.9) -> RepairView:
    return RepairView(closed=closed, patched=patched, debris=debris, confidence=confidence, note="ignore me")


def _use(monkeypatch, answer: RepairView | None) -> FakeLLM:
    llm = FakeLLM(answer)
    monkeypatch.setattr(vision, "llm_and_model", lambda: (llm, "vision-test-model"))
    return llm


@pytest.mark.parametrize(("answer", "status", "detail"), [
    (None, "pending", "A person will check the repair"),
    (_view(confidence=0.5), "warn", "The repair check is not sure"),
    (_view(), "ok", "Trench closed, surface patched, no debris"),
    (_view(patched=False), "fail", "The surface is not patched"),
    (_view(closed=False, debris=True), "fail", "The trench is still open, debris is left on the road"),
], ids=["no-answer", "not-sure", "clean", "not-patched", "open-and-debris"])
async def test_answers(monkeypatch, answer, status, detail):
    _use(monkeypatch, answer)
    check = await repair_check(BEFORE, AFTER)
    assert (check.name, check.status, check.detail) == ("repair", status, detail)


async def test_photos_and_model_are_passed(monkeypatch):
    llm = _use(monkeypatch, _view())
    await repair_check(BEFORE, AFTER)
    assert llm.calls[0]["images"] == [BEFORE, AFTER]
    assert llm.calls[0]["model"] == "vision-test-model"
    assert llm.calls[0]["schema"] is RepairView


async def test_no_llm_module(monkeypatch):
    monkeypatch.setattr(vision, "llm_and_model", lambda: (None, None))
    assert (await repair_check(BEFORE, AFTER)).status == "pending"


async def test_provider_none_is_pending(monkeypatch):
    llm = pytest.importorskip("agents.llm")
    monkeypatch.setenv("LLM_PROVIDER", "none")
    llm.get_llm.cache_clear()
    try:
        check = await repair_check(BEFORE, AFTER)
    finally:
        llm.get_llm.cache_clear()
    assert (check.status, check.detail) == ("pending", "A person will check the repair")
