"""Additional schema-isolation and nested-validation regressions."""

import pytest

from cs329z_hw1 import adapters
from cs329z_hw1.types import ToolSpec
from tests.fixture_tools import make_fixture_tools


def test_exported_and_original_schemas_cannot_change_validation():
    fx = make_fixture_tools()
    registry = adapters.run_tool_registry(fx.tools)
    exported = registry.schemas()
    exported[0]["parameters"]["properties"]["text"]["type"] = "integer"
    fx.spec("echo").parameters["required"].clear()
    assert registry.validate("echo", {"text": "hello"}) is None
    assert registry.validate("echo", {"text": 42}).status == "invalid_args"
    assert registry.validate("echo", {}).status == "invalid_args"
    assert registry.schemas()[0]["parameters"]["properties"]["text"]["type"] == "string"
    assert fx.calls == []


@pytest.mark.parametrize("args", [None, [], "text", {1: "value"}])
def test_non_keyword_arguments_are_rejected_before_execution(args):
    fx = make_fixture_tools()
    registry = adapters.run_tool_registry(fx.tools)
    assert registry.validate("echo", args).status == "invalid_args"
    assert registry.execute("echo", args).status == "invalid_args"
    assert fx.calls == []


def test_nested_schema_and_local_references():
    calls = []
    schema = {
        "type": "object",
        "$defs": {"positive_integer": {"type": "integer", "minimum": 1}},
        "properties": {
            "items": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/positive_integer"},
            },
        },
        "required": ["items"],
        "additionalProperties": False,
    }

    def record(items):
        calls.append(items)
        return sum(items)

    registry = adapters.run_tool_registry([ToolSpec("sum", "Sum integers", schema, record)])
    for items in ([], [0], [True], ["1"]):
        assert registry.execute("sum", {"items": items}).status == "invalid_args"
    assert calls == []
    result = registry.execute("sum", {"items": [1, 2]})
    assert (result.status, result.content) == ("ok", "3")
    assert calls == [[1, 2]]


def test_return_value_conversion_error_is_contained():
    class BrokenString:
        def __str__(self):
            raise ValueError("Cannot render result")

    spec = ToolSpec("broken", "Bad return value", {"type": "object"}, BrokenString)
    registry = adapters.run_tool_registry([spec])
    result = registry.execute("broken", {})
    assert result.status == "tool_error"
    assert "Cannot render result" in result.content
