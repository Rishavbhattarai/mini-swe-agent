"""The single seam for ablations: builds a ToolRegistry from config, binding the
same tool names ('open_file', 'search', ...) to different implementations. The
agent loop, prompts, and harness only ever reference tools by name/schema."""
from __future__ import annotations

from mini_swe_agent.config import ToolsConfig
from mini_swe_agent.tools.base import Executor, ToolRegistry
from mini_swe_agent.tools.edit import EditTool
from mini_swe_agent.tools.find_file import FindFileTool
from mini_swe_agent.tools.open_file_full import FullFileOpenTool
from mini_swe_agent.tools.open_file_windowed import WindowedFileOpenTool
from mini_swe_agent.tools.run_tests import RunTestsTool
from mini_swe_agent.tools.search_basic import BasicSearchTool
from mini_swe_agent.tools.search_ripgrep import RipgrepSearchTool
from mini_swe_agent.tools.submit_patch import SubmitPatchTool


def build_registry(
    executor: Executor,
    tools_config: ToolsConfig,
    file_view_window: int = 100,
    default_test_cmd: str | None = None,
) -> ToolRegistry:
    if tools_config.tool_profile == "windowed":
        open_file = WindowedFileOpenTool(executor=executor, window=file_view_window)
    else:
        open_file = FullFileOpenTool(executor=executor)

    if tools_config.search_impl == "ripgrep":
        search = RipgrepSearchTool(executor=executor)
    else:
        search = BasicSearchTool(executor=executor)

    tools = {
        "find_file": FindFileTool(executor=executor),
        "search": search,
        "open_file": open_file,
        "edit": EditTool(executor=executor),
        "run_tests": RunTestsTool(executor=executor, default_test_cmd=default_test_cmd),
        "submit_patch": SubmitPatchTool(executor=executor),
    }
    return ToolRegistry(tools)
