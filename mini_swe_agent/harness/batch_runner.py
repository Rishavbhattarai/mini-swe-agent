"""Iterates instances sequentially, writing predictions.jsonl and per-instance
trajectories as it goes; resumable by skipping instance_ids already present in
an existing predictions.jsonl."""
from __future__ import annotations

import json
from pathlib import Path

from mini_swe_agent.config import RunConfig
from mini_swe_agent.dataset.swebench_lite import Instance
from mini_swe_agent.harness.single_instance import run_one_local
from mini_swe_agent.harness.swebench_eval import run_one_docker, write_predictions


def _already_done(results_dir: str) -> set[str]:
    path = Path(results_dir) / "predictions.jsonl"
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        if line.strip():
            done.add(json.loads(line)["instance_id"])
    return done


def run_batch(instances: list[Instance], config: RunConfig, results_dir: str) -> list[dict]:
    Path(results_dir).mkdir(parents=True, exist_ok=True)
    config.dump_snapshot(Path(results_dir) / "config_used.yaml")

    done = _already_done(results_dir)
    predictions: list[dict] = []

    # Preserve any previously completed predictions when resuming.
    existing_path = Path(results_dir) / "predictions.jsonl"
    if existing_path.exists():
        predictions = [json.loads(line) for line in existing_path.read_text().splitlines() if line.strip()]

    run_fn = run_one_docker if config.eval.docker else run_one_local

    for instance in instances:
        if instance.instance_id in done:
            continue
        result = run_fn(instance, config, results_dir)
        predictions.append(result)
        write_predictions(predictions, results_dir)  # write after every instance for resumability

    return predictions
