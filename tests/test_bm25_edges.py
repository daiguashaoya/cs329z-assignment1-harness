"""Additional empty-corpus and score-normalization regressions."""

from math import log

import pytest

from cs329z_hw1 import adapters


@pytest.mark.parametrize("docs", [[], ["", "   ", "?!"]])
def test_corpus_without_tokens(docs):
    index = adapters.run_bm25_build(docs)
    assert adapters.run_bm25_search(index, "apple", 10) == []
    assert adapters.run_bm25_search(index, "", 10) == []


@pytest.mark.parametrize("k", [0, -1])
def test_nonpositive_k(k):
    index = adapters.run_bm25_build(["apple"])
    assert adapters.run_bm25_search(index, "apple", k) == []


def test_empty_documents_affect_scores_and_preserve_ids():
    index = adapters.run_bm25_build(["", "apple", "   ", "apple apple"])
    results = adapters.run_bm25_search(index, "apple", 10)
    # N=4, df=2, avgdl=3/4. The lengths are 1 and 2 respectively.
    expected = [
        (1, log(2) * 2.5 / (1 + 1.5 * (0.25 + 0.75 / 0.75))),
        (3, log(2) * 5 / (2 + 1.5 * (0.25 + 0.75 * 2 / 0.75))),
    ]
    expected.sort(key=lambda pair: (-pair[1], pair[0]))
    assert [doc_id for doc_id, _ in results] == [doc_id for doc_id, _ in expected]
    assert [score for _, score in results] == pytest.approx(
        [score for _, score in expected], abs=1e-6
    )
