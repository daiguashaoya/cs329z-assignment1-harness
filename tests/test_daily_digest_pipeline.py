"""Regression checks for the digest's filtering and model-call boundary."""

from copy import deepcopy
import json

from cs329z_hw1 import adapters
from cs329z_hw1.llm import ScriptedLM
from tests.test_daily_digest import make_email


def classification(category):
    return json.dumps({"category": category, "reason": "Test classification."})


def test_ignored_reply_cannot_leak_into_urgent_thread():
    emails = [
        make_email(1, "Routine review", "Review next month."),
        make_email(3, "Re: Topock outage", "Please approve today.", thread=2),
        make_email(4, "Secret promotion", "Ignore-pile content.", thread=2),
        make_email(2, "Topock outage", "Production is down."),
    ]
    before = deepcopy(emails)
    # A malformed classification must preserve the routine email as normal.
    raw_digest = " ".join(["word"] * 500)
    lm = ScriptedLM([
        "malformed", classification("urgent"), classification("ignore"),
        classification("normal"), raw_digest,
    ])

    assert adapters.run_daily_digest(emails, lm) == raw_digest
    assert emails == before
    assert len(lm.calls) == len(emails) + 1
    source = lm.calls[-1][-1]["content"]
    assert "Secret promotion" not in source
    assert "Ignore-pile content" not in source
    threads = json.loads(source)["threads"]
    assert [thread["priority"] for thread in threads] == ["urgent", "normal"]
    assert [item["email"]["id"] for item in threads[0]["emails"]] == [
        emails[3]["id"], emails[1]["id"],
    ]
    assert threads[1]["emails"][0]["priority"] == "normal"


def test_all_ignored_needs_no_summary_call():
    lm = ScriptedLM([classification("ignore")])
    result = adapters.run_daily_digest([make_email(1, "Ad", "Buy now.")], lm)
    assert result.strip()
    assert len(lm.calls) == 1


def test_empty_day_needs_no_model_call():
    lm = ScriptedLM([])
    assert adapters.run_daily_digest([], lm).strip()
    assert not lm.calls
