"""The agent's observe -> LLM -> tool call -> observe loop. Never imports a
concrete tool implementation directly -- only talks to a ToolRegistry, which is
what makes ablations (`--tools basic|windowed`, `--search grep|ripgrep`) swap
cleanly without touching this file."""
from __future__ import annotations

import time
from dataclasses import asdict

from mini_swe_agent.agent.prompts import build_issue_message, build_system_prompt
from mini_swe_agent.agent.parser import extract_tool_call
from mini_swe_agent.agent.stopping import check_stop
from mini_swe_agent.agent.trajectory import Step, Trajectory
from mini_swe_agent.config import AgentConfig, LLMConfig
from mini_swe_agent.llm.base import LLMClient, ToolCall
from mini_swe_agent.tools.base import ToolRegistry


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        agent_config: AgentConfig,
        llm_config: LLMConfig,
    ):
        self.llm = llm
        self.registry = registry
        self.agent_config = agent_config
        self.llm_config = llm_config

    def run(self, instance_id: str, problem_statement: str, log_path: str | None = None) -> Trajectory:
        trajectory = Trajectory(instance_id=instance_id)
        if log_path:
            trajectory.attach_log(log_path)

        system_prompt = build_system_prompt(self.registry, self.llm_config.tool_call_mode)
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            build_issue_message(problem_statement),
        ]

        last_two_calls: list[ToolCall] = []
        start = time.time()
        stop_reason = "max_steps"
        final_patch = None

        for step_num in range(1, self.agent_config.max_steps + 1):
            response = self.llm.chat(messages, tools=self.registry.get_openai_style_schema())
            tool_call = extract_tool_call(response, self.llm_config.tool_call_mode)

            messages.append({"role": "assistant", "content": response.content})
            trajectory.add_step(Step(role="assistant", content=response.content, tool_call=asdict(tool_call) if tool_call else None))

            if tool_call is None:
                messages.append(
                    {"role": "user", "content": "No valid tool call found in your response. Please respond with exactly one tool call."}
                )
                continue

            result = self.registry.call(tool_call.name, **tool_call.arguments)
            trajectory.add_step(Step(role="tool", content=result.output, tool_result=asdict(result)))
            messages.append({"role": "tool", "content": result.output if result.success else f"ERROR: {result.error}"})

            if tool_call.name == "submit_patch" and result.success:
                final_patch = result.metadata.get("patch")

            last_two_calls = (last_two_calls + [tool_call])[-2:]
            stop = check_stop(
                tool_call=tool_call,
                tool_result_success=result.success,
                step_count=step_num,
                max_steps=self.agent_config.max_steps,
                last_two_calls=last_two_calls,
                stop_on_repeated_call=self.agent_config.stop_on_repeated_call,
                auto_stop_on_tests_pass=self.agent_config.auto_stop_on_tests_pass,
            )
            if stop.stopped:
                stop_reason = stop.reason or "unknown"
                break

        if final_patch is None:
            fallback = self.registry.call("submit_patch")
            if fallback.success:
                final_patch = fallback.metadata.get("patch")

        trajectory.finish(stop_reason=stop_reason, final_patch=final_patch, wall_clock_s=time.time() - start)
        return trajectory
