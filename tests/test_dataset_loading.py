import tempfile
from pathlib import Path

from mini_swe_agent.dataset.swebench_lite import Instance, _read_subset_file


def test_read_subset_file_ignores_blank_lines_and_comments():
    with tempfile.TemporaryDirectory() as tmp:
        subset_path = Path(tmp) / "subset.txt"
        subset_path.write_text("# comment\nastropy__astropy-1\n\ndjango__django-2\n")
        ids = _read_subset_file(str(subset_path))
        assert ids == {"astropy__astropy-1", "django__django-2"}


def test_instance_from_row_parses_json_fields():
    row = {
        "instance_id": "demo-1",
        "repo": "org/repo",
        "base_commit": "abc123",
        "problem_statement": "fix the bug",
        "FAIL_TO_PASS": '["tests/test_a.py::test_x"]',
        "PASS_TO_PASS": '["tests/test_b.py::test_y"]',
        "patch": "diff --git a b",
    }
    instance = Instance.from_row(row)
    assert instance.instance_id == "demo-1"
    assert instance.fail_to_pass == ["tests/test_a.py::test_x"]
    assert instance.pass_to_pass == ["tests/test_b.py::test_y"]
