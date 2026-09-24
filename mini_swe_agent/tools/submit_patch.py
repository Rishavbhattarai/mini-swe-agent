"""Finalizes the episode: computes `git diff` against the instance's base_commit
and signals the agent loop to stop. This is the only path that produces a scored
prediction (a forced max_steps stop also captures git diff as a fallback)."""
from __future__ import annotations

from dataclasses import dataclass

from mini_swe_agent.tools.base import Executor, ToolResult


@dataclass
class SubmitPatchTool:
    executor: Executor
    name: str = "submit_patch"
    description: str = (
        "Call this when you believe the issue is resolved and tests pass. "
        "Finalizes your current changes as the submitted patch and ends the episode."
    )

    @property
    def json_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}, "required": []},
        }

    def __call__(self, **_ignored) -> ToolResult:
        stdout, stderr, code = self.executor.run("git diff")
        if code != 0:
            return ToolResult(success=False, output="", error=stderr or "git diff failed")
        return ToolResult(success=True, output=stdout, metadata={"patch": stdout, "submitted": True})
