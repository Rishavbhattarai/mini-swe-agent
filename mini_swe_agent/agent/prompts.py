"""System prompt design, mirroring SWE-agent's structure: role framing, an
explicit tool contract, and a workflow nudge toward the ACI's intended usage
pattern (locate -> open windowed -> search -> edit -> run_tests -> submit)."""
from __future__ import annotations

from mini_swe_agent.llm.structured_fallback import FALLBACK_INSTRUCTIONS
from mini_swe_agent.tools.base import ToolRegistry

SYSTEM_PROMPT_TEMPLATE = """You are an autonomous software engineer. You have access to \
tools to explore and modify a codebase in order to resolve a GitHub issue.

Tools available:
{tool_block}

Rules:
- Respond with exactly ONE tool call per turn. Do not call multiple tools in one turn.
- Do not explain your reasoning at length; take an action.
- Typical workflow: find_file/search to locate relevant code -> open_file to inspect it \
(use the windowed view's `line`/`scroll` to navigate large files) -> edit to make a change \
-> run_tests to verify -> repeat until tests pass -> submit_patch to finish.
- Only call submit_patch when you believe the issue is resolved.
{fallback_note}
"""


def build_system_prompt(registry: ToolRegistry, tool_call_mode: str) -> str:
    tool_block = registry.get_prompt_block()
    fallback_note = FALLBACK_INSTRUCTIONS if tool_call_mode in ("prompted", "auto") else ""
    return SYSTEM_PROMPT_TEMPLATE.format(tool_block=tool_block, fallback_note=fallback_note)


def build_issue_message(problem_statement: str) -> dict:
    return {
        "role": "user",
        "content": f"GitHub issue to resolve:\n\n{problem_statement}",
    }
