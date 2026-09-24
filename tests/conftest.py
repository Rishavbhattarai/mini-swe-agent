import subprocess
import tempfile
from pathlib import Path

import pytest

from mini_swe_agent.env.local_repo import LocalRepoExecutor


@pytest.fixture
def scratch_repo():
    """A tiny local git repo (no network/SWE-bench needed) to unit-test tools against."""
    workdir = tempfile.mkdtemp(prefix="mini-swe-test-")
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=workdir, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=workdir, check=True)

    (Path(workdir) / "foo.py").write_text(
        "\n".join(f"line {i}" for i in range(1, 21)) + "\n"
    )
    (Path(workdir) / "bar.txt").write_text("hello world\nneedle here\n")
    subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=workdir, check=True)

    return LocalRepoExecutor(workdir=workdir)
