"""Bound terminal previews while keeping omitted output available on disk."""

from pathlib import Path
from uuid import uuid4

from cs329z_hw1.tokens import CHARS_PER_TOKEN


def preview(text: str, max_chars: int) -> str:
    """Keep both ends, explicitly marking any omitted middle."""
    if len(text) <= max_chars:
        return text
    marker = "\n[... output omitted ...]\n"
    if max_chars < len(marker):
        return marker.strip()[:max(0, max_chars)]
    keep = max_chars - len(marker)
    head = (keep + 1) // 2
    tail = keep // 2
    return text[:head] + marker + (text[-tail:] if tail else "")


def terminal_observation(result, workspace: Path, max_tokens: int) -> str:
    """Render status and bounded streams; save large sandbox captures verbatim."""
    header = (
        f"exit_code: {result.exit_code}\nrejected: {result.rejected}\n"
        f"timed_out: {result.timed_out}\nreason: {result.reason}\n"
    )
    labels = "stdout:\n\nstderr:\n"
    budget = max_tokens * CHARS_PER_TOKEN
    streams = (result.stdout, result.stderr)
    if len(header) + len(labels) + sum(map(len, streams)) > budget:
        relative = Path(".observations") / uuid4().hex
        directory = workspace / relative
        directory.mkdir(parents=True)
        for name, text in zip(("stdout", "stderr"), streams):
            (directory / f"{name}.txt").write_text(text, encoding="utf-8", newline="")
        header += (
            f"Captured output saved: {relative.as_posix()}/stdout.txt and stderr.txt\n"
            "Preview omitted the middle. Read original lines with "
            f"sed -n 'START,ENDp' {relative.as_posix()}/stdout.txt; "
            "use wc -l for line counts. Files contain the sandbox capture, "
            "which may itself have an output cap.\n"
        )
    available = max(0, budget - len(header) - len(labels))
    # Give a short stream its full space, sharing the rest with the long one.
    out_budget = min(len(streams[0]), available // 2)
    err_budget = min(len(streams[1]), available - out_budget)
    out_budget = min(len(streams[0]), available - err_budget)
    return (
        header + "stdout:\n" + preview(streams[0], out_budget)
        + "\nstderr:\n" + preview(streams[1], err_budget)
    )
