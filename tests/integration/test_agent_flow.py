from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from aikit.components.guardrails.max_length import MaxLengthGuardrail
from aikit.components.llm.fake import FakeLLM
from aikit.core.context import RunContext
from aikit.core.errors import RunNotFoundError
from aikit.core.policy import Policy
from aikit.core.tooling import BaseTool
from aikit.core.types import Capability, ToolResult, ToolSpec
from aikit.flows.agent import AgentFlow


class RecordingTool(BaseTool):
    def __init__(
        self,
        name: str,
        caps: set[Capability] | None = None,
        delay: float = 0.0,
        fail: bool = False,
    ) -> None:
        self.spec = ToolSpec(
            name=name,
            description=f"{name} tool",
            parameters={"type": "object", "properties": {"q": {"type": "string"}}},
            capabilities=frozenset(caps or {"read"}),
        )
        self.delay = delay
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def run(self, args: dict[str, Any], ctx: RunContext) -> ToolResult:
        self.calls.append(args)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("backend down")
        return ToolResult(content=f"{self.spec.name} ok")


def call(name: str, **args: Any) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": args}]}


async def test_tool_then_answer() -> None:
    lookup = RecordingTool("lookup")
    flow = AgentFlow(llm=FakeLLM([call("lookup", q="x"), "final answer"]), tools=[lookup])
    result = await flow.run("question")
    assert result.status == "completed"
    assert result.answer == "final answer"
    assert result.steps == 2
    assert [c.name for c in result.tool_calls] == ["lookup"]
    assert lookup.calls == [{"q": "x"}]


async def test_write_tool_pauses_and_resumes_with_approval() -> None:
    refund = RecordingTool("refund", caps={"write"})
    flow = AgentFlow(llm=FakeLLM([call("refund", q="1"), "refunded"]), tools=[refund])
    paused = await flow.run("refund please", RunContext(user_id="alice", groups=["g"]))
    assert paused.status == "awaiting_approval"
    assert [c.name for c in paused.pending_approvals] == ["refund"]
    assert refund.calls == []
    assert await flow.pending(paused.run_id)

    done = await flow.resume(paused.run_id, True)
    assert done.status == "completed" and done.answer == "refunded"
    assert refund.calls == [{"q": "1"}]
    assert await flow.pending(paused.run_id) is None


async def test_rejected_approval_is_reported_to_the_model() -> None:
    refund = RecordingTool("refund", caps={"write"})
    llm = FakeLLM([call("refund", q="1")])
    flow = AgentFlow(llm=llm, tools=[refund])
    paused = await flow.run("refund please")
    done = await flow.resume(paused.run_id, {paused.pending_approvals[0].id: False})
    assert refund.calls == []
    assert done.status == "completed"
    assert "Rejected by the human reviewer" in done.answer


async def test_resume_unknown_run() -> None:
    flow = AgentFlow(llm=FakeLLM(), tools=[])
    with pytest.raises(RunNotFoundError):
        await flow.resume("missing", True)


async def test_policy_denies_tools_outside_allowlist() -> None:
    blocked = RecordingTool("blocked")
    flow = AgentFlow(
        llm=FakeLLM([call("blocked"), "ok"]),
        tools=[blocked],
        policy=Policy(allowed_tools=["something_else"]),
    )
    result = await flow.run("go")
    assert blocked.calls == []
    assert result.status == "completed"
    assert "not on the allowlist" in str(flow.llm.calls[-1][-1].content)  # type: ignore[attr-defined]


async def test_unknown_tool_is_denied_not_crashed() -> None:
    flow = AgentFlow(llm=FakeLLM([call("ghost"), "ok"]), tools=[])
    result = await flow.run("go")
    assert result.status == "completed"


async def test_max_steps() -> None:
    lookup = RecordingTool("lookup")
    flow = AgentFlow(llm=FakeLLM([call("lookup")] * 10), tools=[lookup], policy=Policy(max_steps=3))
    result = await flow.run("loop forever")
    assert result.status == "max_steps"
    assert result.steps == 3


async def test_token_budget() -> None:
    flow = AgentFlow(
        llm=FakeLLM([call("lookup"), "never reached"]),
        tools=[RecordingTool("lookup")],
        policy=Policy(max_tokens=1),
    )
    result = await flow.run("spend tokens")
    assert result.status == "budget_exceeded"


async def test_tool_timeout_and_failure_become_error_results() -> None:
    slow = RecordingTool("slow", delay=1.0)
    broken = RecordingTool("broken", fail=True)
    llm = FakeLLM([{"tool_calls": [{"name": "slow"}, {"name": "broken"}]}, "recovered"])
    flow = AgentFlow(llm=llm, tools=[slow, broken], policy=Policy(tool_timeout_s=0.05))
    evts = [e async for e in flow.stream("go")]
    results = {e.data["name"]: e.data for e in evts if e.type == "tool_result"}
    assert results["slow"]["is_error"] and "timed out" in results["slow"]["content"]
    assert results["broken"]["is_error"] and "backend down" in results["broken"]["content"]
    assert evts[-1].data["result"]["status"] == "completed"


async def test_read_only_tools_run_in_parallel() -> None:
    a, b = RecordingTool("a", delay=0.2), RecordingTool("b", delay=0.2)
    llm = FakeLLM([{"tool_calls": [{"name": "a"}, {"name": "b"}]}, "done"])
    flow = AgentFlow(llm=llm, tools=[a, b])
    started = time.perf_counter()
    await flow.run("go")
    assert time.perf_counter() - started < 0.35


async def test_input_guardrail_blocks_run() -> None:
    flow = AgentFlow(llm=FakeLLM(), tools=[], guardrails=[MaxLengthGuardrail(max_chars=5)])
    result = await flow.run("this is far too long")
    assert result.status == "blocked"


async def test_memory_carries_conversation() -> None:
    from aikit.components.memory.buffer import BufferMemory

    llm = FakeLLM(["first", "second"])
    flow = AgentFlow(llm=llm, tools=[], memory=BufferMemory())
    ctx = RunContext(session_id="s1")
    await flow.run("hello", ctx)
    await flow.run("again", RunContext(session_id="s1"))
    roles = [m.role for m in llm.calls[-1]]
    assert roles == ["system", "user", "assistant", "user"]
