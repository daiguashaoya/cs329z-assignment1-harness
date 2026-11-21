"""Control-flow and evidence-boundary checks for multi-hop email QA."""

from copy import deepcopy
import json

import pytest

from cs329z_hw1 import adapters
from cs329z_hw1.llm import ScriptedLM
from tests.test_daily_digest import make_email


def test_two_hops_keep_bridge_evidence_and_filter_citations():
    bridge = make_email(1, "Project escrow", "Cedar Legal handles the escrow.")
    detail = make_email(2, "Cedar Legal", "The escrow account is 123456.")
    original = deepcopy([bridge, detail])
    queries = []

    def search(query, k):
        queries.append(query)
        return [bridge] if len(queries) == 1 else [detail]

    lm = ScriptedLM([
        '{"action":"search","query":"Project escrow"}',
        '{"action":"search","query":"Cedar Legal escrow account"}',
        json.dumps({
            "action": "answer", "answer": "123456",
            "support": [bridge["id"], "invented-id", detail["id"], bridge["id"], {}],
        }),
    ])
    result = adapters.run_email_qa("What is the project's escrow account?", search, lm)
    assert result == {"answer": "123456", "support": [bridge["id"], detail["id"]]}
    assert queries == ["Project escrow", "Cedar Legal escrow account"]
    # The final decision can still read evidence retrieved on the first hop.
    final_context = "\n".join(message["content"] for message in lm.calls[-1])
    assert bridge["body"] in final_context and detail["body"] in final_context
    assert [bridge, detail] == original


def test_repeated_search_requests_stop_at_three():
    queries = []

    def search(query, k):
        queries.append(query)
        return []

    lm = ScriptedLM(['{"action":"search","query":"missing fact"}'], repeat_last=True)
    assert adapters.run_email_qa("Find the fact", search, lm) == {
        "answer": None, "support": [],
    }
    assert len(queries) == 3
    assert len(lm.calls) == 4
    assert json.loads(lm.calls[-1][-1]["content"])["searches_remaining"] == 0


@pytest.mark.parametrize("reply", [
    'null', '[]', '{"action":"search","query":42}',
    '{"action":"answer","answer":"A guess","support":["unseen-id"]}',
    '{"action":"answer","answer":42,"support":[]}',
    '{"action":"answer","answer":"A guess","support":"unseen-id"}',
])
def test_malformed_or_unsupported_answers_abstain(reply):
    def search(query, k):
        pytest.fail("No valid search was requested")

    assert adapters.run_email_qa("Question", search, ScriptedLM([reply])) == {
        "answer": None, "support": [],
    }


def test_answer_can_follow_third_search():
    email = make_email(1, "Fact", "The answer is 42.")
    lm = ScriptedLM([
        '{"action":"search","query":"first"}',
        '{"action":"search","query":"second"}',
        '{"action":"search","query":"third"}',
        json.dumps({"action": "answer", "answer": "42", "support": [email["id"]]}),
    ])
    assert adapters.run_email_qa("Question", lambda query, k: [email], lm) == {
        "answer": "42", "support": [email["id"]],
    }
