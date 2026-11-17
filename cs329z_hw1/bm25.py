"""BM25 retrieval using term-to-document postings, without model calls."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from heapq import nsmallest
from math import log1p

from cs329z_hw1.tokenizer import tokenize


K1 = 1.5
B = 0.75


@dataclass
class BM25Index:
    # Each posting is (document's list position, term frequency).
    postings: dict[str, list[tuple[int, int]]]
    doc_lengths: list[int]
    avgdl: float
    idf: dict[str, float]
    # Precomputed K1 * (1 - B + B * document_length / avgdl).
    length_norms: list[float]


def build_index(docs: list[str]) -> BM25Index:
    """Visit each document once to collect postings and corpus statistics."""
    postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
    doc_lengths = []
    for doc_id, text in enumerate(docs):
        tokens = tokenize(text)
        doc_lengths.append(len(tokens))
        for term, frequency in Counter(tokens).items():
            postings[term].append((doc_id, frequency))

    # Empty documents contribute to both N and the average length.
    doc_count = len(doc_lengths)
    avgdl = sum(doc_lengths) / doc_count if doc_count else 0.0
    # Each document appears once per term, so len(entries) is df(term).
    idf = {
        term: log1p((doc_count - len(entries) + 0.5) / (len(entries) + 0.5))
        for term, entries in postings.items()
    }
    length_norms = [
        K1 * (1 - B + B * length / avgdl) if avgdl else K1 * (1 - B)
        for length in doc_lengths
    ]
    return BM25Index(dict(postings), doc_lengths, avgdl, idf, length_norms)


def search(index: BM25Index, query: str, k: int) -> list[tuple[int, float]]:
    """Score only documents in the query terms' postings and select top-k."""
    if k <= 0:
        return []

    scores: dict[int, float] = defaultdict(float)
    # Deduplicate query terms while keeping a deterministic summation order.
    for term in dict.fromkeys(tokenize(query)):
        entries = index.postings.get(term)
        if not entries:
            continue
        idf = index.idf[term]
        for doc_id, frequency in entries:
            scores[doc_id] += (
                idf * frequency * (K1 + 1)
                / (frequency + index.length_norms[doc_id])
            )

    # Only matching documents have scores. A bounded heap avoids sorting all
    # matches when the requested k is small; lower document ids break ties.
    return nsmallest(k, scores.items(), key=lambda pair: (-pair[1], pair[0]))
