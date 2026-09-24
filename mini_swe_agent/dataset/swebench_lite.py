"""Loads SWE-bench Lite instances from Hugging Face, filtered by --limit,
--subset (explicit instance_id allowlist file), or explicit instance_ids."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from datasets import load_dataset


@dataclass
class Instance:
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    fail_to_pass: list[str]
    pass_to_pass: list[str]
    gold_patch: str  # reference only -- never shown to the agent
    raw_row: dict  # full original HF row, needed by swebench's own image-build/test_spec API

    @classmethod
    def from_row(cls, row: dict) -> "Instance":
        import json

        return cls(
            instance_id=row["instance_id"],
            repo=row["repo"],
            base_commit=row["base_commit"],
            problem_statement=row["problem_statement"],
            fail_to_pass=json.loads(row["FAIL_TO_PASS"]) if isinstance(row["FAIL_TO_PASS"], str) else row["FAIL_TO_PASS"],
            pass_to_pass=json.loads(row["PASS_TO_PASS"]) if isinstance(row["PASS_TO_PASS"], str) else row["PASS_TO_PASS"],
            gold_patch=row.get("patch", ""),
            raw_row=dict(row),
        )


def _read_subset_file(path: str) -> set[str]:
    ids = set()
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            ids.add(line)
    return ids


def load_instances(
    name: str = "princeton-nlp/SWE-bench_Lite",
    split: str = "test",
    limit: Optional[int] = None,
    subset_file: Optional[str] = None,
    instance_ids: Optional[list[str]] = None,
) -> list[Instance]:
    ds = load_dataset(name, split=split)
    instances = [Instance.from_row(row) for row in ds]

    if subset_file:
        allowed = _read_subset_file(subset_file)
        instances = [i for i in instances if i.instance_id in allowed]
    if instance_ids:
        allowed = set(instance_ids)
        instances = [i for i in instances if i.instance_id in allowed]
    if limit is not None:
        instances = instances[:limit]

    return instances
