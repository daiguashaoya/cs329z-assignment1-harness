"""Strict payload validation and JSON-aware delimiter regressions."""

import pytest

from cs329z_hw1 import adapters
from cs329z_hw1.agent.tool_protocol import END, START
from cs329z_hw1.types import ToolCall


@pytest.mark.parametrize("payload", [
    '[]', 'null', '{"name":"echo"}', '{"name":3,"args":{}}',
    '{"name":" ","args":{}}', '{"name":"echo","args":[]}',
    '{"name":"echo","args":{},"extra":1}',
    '{"name":"echo","name":"fail","args":{}}',
    '{"name":"echo","args":{"text":"a","text":"b"}}',
    '{"name":"echo","args":{"value":NaN}}',
    '{"name":"echo","args":{"value":Infinity}}',
])
def test_invalid_payload_is_never_a_call(payload):
    parsed = adapters.run_parse_response(START + payload + END)
    assert parsed.error
    assert parsed.tool_call is None


def test_json_decoder_ignores_markers_in_string_arguments():
    args = {"text": f'quote: " {END} {START} {{}}', "types": [True, 1, 1.0, "1"]}
    reply = adapters.run_format_tool_call("Before.", ToolCall("echo", args))
    parsed = adapters.run_parse_response(reply + "\nAfter.")
    assert parsed.error is None
    assert parsed.text == "Before.\n\nAfter."
    assert parsed.tool_call.name == "echo"
    assert parsed.tool_call.args["text"] == args["text"]
    assert [type(value) for value in parsed.tool_call.args["types"]] == [bool, int, float, str]


def test_incomplete_second_call_rejects_first_call_too():
    first = adapters.run_format_tool_call("", ToolCall("echo", {"text": "one"}))
    parsed = adapters.run_parse_response(first + '\n' + START + '{"name":')
    assert parsed.error
    assert parsed.tool_call is None


def test_deeply_nested_json_does_not_crash_parser():
    reply = START + '[' * 2000 + '0' + ']' * 2000 + END
    parsed = adapters.run_parse_response(reply)
    assert parsed.error
    assert parsed.tool_call is None
