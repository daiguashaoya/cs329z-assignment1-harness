"""Tool discovery, JSON Schema validation and exception-safe execution."""

from copy import deepcopy
from dataclasses import replace

from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for

from cs329z_hw1.types import ToolResult, ToolSpec


class ToolRegistry:
    def __init__(self, tools: list[ToolSpec]):
        self._tools: dict[str, ToolSpec] = {}
        self._validators = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            # Keep registration metadata independent of caller-owned schemas.
            spec = replace(tool, parameters=deepcopy(tool.parameters))
            validator_class = validator_for(spec.parameters)
            validator_class.check_schema(spec.parameters)
            self._tools[spec.name] = spec
            self._validators[spec.name] = validator_class(spec.parameters)

    def schemas(self) -> list[dict]:
        """Expose model-facing metadata in insertion order, without functions."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": deepcopy(tool.parameters),
            }
            for tool in self._tools.values()
        ]

    def validate(self, name: str, args: dict) -> ToolResult | None:
        """Check a call without running its function or coercing arguments."""
        if not isinstance(name, str) or name not in self._tools:
            return ToolResult("unknown_tool", f"Unknown tool: {name!r}")
        # Tool functions receive keyword arguments, so the outer value must
        # be an object with string keys even if a schema is permissive.
        if not isinstance(args, dict) or any(not isinstance(key, str) for key in args):
            return ToolResult("invalid_args", "Arguments must be an object with string keys.")
        try:
            self._validators[name].validate(args)
        except ValidationError as exc:
            return ToolResult("invalid_args", exc.message)
        except Exception as exc:
            return ToolResult("invalid_args", f"Argument validation failed: {exc}")
        return None

    def execute(self, name: str, args: dict) -> ToolResult:
        """Validate first, then invoke exactly once; contain tool exceptions."""
        error = self.validate(name, args)
        if error is not None:
            return error
        try:
            value = self._tools[name].fn(**args)
            return ToolResult("ok", str(value))
        except Exception as exc:
            return ToolResult("tool_error", str(exc))
