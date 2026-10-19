"""Every LLM adapter must pass LLMContract. Add a subclass when you add an adapter."""

from __future__ import annotations

import pytest

from aikit.components.llm.fake import FakeLLM
from aikit.components.llm.openai_compat import OpenAICompatLLM
from aikit.core.errors import LLMError
from aikit.core.ports import LLM
from aikit.core.types import LLMResponse, Message, ToolCall, ToolSpec
from tests.contract.gateway import MockGateway

LOOKUP = ToolSpec(
    name="lookup",
    description="Look up stock for a sku",
    parameters={"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]},
)


class LLMContract:
    @pytest.fixture
    def llm(self) -> LLM:
        raise NotImplementedError

    def test_satisfies_protocol(self, llm: LLM) -> None:
        assert isinstance(llm, LLM)
        assert llm.model

    async def test_chat_returns_text(self, llm: LLM) -> None:
        response = await llm.chat([Message.system("Be brief."), Message.user("hello there")])
        assert isinstance(response, LLMResponse)
        assert response.content
        assert response.usage.prompt_tokens >= 0

    async def test_tool_call_round_trip(self, llm: LLM) -> None:
        first = await llm.chat([Message.user("lookup stock for sku 1")], tools=[LOOKUP])
        assert first.tool_calls and first.tool_calls[0].name == "lookup"
        call = first.tool_calls[0]
        second = await llm.chat(
            [
                Message.user("lookup stock for sku 1"),
                Message.assistant(None, [call]),
                Message.tool(call.id, '{"stock": 4}', name="lookup"),
            ],
            tools=[LOOKUP],
        )
        assert second.content and not second.tool_calls

    async def test_stream_yields_text(self, llm: LLM) -> None:
        parts = [part async for part in llm.stream([Message.user("say hello")])]
        assert parts and all(isinstance(p, str) for p in parts)
        assert "".join(parts).strip()


class TestFakeLLM(LLMContract):
    @pytest.fixture
    def llm(self) -> LLM:
        return FakeLLM()


class TestOpenAICompatLLM(LLMContract):
    @pytest.fixture
    def llm(self) -> LLM:
        llm = OpenAICompatLLM(model="m", base_url="https://gateway.test/v1", api_key="secret")
        llm.http._transport = MockGateway().transport
        return llm


# ---------------------------------------------------------------- adapter specifics


def make_llm(gateway: MockGateway, **kwargs: object) -> OpenAICompatLLM:
    llm = OpenAICompatLLM(
        model="m",
        base_url="https://gateway.test/v1",
        api_key="secret",
        retry_backoff=0,
        **kwargs,  # type: ignore[arg-type]
    )
    llm.http._transport = gateway.transport
    return llm


async def test_openai_compat_sends_auth_and_tool_messages() -> None:
    gateway = MockGateway()
    llm = make_llm(gateway, temperature=0.2, extra_body={"user": "svc"})
    call = ToolCall(id="c1", name="lookup", arguments={"sku": "1"})
    await llm.chat([Message.user("x"), Message.assistant(None, [call]), Message.tool("c1", "ok")])
    body = gateway.requests[-1]
    assert gateway.headers[-1]["authorization"] == "Bearer secret"
    assert body["temperature"] == 0.2
    assert body["user"] == "svc"
    assert body["messages"][1]["tool_calls"][0]["function"]["arguments"] == '{"sku": "1"}'
    assert body["messages"][2] == {"role": "tool", "content": "ok", "tool_call_id": "c1"}


async def test_openai_compat_retries_transient_errors() -> None:
    gateway = MockGateway(fail_first=2, fail_status=503)
    response = await make_llm(gateway, max_retries=3).chat([Message.user("hi")])
    assert response.content == "echo: hi"
    assert len(gateway.requests) == 3


async def test_openai_compat_gives_up_after_max_retries() -> None:
    gateway = MockGateway(fail_first=5, fail_status=429)
    with pytest.raises(LLMError, match="after 2 attempts"):
        await make_llm(gateway, max_retries=1).chat([Message.user("hi")])


async def test_openai_compat_does_not_retry_client_errors() -> None:
    gateway = MockGateway(fail_first=1, fail_status=400)
    with pytest.raises(LLMError) as info:
        await make_llm(gateway).chat([Message.user("hi")])
    assert info.value.status_code == 400
    assert len(gateway.requests) == 1


async def test_fake_llm_replays_script() -> None:
    llm = FakeLLM(
        responses=[{"tool_calls": [{"name": "lookup", "arguments": {"sku": "9"}}]}, "done"]
    )
    first = await llm.chat([Message.user("x")])
    second = await llm.chat([Message.user("x")])
    assert first.tool_calls[0].arguments == {"sku": "9"}
    assert second.content == "done"
