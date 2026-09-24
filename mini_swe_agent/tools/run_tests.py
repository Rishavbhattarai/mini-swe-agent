"""Runs the instance's test command inside the current executor (local clone or
the SWE-bench instance container) and returns a truncated pass/fail summary so
context doesn't blow up on verbose pytest output."""
from __future__ import annotations

from dataclasses import dataclass

from mini_swe_agent.tools.base import Executor, ToolResult

MAX_OUTPUT_CHARS = 4000


@dataclass
class RunTestsTool:
    executor: Executor
    default_test_cmd: str | None = None
    name: str = "run_tests"
    description: str = (
        "Run the test suite (or a specific test command) and report pass/fail. "
        "Use this to check your fix before submitting."
    )

    @property
    def json_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "test_cmd": {
                        "type": "string",
                        "description": "Optional override test command; defaults to the instance's known test invocation.",
                    },
                },
                "required": [],
            },
        }

    def __call__(self, test_cmd: str | None = None, **_ignored) -> ToolResult:
        cmd = test_cmd or self.default_test_cmd
        if not cmd:
            return ToolResult(success=False, output="", error="no test command available for this instance")

        stdout, stderr, code = self.executor.run(cmd)
        combined = (stdout + "\n" + stderr).strip()
        truncated = len(combined) > MAX_OUTPUT_CHARS
        if truncated:
            combined = combined[-MAX_OUTPUT_CHARS:]
            combined = "... [truncated, showing tail]\n" + combined

        return ToolResult(
            success=(code == 0),
            output=combined,
            metadata={"exit_code": code, "truncated": truncated},
        )
