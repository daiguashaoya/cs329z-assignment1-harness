"""Source fidelity, paging boundaries and input isolation regressions."""

import pytest

from cs329z_hw1 import adapters
from cs329z_hw1.tokens import count_tokens


def build(text, title="Test document"):
    return adapters.run_build_doc_index([{"doc_id": "test", "title": title, "text": text}])


def test_empty_corpus_and_empty_document():
    index = adapters.run_build_doc_index([])
    assert adapters.run_search_docs(index, "policy") == []
    with pytest.raises(LookupError):
        adapters.run_read_doc(index, "missing")
    with pytest.raises(ValueError):
        adapters.run_read_doc(build(""), "test")


def test_search_excerpt_quotes_relevant_source_and_points_to_its_line():
    text = "Background material.\n" * 100 + "Quokka equipment requires approval from the site lead.\n"
    index = build(text)
    result = adapters.run_search_docs(index, "quokka approval", 1)[0]
    assert result["snippet"] in text
    assert "Quokka" in result["snippet"]
    assert count_tokens(result["snippet"]) <= 150
    window = adapters.run_read_doc(index, "test", result["start_line"])
    assert "Quokka equipment" in window["text"]


def test_full_line_windows_preserve_blank_lines_and_advance():
    lines = [f"Line {i}: " + "x" * 700 if i % 3 else "" for i in range(25)]
    index = build("\n".join(lines) + "\n")
    start, collected = 1, []
    while start <= len(lines):
        window = adapters.run_read_doc(index, "test", start)
        expected = lines[start - 1:window["end_line"]]
        assert window["text"] == "\n".join(expected)
        assert count_tokens(window["text"]) <= 1500
        collected.extend(expected)
        start = window["end_line"] + 1
    assert collected == lines


def test_single_line_above_preferred_size_still_fits_hard_limit():
    index = build("x" * 5000 + "\nnext")
    first = adapters.run_read_doc(index, "test")
    assert first["end_line"] == 1 and len(first["text"]) == 5000
    assert adapters.run_read_doc(index, "test", 2)["text"] == "next"
    with pytest.raises(ValueError):
        adapters.run_read_doc(build("x" * 6001), "test")


def test_index_snapshots_source_and_outputs_do_not_mutate_it():
    docs = [{"doc_id": "test", "title": "Original", "text": "A quokka needs four words here."}]
    index = adapters.run_build_doc_index(docs)
    docs[0]["text"] = "Changed"
    docs[0]["title"] = "Changed"
    result = adapters.run_search_docs(index, "quokka", 1)[0]
    result["snippet"] = "Changed"
    assert adapters.run_search_docs(index, "quokka", 1)[0]["title"] == "Original"
    assert adapters.run_read_doc(index, "test")["text"] == "A quokka needs four words here."


@pytest.mark.parametrize("query,k", [("?!", 5), ("policy", 0), ("policy", -1)])
def test_empty_query_or_nonpositive_k(query, k):
    assert adapters.run_search_docs(build("Policy details are here."), query, k) == []
