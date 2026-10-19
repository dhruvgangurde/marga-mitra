import asyncio
import base64
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, SecretStr

from agents import llm as llm_module
from agents.llm import AnthropicClient, GeminiClient, get_llm


class Choice(BaseModel):
    option: int
    reason: str


@pytest.fixture(autouse=True)
def _fresh_llm():
    get_llm.cache_clear()
    yield
    get_llm.cache_clear()


async def test_no_model_returns_none(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    llm = get_llm()
    assert llm.provider == "none"
    assert await llm.structured("s", "u", Choice) is None


def test_provider_needs_a_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    assert get_llm().provider == "anthropic"
    get_llm.cache_clear()
    monkeypatch.setenv("LLM_API_KEY", "")
    assert get_llm().provider == "none"


def _client(tmp_path, fake, cache=True, timeout_s=25.0):
    client = AnthropicClient(SecretStr("test-key"), "m", cache_dir=tmp_path if cache else None, timeout_s=timeout_s)
    client._call = fake
    return client


def _counting_fake():
    calls = []

    async def fake(system, user, schema, model, images, max_tokens):
        calls.append(user)
        return Choice(option=1, reason="ok")

    return fake, calls


async def test_cache_replays_identical_calls(tmp_path):
    fake, calls = _counting_fake()
    client = _client(tmp_path, fake)
    first = await client.structured("s", "u", Choice)
    second = await client.structured("s", "u", Choice)
    assert first == second == Choice(option=1, reason="ok")
    assert len(calls) == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


async def test_no_cache_dir_calls_every_time(tmp_path):
    fake, calls = _counting_fake()
    client = _client(tmp_path, fake, cache=False)
    await client.structured("s", "u", Choice)
    await client.structured("s", "u", Choice)
    assert len(calls) == 2


async def test_different_user_text_is_a_miss(tmp_path):
    fake, calls = _counting_fake()
    client = _client(tmp_path, fake)
    await client.structured("s", "u1", Choice)
    await client.structured("s", "u2", Choice)
    assert len(calls) == 2
    assert len(list(tmp_path.glob("*.json"))) == 2


async def test_broken_cache_file_is_a_miss(tmp_path):
    fake, calls = _counting_fake()
    client = _client(tmp_path, fake)
    await client.structured("s", "u", Choice)
    next(tmp_path.glob("*.json")).write_text("not json", encoding="utf-8")
    assert await client.structured("s", "u", Choice) == Choice(option=1, reason="ok")
    assert len(calls) == 2


async def test_timeout_gives_none(tmp_path):
    async def slow(*args):
        await asyncio.sleep(1)
        return Choice(option=1, reason="ok")

    assert await _client(tmp_path, slow, timeout_s=0.05).structured("s", "u", Choice) is None


async def test_error_gives_none_and_no_cache_file(tmp_path):
    async def boom(*args):
        raise RuntimeError("down")

    assert await _client(tmp_path, boom).structured("s", "u", Choice) is None
    assert list(tmp_path.glob("*")) == []


async def test_wrong_type_gives_none(tmp_path):
    async def wrong(*args):
        return {"option": 1, "reason": "ok"}

    assert await _client(tmp_path, wrong).structured("s", "u", Choice) is None
    assert list(tmp_path.glob("*")) == []


async def test_key_never_leaks(tmp_path):
    fake, _ = _counting_fake()
    client = _client(tmp_path, fake)
    await client.structured("s", "u", Choice)
    assert "test-key" not in repr(client)
    assert "test-key" not in str(client)
    assert all("test-key" not in f.read_text(encoding="utf-8") for f in tmp_path.glob("*"))


JPEG = b"\xff\xd8\xff" + bytes(20)
PNG = b"\x89PNG\r\n\x1a\n" + bytes(20)


class FakeAnthropic:
    init: dict = {}
    parse_kwargs: dict = {}

    def __init__(self, **kwargs):
        FakeAnthropic.init = kwargs
        self.messages = SimpleNamespace(parse=self._parse)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def _parse(self, **kwargs):
        FakeAnthropic.parse_kwargs = kwargs
        return SimpleNamespace(parsed_output=Choice(option=0, reason="ok"))


@pytest.fixture
def fake_anthropic(monkeypatch):
    monkeypatch.setattr(llm_module, "AsyncAnthropic", FakeAnthropic)
    return FakeAnthropic


async def _ask_claude(images=None):
    client = AnthropicClient(SecretStr("test-key"), "claude-haiku-5-5", cache_dir=None)
    return await client.structured("sys", "Pick one", Choice, images=images)


async def test_claude_call_with_a_jpeg(fake_anthropic):
    assert await _ask_claude([JPEG]) == Choice(option=0, reason="ok")
    assert fake_anthropic.init["api_key"] == "test-key"
    kw = fake_anthropic.parse_kwargs
    assert kw["output_format"] is Choice
    assert kw["system"] == "sys"
    assert kw["max_tokens"] == 800
    assert kw["model"] == "claude-haiku-5-5"
    assert "temperature" not in kw
    image, text = kw["messages"][0]["content"]
    assert image == {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                 "data": base64.b64encode(JPEG).decode()}}
    assert text == {"type": "text", "text": "Pick one"}


async def test_claude_call_with_a_png(fake_anthropic):
    await _ask_claude([PNG])
    image = fake_anthropic.parse_kwargs["messages"][0]["content"][0]
    assert image["source"]["media_type"] == "image/png"


async def test_claude_call_without_images_sends_plain_text(fake_anthropic):
    await _ask_claude()
    assert fake_anthropic.parse_kwargs["messages"][0]["content"] == "Pick one"


async def test_gemini_call(monkeypatch):
    seen = {}

    class FakeModels:
        async def generate_content(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(parsed=Choice(option=0, reason="ok"))

    class FakeAio:
        models = FakeModels()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    class FakeGenai:
        def __init__(self, api_key):
            seen["api_key"] = api_key
            self.aio = FakeAio()

    monkeypatch.setattr(llm_module.genai, "Client", FakeGenai)
    client = GeminiClient(SecretStr("test-key"), "gemini-test", cache_dir=None)
    assert await client.structured("sys", "Pick one", Choice, images=[JPEG]) == Choice(option=0, reason="ok")
    assert seen["api_key"] == "test-key"
    assert seen["model"] == "gemini-test"
    config = seen["config"]
    assert config.response_schema is Choice
    assert config.response_mime_type == "application/json"
    assert config.system_instruction == "sys"
    assert seen["contents"][-1] == "Pick one"
    assert len(seen["contents"]) == 2
