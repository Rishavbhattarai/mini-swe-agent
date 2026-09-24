"""Run configuration: merges defaults < YAML file < env vars < CLI overrides."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel


class LLMConfig(BaseModel):
    model: str = "qwen2.5-coder:7b"
    host: str = "http://localhost:11434"
    tool_call_mode: Literal["native", "prompted", "auto"] = "auto"
    temperature: float = 0.0
    request_timeout_s: int = 600


class AgentConfig(BaseModel):
    max_steps: int = 40
    file_view_window: int = 100
    stop_on_repeated_call: bool = True
    auto_stop_on_tests_pass: bool = False


class ToolsConfig(BaseModel):
    tool_profile: Literal["basic", "windowed"] = "windowed"
    search_impl: Literal["grep", "ripgrep"] = "ripgrep"


class DatasetConfig(BaseModel):
    name: str = "princeton-nlp/SWE-bench_Lite"
    split: str = "test"
    limit: Optional[int] = None
    subset_file: Optional[str] = None


class EvalConfig(BaseModel):
    docker: bool = True
    test_timeout_s: int = 600


class RunConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    agent: AgentConfig = AgentConfig()
    tools: ToolsConfig = ToolsConfig()
    dataset: DatasetConfig = DatasetConfig()
    eval: EvalConfig = EvalConfig()
    results_dir: str = "results"

    @classmethod
    def load(
        cls,
        config_path: Optional[str] = None,
        overrides: Optional[dict] = None,
    ) -> "RunConfig":
        data: dict = {}
        if config_path:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}

        cfg = cls.model_validate(data)

        # Env var overrides (highest precedence below explicit CLI overrides).
        if host := os.environ.get("OLLAMA_HOST"):
            cfg.llm.host = host
        if model := os.environ.get("MINI_SWE_MODEL"):
            cfg.llm.model = model

        # Explicit CLI overrides win last.
        if overrides:
            for dotted_key, value in overrides.items():
                _set_dotted(cfg, dotted_key, value)

        return cfg

    def dump_snapshot(self, path: str | Path) -> None:
        Path(path).write_text(yaml.safe_dump(self.model_dump(), sort_keys=False))


def _set_dotted(obj: BaseModel, dotted_key: str, value) -> None:
    parts = dotted_key.split(".")
    target = obj
    for part in parts[:-1]:
        target = getattr(target, part)
    setattr(target, parts[-1], value)
