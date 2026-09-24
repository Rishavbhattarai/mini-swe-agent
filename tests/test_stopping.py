from mini_swe_agent.agent.stopping import check_stop
from mini_swe_agent.llm.base import ToolCall


def _base_kwargs(call_history, tool_call=None):
    return dict(
        tool_call=tool_call,
        tool_result_success=False,
        step_count=len(call_history),
        max_steps=40,
        call_history=call_history,
        stop_on_repeated_call=True,
        auto_stop_on_tests_pass=False,
    )


def test_detects_immediate_duplicate_call():
    history = [
        ToolCall(name="open_file", arguments={"path": "a.py"}),
        ToolCall(name="open_file", arguments={"path": "a.py"}),
        ToolCall(name="open_file", arguments={"path": "a.py"}),
    ]
    stop = check_stop(**_base_kwargs(history))
    assert stop.stopped
    assert stop.reason == "repeated_call"


def test_detects_period_two_cycle():
    history = [
        ToolCall(name="find_file", arguments={"pattern": "*.py"}),
        ToolCall(name="open_file", arguments={"path": "compound.py"}),
        ToolCall(name="find_file", arguments={"pattern": "*.py"}),
        ToolCall(name="open_file", arguments={"path": "compound.py"}),
        ToolCall(name="find_file", arguments={"pattern": "*.py"}),
        ToolCall(name="open_file", arguments={"path": "compound.py"}),
    ]
    stop = check_stop(**_base_kwargs(history))
    assert stop.stopped
    assert stop.reason == "repeated_call"


def test_no_false_positive_on_varied_calls():
    history = [
        ToolCall(name="find_file", arguments={"pattern": "*.py"}),
        ToolCall(name="open_file", arguments={"path": "a.py"}),
        ToolCall(name="search", arguments={"query": "foo"}),
        ToolCall(name="open_file", arguments={"path": "b.py"}),
    ]
    stop = check_stop(**_base_kwargs(history))
    assert not stop.stopped
