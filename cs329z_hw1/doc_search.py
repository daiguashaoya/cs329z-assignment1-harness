"""BM25 document search with source excerpts and bounded line windows."""

from dataclasses import dataclass
import re

from cs329z_hw1.bm25 import BM25Index, build_index, search
from cs329z_hw1.tokenizer import tokenize
from cs329z_hw1.tokens import CHARS_PER_TOKEN
from cs329z_hw1.types import DocWindow, SearchResult


SNIPPET_CHARS = 150 * CHARS_PER_TOKEN
WINDOW_CHARS = 1000 * CHARS_PER_TOKEN  # Leave room for other tool results.
MAX_WINDOW_CHARS = 1500 * CHARS_PER_TOKEN
WORD = re.compile(r"[a-z0-9]+", re.IGNORECASE | re.ASCII)


@dataclass
class DocumentIndex:
    documents: list[dict]
    lines: dict[str, list[str]]
    bm25: BM25Index


def build_doc_index(docs: list[dict]) -> DocumentIndex:
    """Snapshot source metadata/text and reuse the existing BM25 index."""
    documents = []
    lines = {}
    for doc in docs:
        doc_id = doc["doc_id"]
        if doc_id in lines:
            raise ValueError(f"Duplicate document ID: {doc_id}")
        documents.append({key: doc[key] for key in ("doc_id", "title", "text")})
        lines[doc_id] = doc["text"].splitlines()
    bm25 = build_index([doc["title"] + "\n" + doc["text"] for doc in documents])
    return DocumentIndex(documents, lines, bm25)


def _excerpt(text: str, terms: set[str], idf: dict[str, float]) -> tuple[str, int]:
    """Choose a literal excerpt covering informative query terms, plus its line."""
    hits = [match for match in WORD.finditer(text) if match.group().lower() in terms]
    if not hits:
        return text[:SNIPPET_CHARS].strip(), 1

    best_start, best_score = 0, (-1.0, -1)
    for hit in hits:
        # Keep context before the match and avoid starting inside a word.
        start = max(0, hit.start() - 100)
        while start > 0 and text[start - 1].isalnum():
            start -= 1
        found = {
            match.group().lower() for match in hits
            if start <= match.start() and match.end() <= start + SNIPPET_CHARS
        }
        score = (sum(idf.get(term, 0.0) for term in sorted(found)), len(found))
        if score > best_score:
            best_start, best_score = start, score

    snippet = text[best_start:best_start + SNIPPET_CHARS].strip()
    start_line = text.count("\n", 0, best_start) + 1
    return snippet, start_line


def search_docs(index: DocumentIndex, query: str, k: int = 5) -> list[SearchResult]:
    terms = set(tokenize(query))
    results = []
    for doc_number, _ in search(index.bm25, query, k):
        doc = index.documents[doc_number]
        snippet, start_line = _excerpt(doc["text"], terms, index.bm25.idf)
        results.append({
            "doc_id": doc["doc_id"], "title": doc["title"], "snippet": snippet,
            "start_line": start_line,
        })
    return results


def read_doc(index: DocumentIndex, doc_id: str, start_line: int = 1) -> DocWindow:
    if doc_id not in index.lines:
        raise LookupError(f"Unknown document ID: {doc_id}")
    lines = index.lines[doc_id]
    if type(start_line) is not int or not 1 <= start_line <= len(lines):
        raise ValueError(f"start_line must be in 1..{len(lines)} for {doc_id}.")

    first = lines[start_line - 1]
    if len(first) > MAX_WINDOW_CHARS:
        # A single oversized line cannot satisfy both full-line fidelity and
        # the token cap. Reject rather than silently lose part of that line.
        raise ValueError("The starting line exceeds the 1500-token window limit.")
    selected = [first]
    size = len(first)
    end_line = start_line
    for line in lines[start_line:]:
        if size + 1 + len(line) > WINDOW_CHARS:
            break
        selected.append(line)
        size += 1 + len(line)
        end_line += 1

    return {
        "doc_id": doc_id, "start_line": start_line, "end_line": end_line,
        "total_lines": len(lines), "text": "\n".join(selected),
    }
