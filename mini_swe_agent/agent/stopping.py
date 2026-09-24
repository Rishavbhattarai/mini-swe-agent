"""Stop conditions for the agent loop, checked each iteration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from mini_swe_agent.llm.base import ToolCall


@dataclass
class StopCheck:
    stopped: bool
    reason: Optional[str] = None


def check_stop(
    tool_call: Optional[ToolCall],
    tool_result_success: Optional[bool],
    step_count: int,
    max_steps: int,
    last_two_calls: list[ToolCall],
    stop_on_repeated_call: bool,
    auto_stop_on_tests_pass: bool,
) -> StopCheck:
    if tool_call is not None and tool_call.name == "submit_patch" and tool_result_success:
        return StopCheck(stopped=True, reason="submitted")

    if step_count >= max_steps:
        return StopCheck(stopped=True, reason="max_steps")

    if (
        stop_on_repeated_call
        and len(last_two_calls) == 2
        and last_two_calls[0].name == last_two_calls[1].name
        and last_two_calls[0].arguments == last_two_calls[1].arguments
    ):
        return StopCheck(stopped=True, reason="repeated_call")

    if (
        auto_stop_on_tests_pass
        and tool_call is not None
        and tool_call.name == "run_tests"
        and tool_result_success
    ):
        return StopCheck(stopped=True, reason="tests_pass_auto_stop")

    return StopCheck(stopped=False)
