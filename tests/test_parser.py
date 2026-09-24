from mini_swe_agent.agent.parser import extract_tool_call
from mini_swe_agent.llm.base import LLMResponse, ToolCall


def test_extract_native_tool_call():
    response = LLMResponse(content="", tool_calls=[ToolCall(name="open_file", arguments={"path": "a.py"})])
    call = extract_tool_call(response, tool_call_mode="native")
    assert call.name == "open_file"


def test_extract_prompted_fallback():
    content = 'I will open the file.\n```tool_call\n{"name": "search", "arguments": {"query": "foo"}}\n```'
    response = LLMResponse(content=content, tool_calls=[])
    call = extract_tool_call(response, tool_call_mode="prompted")
    assert call.name == "search"
    assert call.arguments == {"query": "foo"}


def test_extract_auto_prefers_native_then_falls_back():
    response = LLMResponse(content="no fenced block here", tool_calls=[])
    call = extract_tool_call(response, tool_call_mode="auto")
    assert call is None


def test_extract_prompted_fallback_missing_closing_fence():
    """Confirmed real failure mode: qwen2.5-coder:7b consistently omitted the
    closing ``` fence after the JSON object in a live run, causing 37
    consecutive correct tool calls in a row to silently fail parsing and get
    dropped -- the entire step budget was burned on this parser bug, not a
    model failure. The parser must not require a closing fence."""
    content = '```tool_call\n{"name": "edit", "arguments": {"path": "a.py", "start_line": 1, "end_line": 1, "replacement": "x = 1"}}'
    response = LLMResponse(content=content, tool_calls=[])
    call = extract_tool_call(response, tool_call_mode="prompted")
    assert call is not None
    assert call.name == "edit"
    assert call.arguments["replacement"] == "x = 1"
