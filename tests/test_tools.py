from mini_swe_agent.tools.edit import EditTool
from mini_swe_agent.tools.find_file import FindFileTool
from mini_swe_agent.tools.open_file_full import FullFileOpenTool
from mini_swe_agent.tools.open_file_windowed import WindowedFileOpenTool
from mini_swe_agent.tools.search_basic import BasicSearchTool
from mini_swe_agent.tools.search_ripgrep import RipgrepSearchTool
from mini_swe_agent.tools.submit_patch import SubmitPatchTool


class _NoRipgrepExecutor:
    """Wraps a real executor but pretends `rg` isn't installed, to exercise
    RipgrepSearchTool's grep fallback (confirmed needed: SWE-bench's official
    conda-based instance images don't ship ripgrep)."""

    def __init__(self, inner):
        self._inner = inner

    def run(self, cmd, cwd=None):
        if cmd.strip() == "command -v rg":
            return "", "", 1
        return self._inner.run(cmd, cwd)

    def write_file(self, path, content):
        return self._inner.write_file(path, content)


def test_find_file(scratch_repo):
    result = FindFileTool(executor=scratch_repo)(pattern="*.py")
    assert result.success
    assert "foo.py" in result.output


def test_basic_search(scratch_repo):
    result = BasicSearchTool(executor=scratch_repo)(query="needle")
    assert result.success
    assert "bar.txt" in result.output


def test_open_file_full(scratch_repo):
    result = FullFileOpenTool(executor=scratch_repo)(path="foo.py")
    assert result.success
    assert "line 1" in result.output


def test_open_file_windowed_scroll(scratch_repo):
    tool = WindowedFileOpenTool(executor=scratch_repo, window=5)
    first = tool(path="foo.py", line=1)
    assert first.success
    second = tool(path="foo.py", scroll="down")
    assert second.success
    assert first.output != second.output


def test_edit_rejects_syntax_error(scratch_repo):
    scratch_repo.write_file("broken.py", "def f():\n    return 1\n")
    result = EditTool(executor=scratch_repo)(
        path="broken.py", start_line=1, end_line=2, replacement="def f(:\n    return 1"
    )
    assert not result.success
    assert "syntax error" in result.error


def test_edit_rejects_noop_edit(scratch_repo):
    scratch_repo.write_file("same.py", "def f():\n    return 1\n")
    result = EditTool(executor=scratch_repo)(
        path="same.py", start_line=2, end_line=2, replacement="    return 1"
    )
    assert not result.success
    assert "identical" in result.error


def test_edit_restores_dropped_indentation(scratch_repo):
    """Reproduces the real ablation-study failure: model provides a correct
    fix but strips leading whitespace, which would otherwise be rejected by
    the syntax guardrail. edit() should re-apply the original indentation."""
    scratch_repo.write_file(
        "indented.py",
        "class C:\n"
        "    def f(self):\n"
        '        header_rows = getattr(self, "header_rows", ["name"])\n'
        "        return header_rows\n",
    )
    result = EditTool(executor=scratch_repo)(
        path="indented.py",
        start_line=3,
        end_line=3,
        replacement='header_rows = getattr(self, "header_rows", ["name", "unit"])',
    )
    assert result.success, result.error
    reread = FullFileOpenTool(executor=scratch_repo)(path="indented.py")
    assert '        header_rows = getattr(self, "header_rows", ["name", "unit"])' in reread.output


def test_edit_applies_valid_change(scratch_repo):
    scratch_repo.write_file("ok.py", "def f():\n    return 1\n")
    result = EditTool(executor=scratch_repo)(
        path="ok.py", start_line=2, end_line=2, replacement="    return 2"
    )
    assert result.success
    reread = FullFileOpenTool(executor=scratch_repo)(path="ok.py")
    assert "return 2" in reread.output


def test_ripgrep_search_falls_back_to_grep_when_rg_missing(scratch_repo):
    tool = RipgrepSearchTool(executor=_NoRipgrepExecutor(scratch_repo))
    result = tool(query="needle")
    assert result.success
    assert "bar.txt" in result.output


def test_submit_patch_returns_diff(scratch_repo):
    scratch_repo.write_file("foo.py", "line 1 changed\n")
    result = SubmitPatchTool(executor=scratch_repo)()
    assert result.success
    assert "foo.py" in result.output
