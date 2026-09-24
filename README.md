# mini-swe-agent

A small SWE-agent-style coding agent, evaluated on SWE-bench Lite, built to
demonstrate the core SWE-agent insight: the **agent-computer interface (ACI)**
— the tools an LLM is given (file viewer, search, edit commands) — matters as
much as the model itself. The agent reads a GitHub issue, explores a repo,
edits code, runs tests, and submits a patch; different tool designs (windowed
file viewer vs. full-file dump, ripgrep vs. basic grep) can be swapped via
config and compared in an ablation study that reports fix-rate deltas.

Runs entirely on a **local Ollama model** (default `qwen2.5-coder:7b`) — no
API keys required.

## Prerequisites

1. **Ollama**, running locally, with the model pulled:
   ```
   ollama serve
   ollama pull qwen2.5-coder:7b
   # optional, if you have 20GB+ RAM/VRAM to spare (thrashes/times out on a
   # 16GB machine -- confirmed on an M4 MacBook with 16GB RAM):
   ollama pull qwen2.5-coder:32b
   ```
2. **Docker Desktop**, running. Required for the official SWE-bench Lite
   evaluation harness (`swebench` builds a per-instance repo image and runs
   tests inside it — this is what produces real, comparable fix-rate
   numbers). Docker is **not currently installed** on this machine as of
   scaffold time — install it before running any `--docker true` command.
3. Python >= 3.10.

## Setup

```bash
pip install -e ".[dev]"
```

## Quickstart: agent-loop smoke test (no Docker)

Fastest way to check the agent loop itself is working, without touching
Docker or official scoring:

```bash
mini-swe run-one --instance-id <some_instance_id> --config configs/default.yaml --docker false
```

This clones the instance's repo locally, runs the agent, and prints the
resulting patch. **Not scored** — use this only to debug agent behavior.

## Official 5-instance dry run (Docker, real scoring)

1. Populate `configs/subsets/dev5.txt` with 5 real instance_ids:
   ```bash
   python -c "from mini_swe_agent.dataset.swebench_lite import load_instances; [print(i.instance_id) for i in load_instances(limit=5)]"
   ```
2. Run + score:
   ```bash
   mini-swe run-batch --subset configs/subsets/dev5.txt --config configs/default.yaml --results-dir results/dev5
   mini-swe evaluate --run-dir results/dev5
   python scripts/report.py results/dev5
   ```

## Full SWE-bench Lite run (300 instances)

```bash
mini-swe run-batch --limit 300 --config configs/default.yaml --results-dir results/full_lite
mini-swe evaluate --run-dir results/full_lite
python scripts/report.py results/full_lite
```

This builds a Docker image per repo (cached after first use) and runs 300
local-LLM episodes — expect a long wall-clock run (likely hours). `run-batch`
is resumable: re-running the same command skips instances already present in
`results/full_lite/predictions.jsonl`.

## Ablation study: does the ACI matter?

Compares the "basic" ACI (full-file dumps, plain grep) against the
"windowed" ACI (SWE-agent-style scrollable file viewer, ripgrep) on the same
instances, everything else held constant:

```bash
mini-swe ablate --configs configs/ablation_basic_tools.yaml configs/ablation_windowed_tools.yaml --limit 10
python scripts/report.py results/ablation_basic_tools results/ablation_windowed_tools
```

Produces a Markdown comparison table (fix rate, resolved count, delta vs.
baseline, avg steps, avg wall clock) — the flagship result for writing this
project up.

## Swapping models

Edit `configs/default.yaml`'s `llm.model`, or override without touching the
file:

```bash
export MINI_SWE_MODEL=qwen2.5-coder:7b
mini-swe run-one --instance-id <id> --config configs/default.yaml --docker false
```

## Project layout

See `mini_swe_agent/` for the package (tools, agent loop, dataset loading,
harness/eval integration, ablation runner, CLI) and `tests/` for unit tests
(`pytest`). The key extensibility seam is `mini_swe_agent/tools/registry.py`:
it binds tool names (`open_file`, `search`, ...) to concrete implementations
based on `tools.tool_profile` / `tools.search_impl` in config — the agent
loop and prompts never import a concrete tool directly, which is what makes
ablations swap cleanly.

**Version note**: the `swebench` package's public API (image-build helpers,
`run_evaluation` entrypoint) differs across releases. `mini_swe_agent/env/docker_repo.py`
and `mini_swe_agent/harness/swebench_eval.py` are scaffolded against the
expected shape but should be checked against `pip show swebench`'s installed
version before the first real Docker run.
