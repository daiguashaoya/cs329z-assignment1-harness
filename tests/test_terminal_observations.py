"""Ensure bounded previews remain auditable and omitted lines are recoverable."""

import re

from cs329z_hw1.agent.observations import terminal_observation
from cs329z_hw1.sandbox import TerminalResult
from cs329z_hw1.tokens import count_message_tokens, count_tokens
from tests.test_terminal import make_session, run, send, terminal_results


def test_saved_capture_preserves_empty_lines_unicode_and_stderr(tmp_path):
    stdout = "first\n\n" + "中间行\n" * 5000 + "last\n"
    stderr = "error-head\n" + "details\n" * 5000 + "error-tail\n"
    content = terminal_observation(
        TerminalResult(stdout=stdout, stderr=stderr, exit_code=3), tmp_path, 1000
    )
    assert count_tokens(content) <= 1000
    assert all(word in content for word in ("first", "last", "error-head", "error-tail", "omitted"))
    saved = list((tmp_path / ".observations").iterdir())
    assert len(saved) == 1
    assert (saved[0] / "stdout.txt").read_bytes().decode("utf-8") == stdout
    assert (saved[0] / "stderr.txt").read_bytes().decode("utf-8") == stderr


def test_small_output_needs_no_saved_files(tmp_path):
    content = terminal_observation(TerminalResult(stdout="ok\n", exit_code=0), tmp_path, 1000)
    assert "ok\n" in content
    assert not (tmp_path / ".observations").exists()


def test_middle_line_read_back_through_sandbox(scripted, tmp_path):
    lm = scripted([run('python3 -c "for i in range(12000): print(i)"'), "Printed."])
    session = make_session(lm, tmp_path, context_budget=6000)
    send(session, "Print the numbered lines.")
    content = terminal_results(session)[0]["content"]
    path = re.search(r"Captured output saved: (\S+)/stdout.txt", content).group(1)
    # A separate scripted session reads the saved capture from the same workspace.
    reader = scripted([run(f"sed -n '6201p' {path}/stdout.txt"), "Read."])
    other = make_session(reader, tmp_path)
    send(other, "Read the middle line.")
    assert "stdout:\n6200\n" in terminal_results(other)[0]["content"]
    assert content in lm.calls[1][-1]["content"]


def test_repeated_output_does_not_rewrite_transcript(scripted, tmp_path):
    command = 'python3 -c "print(\'x\' * 100000)"'
    lm = scripted([run(command)] * 10 + ["Done."])
    session = make_session(lm, tmp_path, context_budget=6000)
    send(session, "Run the commands.")
    assert all(count_message_tokens(call) <= 6000 for call in lm.calls)
    for number, result in enumerate(terminal_results(session)):
        assert result["content"] in lm.calls[number + 1][-1]["content"]
        assert "Captured output saved:" in result["content"]
