"""Assemble Cardinal tools with session-local, lazily loaded resources."""

from copy import deepcopy
from dataclasses import asdict
import json

from cs329z_hw1 import adapters, data
from cs329z_hw1.cardinal import CARDINAL_TOOLS, cardinal_spec
from cs329z_hw1.tokenizer import tokenize
from cs329z_hw1.types import AgentConfig, Email, LMCallable, ToolSpec


DESCRIPTIONS = {
    "search_emails": "Search email subjects and bodies with BM25 keywords; returns matching emails with IDs.",
    "read_email": "Read the full email for an email_id returned by a search.",
    "email_qa": "Answer a question using up to three email searches and cite supporting email IDs.",
    "daily_digest": "Summarize emails from one UTC date, with urgent work first and irrelevant mail excluded.",
    "search_docs": "Search company policy and project documents; returns document IDs and snippets.",
    "read_doc": "Read a document window from start_line; use returned end_line to continue paging.",
    "run_terminal": "Run a shell command in the configured terminal workspace; returns stdout, stderr and exit status.",
    "remember": "Save a useful fact to the configured persistent memory store.",
    "recall": "Find previously saved facts matching query keywords in persistent memory.",
    "ask_user": "Ask the user a clarification question through the configured user interface.",
}


class CardinalTools:
    def __init__(self, lm: LMCallable, config: AgentConfig):
        self.config = config
        self.aux_lm = config.aux_lm if config.aux_lm is not None else lm
        self._emails: list[Email] | None = None
        self._by_id: dict[str, Email] = {}
        self._email_index = None
        self._doc_index = None

    def spec(self, name: str) -> ToolSpec:
        return cardinal_spec(name, DESCRIPTIONS[name], getattr(self, name))

    def _load_emails(self) -> list[Email]:
        if self._emails is None:
            emails = data.load_emails()
            self._by_id = {email["id"]: email for email in emails}
            self._emails = emails
        return self._emails

    def search_emails(self, query: str, k: int = 5) -> list[Email]:
        emails = self._load_emails()
        if self._email_index is None:
            self._email_index = adapters.run_bm25_build([data.email_text(e) for e in emails])
        matches = adapters.run_bm25_search(self._email_index, query, k)
        return [deepcopy(emails[doc_id]) for doc_id, _ in matches]

    def read_email(self, email_id: str) -> Email:
        self._load_emails()
        if email_id not in self._by_id:
            raise LookupError(f"Unknown email ID: {email_id}")
        return deepcopy(self._by_id[email_id])

    def email_qa(self, question: str) -> dict:
        return adapters.run_email_qa(question, self.search_emails, self.aux_lm)

    def daily_digest(self, date: str) -> str:
        emails = [deepcopy(e) for e in self._load_emails() if e["date"][:10] == date]
        return adapters.run_daily_digest(emails, self.aux_lm)

    def _load_docs(self):
        if self._doc_index is None:
            self._doc_index = adapters.run_build_doc_index(data.load_docs())
        return self._doc_index

    def search_docs(self, query: str, k: int = 5):
        return adapters.run_search_docs(self._load_docs(), query, k)

    def read_doc(self, doc_id: str, start_line: int = 1):
        return adapters.run_read_doc(self._load_docs(), doc_id, start_line)

    def run_terminal(self, cmd: str) -> str:
        # Importing and preparing the terminal workspace is also deferred.
        from cs329z_hw1 import sandbox

        result = sandbox.run_terminal(
            cmd, workspace=self.config.workspace, timeout=self.config.terminal_timeout
        )
        content = json.dumps(asdict(result), ensure_ascii=False)
        if result.rejected or result.timed_out or result.exit_code != 0:
            reason = result.reason if result.rejected else (
                "Terminal command timed out" if result.timed_out else "Non-zero exit code"
            )
            raise RuntimeError(f"{reason}\n{content}")
        return content

    def _memory_path(self):
        if self.config.memory_dir is None:
            raise RuntimeError("Persistent memory is not configured; set memory_dir.")
        return self.config.memory_dir / "facts.jsonl"

    def remember(self, fact: str) -> str:
        path = self._memory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"fact": fact}, ensure_ascii=False) + "\n")
        return "Fact saved."

    def recall(self, query: str) -> str:
        path = self._memory_path()
        if not path.exists():
            return "No saved facts."
        terms = set(tokenize(query))
        with path.open(encoding="utf-8") as stream:
            facts = [json.loads(line)["fact"] for line in stream if line.strip()]
        matches = [fact for fact in facts if not terms or terms.intersection(tokenize(fact))]
        return json.dumps(matches, ensure_ascii=False) if matches else "No matching saved facts."

    def ask_user(self, question: str) -> str:
        if self.config.user is None:
            raise RuntimeError("No user interface is configured; set user.")
        return self.config.user.ask(question)


def assemble_tools(
    lm: LMCallable, tools: list[ToolSpec] | None, config: AgentConfig
) -> list[ToolSpec]:
    bindings = CardinalTools(lm, config)
    if tools is None:
        return [bindings.spec(name) for name in CARDINAL_TOOLS]

    selected = list(tools)  # An explicit empty list must remain distinct from None.
    names = {tool.name for tool in selected}
    extras = []
    if config.user is not None:
        extras.append("ask_user")
    if config.memory_dir is not None:
        extras.extend(("remember", "recall"))
    for name in extras:
        if name not in names:
            selected.append(bindings.spec(name))
            names.add(name)
    return selected
