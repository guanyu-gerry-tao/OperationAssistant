from dataclasses import dataclass, field
from typing import Any, Literal


ToolPermissionLevel = Literal["read_only"]


@dataclass(frozen=True)
class ToolArgumentSpec:
    """Schema entry for one supported tool argument."""

    name: str
    argument_type: str
    required: bool = True
    description: str = ""


@dataclass(frozen=True)
class ToolDefinition:
    """Function-calling contract exposed by the local tool registry."""

    name: str
    description: str
    permission_level: ToolPermissionLevel
    arguments: list[ToolArgumentSpec] = field(default_factory=list)
    output_contract: str = ""

    def to_function_schema(self) -> dict[str, Any]:
        """Return a JSON Schema compatible function-calling contract."""

        # Standard JSON Schema makes the contract usable beyond this local registry.
        properties = {
            argument.name: {
                "type": argument.argument_type,
                "description": argument.description,
            }
            for argument in self.arguments
        }
        required_arguments = [
            argument.name
            for argument in self.arguments
            if argument.required
        ]
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required_arguments,
                "additionalProperties": False,
            },
            "metadata": {
                "permission_level": self.permission_level,
                "output_contract": self.output_contract,
            },
        }


@dataclass(frozen=True)
class ToolCall:
    """One validated tool invocation selected by the workflow."""

    tool_name: str
    arguments: dict[str, Any]
    reason: str


@dataclass(frozen=True)
class ToolResult:
    """Result returned after executing one read-only sample tool."""

    tool_name: str
    arguments: dict[str, Any]
    permission_level: ToolPermissionLevel
    output: dict[str, Any]
    output_summary: str
