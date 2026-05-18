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
