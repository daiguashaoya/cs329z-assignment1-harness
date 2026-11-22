"""Boundary ordering and state-isolation checks for the agent loop."""

import pytest

from cs329z_hw1 import adapters
from cs329z_hw1.types import AgentConfig, ToolCall, ToolSpec
from tests.fixture_tools import make_fixture_tools
from tests.helpers import events, truncated


def session(lm, **config):
    fx = make_fixture_tools()
    return adapters.run_agent_session(lm, fx.tools, AgentConfig(**config)), fx


def tool(name, **args):
    return {"tool_call": {"name": name, "args": args}}


def test_final_turn_executes_tool_and_turn_limit_precedes_token_limit(scripted):
    lm = scripted([tool("write_note", text="saved on final turn")])
    agent, fx = session(lm, max_turns=1, token_budget=1)
    result = agent.send("Save the note")
    assert result.status == "max_turns"
    assert fx.notes == ["saved on final turn"]
    assert events(result.transcript, "tool_result")[-1]["status"] == "ok"
    assert len(lm.calls) == 1


@pytest.mark.parametrize("config,status", [
    ({"max_turns": 0}, "max_turns"),
    ({"token_budget": 0}, "token_budget"),
])
def test_zero_budget_does_not_call_model(scripted, config, status):
    lm = scripted([])
    agent, _ = session(lm, **config)
    assert agent.send("Hello").status == status
    assert lm.calls == []


def test_truncated_output_never_executes_even_if_call_looks_complete(scripted):
    reply = adapters.run_format_tool_call("", ToolCall("write_note", {"text": "unsafe"}))
    lm = scripted([truncated(reply), "Recovered."])
    agent, fx = session(lm)
    assert agent.send("Do something").status == "done"
    assert fx.notes == []
    assert events(agent.transcript, "error")


@pytest.mark.parametrize("middle", ["fail", "write_note"])
def test_tool_error_and_denial_reset_malformed_counter(scripted, middle):
    args = {} if middle == "fail" else {"text": "requires approval"}
    lm = scripted([
        tool("missing"), tool("missing"), tool(middle, **args),
        tool("missing"), tool("missing"), "Done.",
    ])
    agent, _ = session(lm, mode="confirm")
    assert agent.send("Proceed").status == "done"
    assert len(lm.calls) == 6
    statuses = [event["status"] for event in events(agent.transcript, "tool_result")]
    assert statuses[2] == ("tool_error" if middle == "fail" else "denied")


def test_mutating_tool_does_not_rewrite_call_log(scripted):
    def mutate(data):
        data["values"].append(2)
        return data

    spec = ToolSpec("mutate", "Change a nested argument", {
        "type": "object", "properties": {"data": {"type": "object"}},
        "required": ["data"],
    }, mutate)
    lm = scripted([tool("mutate", data={"values": [1]}), "Done.", "Again."])
    agent = adapters.run_agent_session(lm, [spec], AgentConfig())
    first = agent.send("Run it")
    assert events(first.transcript, "tool_call")[0]["args"] == {"data": {"values": [1]}}
    first.transcript[0]["content"] = "caller mutation"
    assert agent.transcript[0]["content"] == "Run it"
    agent.send("Continue")
    assert len(events(first.transcript, "user")) == 1


def test_modes_do_not_mutate_shared_config(scripted):
    config = AgentConfig()
    first = adapters.run_agent_session(scripted(["One"]), [], config)
    second = adapters.run_agent_session(scripted(["Two"]), [], config)
    first.set_mode("confirm")
    assert config.mode == "auto"
    assert second.config.mode == "auto"


def test_blank_final_answer_still_returns_nonempty_result(scripted):
    agent, _ = session(scripted(["   "]))
    result = agent.send("Hello")
    assert result.status == "done"
    assert result.text.strip()
