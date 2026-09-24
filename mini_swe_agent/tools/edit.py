"""Line-range replace edit tool, with a pre-commit syntax guardrail for Python
files (mirrors SWE-agent's edit validation/linting before an edit is accepted)."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from mini_swe_agent.tools.base import Executor, ToolResult

CONTEXT_LINES = 3


def _restore_dropped_indentation(replacement: str, original_first_line: str) -> str:
    """If the model dropped leading whitespace entirely (first replacement
    line has none, but the line it's replacing did), re-apply the original
    line's indentation to every non-blank replacement line.

    Confirmed real failure mode via the ablation study: the model correctly
    identified the fix (adding "unit" to a default list) but submitted the
    replacement with no leading whitespace, tripping the syntax guardrail,
    then retried the identical malformed edit 3 times without adapting
    instead of fixing the indentation itself.
    """
    indent_match = re.match(r"^[ \t]*", original_first_line)
    original_indent = indent_match.group() if indent_match else ""
    if not original_indent:
        return replacement

    repl_lines = replacement.splitlines()
    if not repl_lines or repl_lines[0].startswith((" ", "\t")):
        return replacement  # model already provided some indentation; trust it

    return "\n".join(original_indent + line if line.strip() else line for line in repl_lines)


@dataclass
class EditTool:
    executor: Executor
    name: str = "edit"
    description: str = (
        "Replace lines [start_line, end_line] (1-indexed, inclusive) in a file with new content. "
        "Python edits are syntax-checked before being committed; invalid edits are rejected."
    )

    @property
    def json_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                    "replacement": {"type": "string", "description": "New text for the given line range."},
                },
                "required": ["path", "start_line", "end_line", "replacement"],
            },
        }

    def __call__(self, path: str, start_line: int, end_line: int, replacement: str, **_ignored) -> ToolResult:
        stdout, stderr, code = self.executor.run(f"cat {path}")
        if code != 0:
            return ToolResult(success=False, output="", error=stderr or f"could not read {path}")

        lines = stdout.splitlines()
        if not (1 <= start_line <= end_line <= len(lines) + 1):
            return ToolResult(
                success=False,
                output="",
                error=f"invalid line range [{start_line}, {end_line}] for a {len(lines)}-line file",
            )

        original_slice = "\n".join(lines[start_line - 1 : end_line])
        replacement = _restore_dropped_indentation(replacement, lines[start_line - 1])

        if replacement.strip() == original_slice.strip():
            # Confirmed real failure mode with a small local model: it located
            # the right line, called edit with the SAME content twice, got no
            # signal that nothing had changed, and gave up. Reject no-op edits
            # outright so the model is forced to actually produce a change.
            return ToolResult(
                success=False,
                output="",
                error=(
                    "edit rejected: the replacement text is identical to the current "
                    f"content of lines {start_line}-{end_line}. This made no change to "
                    "the file. If you intend to fix the issue, the replacement must "
                    "actually differ from the original."
                ),
            )

        new_lines = lines[: start_line - 1] + replacement.splitlines() + lines[end_line:]
        new_content = "\n".join(new_lines) + "\n"

        if path.endswith(".py"):
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"edit rejected: resulting file has a syntax error: {e}",
                )

        write_result = self.executor.write_file(path, new_content)
        if not write_result:
            return ToolResult(success=False, output="", error=f"failed to write {path}")

        preview_start = max(1, start_line - CONTEXT_LINES)
        preview_end = min(len(new_lines), start_line - 1 + len(replacement.splitlines()) + CONTEXT_LINES)
        preview = "\n".join(
            f"{i + 1}: {new_lines[i]}" for i in range(preview_start - 1, preview_end)
        )
        return ToolResult(success=True, output=f"Edit applied. Preview:\n{preview}", metadata={"path": path})
