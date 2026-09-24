import json
import tempfile
from pathlib import Path

from mini_swe_agent.harness.swebench_eval import write_predictions


def test_write_predictions_splits_schema_and_metadata():
    result = {
        "instance_id": "demo-1",
        "model_patch": "diff --git a b",
        "model_name_or_path": "qwen2.5-coder:7b",
        "stop_reason": "submitted",
        "total_steps": 12,
        "wall_clock_s": 3.5,
    }
    with tempfile.TemporaryDirectory() as tmp:
        write_predictions([result], tmp)

        predictions = json.loads((Path(tmp) / "predictions.jsonl").read_text())
        assert set(predictions.keys()) == {"instance_id", "model_patch", "model_name_or_path"}

        metadata = json.loads((Path(tmp) / "run_metadata.jsonl").read_text())
        assert metadata["instance_id"] == "demo-1"
        assert metadata["stop_reason"] == "submitted"
        assert metadata["total_steps"] == 12
        assert metadata["wall_clock_s"] == 3.5
