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
