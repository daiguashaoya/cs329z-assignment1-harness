"""Verify real bindings, lazy resource reuse and auxiliary-model routing."""

import pytest

from cs329z_hw1 import adapters, data
from cs329z_hw1.agent.cardinal_tools import CardinalTools
from cs329z_hw1.types import AgentConfig
from cs329z_hw1.user import ScriptedUser
from tests.test_daily_digest import make_email


def test_email_data_and_index_load_once_per_session(scripted, monkeypatch):
    emails = [make_email(1, "Apple", "apple"), make_email(2, "Banana", "banana")]
    loads, builds = [], []
    build = adapters.run_bm25_build

    def load_emails():
        loads.append(True)
        return emails

    def build_index(docs):
        builds.append(True)
        return build(docs)

    monkeypatch.setattr(data, "load_emails", load_emails)
    monkeypatch.setattr(adapters, "run_bm25_build", build_index)
    bindings = CardinalTools(scripted([]), AgentConfig())
    assert loads == builds == []
    read = bindings.read_email(emails[0]["id"])
    assert len(loads) == 1 and builds == []
    read["body"] = "caller mutation"
    assert emails[0]["body"] == "apple"
    assert bindings.search_emails("apple")[0]["id"] == emails[0]["id"]
    bindings.search_emails("banana")
    assert len(loads) == len(builds) == 1
    other = CardinalTools(scripted([]), AgentConfig())
    other.search_emails("apple")
    assert len(loads) == len(builds) == 2


def test_pipeline_calls_use_auxiliary_model_not_agent_turns(scripted, monkeypatch):
    emails = [make_email(1, "Note", "Hello")]
    monkeypatch.setattr(data, "load_emails", lambda: emails)
    aux = scripted(["QA from auxiliary", "Digest from auxiliary"])

    def qa(question, search, lm):
        assert lm is aux
        assert search("Note")[0]["id"] == emails[0]["id"]
        return {"answer": lm([{"role": "user", "content": question}]), "support": [emails[0]["id"]]}

    def digest(day, lm):
        assert lm is aux and day == emails
        return lm([{"role": "user", "content": "Digest"}])

    monkeypatch.setattr(adapters, "run_email_qa", qa)
    monkeypatch.setattr(adapters, "run_daily_digest", digest)
    main = scripted([
        {"tool_call": {"name": "email_qa", "args": {"question": "Question"}}},
        {"tool_call": {"name": "daily_digest", "args": {"date": "2001-05-14"}}},
        "Finished.",
    ])
    agent = adapters.run_agent_session(main, None, AgentConfig(aux_lm=aux))
    assert agent.send("Answer and summarize").status == "done"
    assert len(main.calls) == 3 and len(aux.calls) == 2
    assert "QA from auxiliary" in main.calls[1][-1]["content"]
    assert "Digest from auxiliary" in main.calls[2][-1]["content"]


def test_auxiliary_falls_back_only_when_none(scripted):
    main = scripted([])
    assert CardinalTools(main, AgentConfig()).aux_lm is main


def test_documents_load_and_build_only_on_first_use(scripted, monkeypatch):
    loads, builds = [], []
    marker = object()
    monkeypatch.setattr(data, "load_docs", lambda: loads.append(True) or [])
    monkeypatch.setattr(adapters, "run_build_doc_index", lambda docs: builds.append(True) or marker)
    monkeypatch.setattr(adapters, "run_search_docs", lambda index, query, k: (index, query, k))
    monkeypatch.setattr(adapters, "run_read_doc", lambda index, doc_id, start: (index, doc_id, start))
    bindings = CardinalTools(scripted([]), AgentConfig())
    assert loads == builds == []
    assert bindings.search_docs("policy") == (marker, "policy", 5)
    assert bindings.read_doc("policy-id") == (marker, "policy-id", 1)
    assert len(loads) == len(builds) == 1


def test_explicit_empty_tools_stays_empty(scripted):
    tools = []
    agent = adapters.run_agent_session(scripted([]), tools, AgentConfig())
    assert agent.registry.schemas() == []
    assert tools == []


def test_optional_tools_are_callable_without_loading_corpus(scripted, tmp_path, monkeypatch):
    def refuse():
        pytest.fail("An optional tool loaded the email archive")

    monkeypatch.setattr(data, "load_emails", refuse)
    user = ScriptedUser(answers=["Friday"])
    config = AgentConfig(user=user, memory_dir=tmp_path / "memory")
    agent = adapters.run_agent_session(scripted([]), [], config)
    assert not config.memory_dir.exists()
    assert agent.registry.execute("ask_user", {"question": "When?"}).content == "Friday"
    assert agent.registry.execute("recall", {"query": "badge"}).status == "ok"
    assert agent.registry.execute("remember", {"fact": "Badge number 58213"}).status == "ok"
    assert "58213" in agent.registry.execute("recall", {"query": "badge"}).content
    other = adapters.run_agent_session(scripted([]), [], config)
    assert "58213" in other.registry.execute("recall", {"query": "badge"}).content
