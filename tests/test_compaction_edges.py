"""Check auxiliary budgets, fresh evidence fidelity and degraded summarizers."""

import pytest

from cs329z_hw1 import adapters
from cs329z_hw1.agent.compaction import summarize
from cs329z_hw1.tokens import count_message_tokens, count_tokens
from cs329z_hw1.types import AgentConfig
from tests.fixture_tools import make_fixture_tools
from tests.helpers import events
from tests.test_compaction import run_long_session


def test_fresh_observations_are_verbatim_even_when_history_compacts(scripted, canned_aux):
    lm, _, session, _, _ = run_long_session(scripted, canned_aux)
    results = events(session.transcript, "tool_result")
    for send_number in range(12):
        for tool_number in range(4):
            observation = results[send_number * 4 + tool_number]["content"]
            next_call = lm.calls[send_number * 5 + tool_number + 1]
            assert any(observation in message["content"] for message in next_call)
    assert canned_aux.calls
    assert all(count_message_tokens(call) <= 4000 for call in canned_aux.calls)


@pytest.mark.parametrize("mode", ["missing", "empty", "oversized", "failed"])
def test_unavailable_or_unbounded_summary_does_not_break_the_loop(scripted, mode):
    aux = None
    if mode == "empty":
        aux = scripted([""], repeat_last=True)
    elif mode == "oversized":
        aux = scripted(["summary " * 10000], repeat_last=True)
    elif mode == "failed":
        def aux(messages):
            raise RuntimeError("Auxiliary unavailable")
    lm, _, session, results, _ = run_long_session(scripted, aux)
    assert all(result.status == "done" for result in results)
    assert len(lm.calls) == 60
    assert all(count_message_tokens(call) <= 4000 for call in lm.calls)
    assert len(events(session.transcript, "assistant")) == 60


def test_auxiliary_input_is_chunked_as_well_as_output_bounded(scripted):
    aux = scripted(["Durable facts."], repeat_last=True)
    text = "begin " + "large source content\n" * 5000 + "end"
    summary = summarize([{"role": "assistant", "content": text}], aux, 1000, 100)
    assert len(aux.calls) > 1
    assert all(count_message_tokens(call) <= 1000 for call in aux.calls)
    assert count_tokens(summary) <= 100
    assert "end" in aux.calls[-1][-1]["content"]


def test_impossible_current_request_is_rejected_before_any_model_call(scripted):
    lm = scripted(["Should not be called."])
    session = adapters.run_agent_session(lm, [], AgentConfig(context_budget=1000))
    with pytest.raises(ValueError, match="context_budget"):
        session.send("x" * 10000)
    assert not lm.calls


def test_large_tool_result_is_bounded_before_both_log_and_context(scripted, canned_aux):
    lm = scripted([
        {"tool_call": {"name": "big_output", "args": {"n_lines": 3000}}},
        "Done.",
    ])
    session = adapters.run_agent_session(
        lm, make_fixture_tools().tools,
        AgentConfig(context_budget=4000, aux_lm=canned_aux),
    )
    session.send("Print. Keep request REF-2026.")
    observation = events(session.transcript, "tool_result")[0]["content"]
    assert count_tokens(observation) <= 1000
    assert "omitted" in observation
    assert "line 1:" in observation and "line 3000:" in observation
    assert observation in lm.calls[1][-1]["content"]
