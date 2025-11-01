"""Tool call schema definitions for representing and managing tool calls."""

import json
from typing import Dict, List

from mcp.types import Tool
from pydantic import BaseModel, Field, model_validator, ConfigDict


class ParamAttrs(BaseModel):
    """Attributes for tool parameters."""

    type: str = Field(default="str", description="tool parameter type")
    description: str = Field(default="", description="tool parameter description")
    required: bool = Field(default=True, description="tool parameter required")
    enum: List[str] | None = Field(default=None, description="tool parameter enum")

    model_config = ConfigDict(extra="allow")


class ToolCall(BaseModel):
    """
    input:
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "It is very useful when you want to check the weather of a specified city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Cities or counties, such as Beijing, Hangzhou, Yuhang District, etc.",
                    }
                },
                "required": ["location"]
            }
        }
    }
    output:
    {
        "index": 0
        "id": "call_6596dafa2a6a46f7a217da",
        "function": {
            "arguments": "{\"location\": \"Beijing\"}",
            "name": "get_current_weather"
        },
        "type": "function",
    }
    """

    index: int = Field(default=0)
    id: str = Field(default="")
    type: str = Field(default="function")
    name: str = Field(default="")

    arguments: str = Field(default="", description="tool execution arguments")

    description: str = Field(default="")
    input_schema: Dict[str, ParamAttrs] = Field(default_factory=dict)
    output_schema: Dict[str, ParamAttrs] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def init_tool_call(cls, data: dict):
        """Initialize ToolCall from raw data dictionary, extracting function info."""
        tool_type = data.get("type", "")
        tool_type_dict = data.get(tool_type, {})

        if "name" in tool_type_dict:
            data["name"] = tool_type_dict["name"]

        if "arguments" in tool_type_dict:
            data["arguments"] = tool_type_dict["arguments"]

        if "description" in tool_type_dict:
            data["description"] = tool_type_dict["description"]

        if "parameters" in tool_type_dict:
            tool_params = tool_type_dict["parameters"]
            properties: dict = tool_params.get("properties", {})
            required: list = tool_params.get("required", [])
            data["input_schema"] = {}
            for name, param_attrs in properties.items():
                tool_param = ParamAttrs(**param_attrs)
                tool_param.required = name in required
                data["input_schema"][name] = tool_param

        return data

    @property
    def argument_dict(self) -> dict:
        """Parse and return arguments as a dictionary."""
        return json.loads(self.arguments)

    def check_argument(self) -> bool:
        """Check if arguments can be parsed as valid JSON."""
        try:
            _ = self.argument_dict
            return True
        except Exception:
            return False

    def simple_input_dump(self, version: str = "default") -> dict:
        """Convert ToolCall to input format dictionary for API requests."""
        if version == "default":
            required_list = [name for name, tool_param in self.input_schema.items() if tool_param.required]
            properties = {
                name: tool_param.model_dump(exclude={"required"}, exclude_none=True)
                for name, tool_param in self.input_schema.items()
            }

            return {
                "type": self.type,
                self.type: {
                    "name": self.name,
                    "description": self.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required_list,
                    },
                },
            }

        else:
            raise NotImplementedError(f"version {version} not supported")

    def simple_output_dump(self, version: str = "default") -> dict:
        """Convert ToolCall to output format dictionary for API responses."""
        if version == "default":
            return {
                "index": self.index,
                "id": self.id,
                self.type: {
                    "arguments": self.arguments,
                    "name": self.name,
                },
                "type": self.type,
            }
        else:
            raise NotImplementedError(f"version {version} not supported")

    @classmethod
    def from_mcp_tool(cls, tool: Tool) -> "ToolCall":
        """Create a ToolCall instance from an MCP Tool object."""
        input_schema = {}
        properties = tool.inputSchema["properties"]
        required = tool.inputSchema.get("required", [])
        for name, attr_dict in properties.items():
            param_attrs = ParamAttrs()

            if name in required:
                param_attrs.required = True
            param_attrs.type = attr_dict.get("type", "str")
            param_attrs.description = attr_dict.get("description", "")
            if "enum" in attr_dict:
                param_attrs.enum = attr_dict["enum"]
            input_schema[name] = param_attrs

        return cls(
            name=tool.name,
            description=tool.description,
            input_schema=input_schema,
        )

    def _build_mcp_schema(self, schema_dict: Dict[str, ParamAttrs]) -> dict:
        """Build an MCP schema dictionary from a ParamAttrs schema dictionary."""
        properties = {}
        required = []

        for name, param_attrs in schema_dict.items():
            param_dict = {
                "type": param_attrs.type,
                "description": param_attrs.description,
            }

            # Add enum if present
            if param_attrs.enum is not None:
                param_dict["enum"] = param_attrs.enum

            # Copy any extra fields from param_attrs
            excluded_keys = {"type", "description", "required", "enum"}
            for key, value in param_attrs.model_dump().items():
                if key not in excluded_keys:
                    param_dict[key] = value

            properties[name] = param_dict

            # Track required parameters
            if param_attrs.required:
                required.append(name)

        mcp_schema = {
            "type": "object",
            "properties": properties,
        }

        if required:
            mcp_schema["required"] = required

        return mcp_schema

    def to_mcp_tool(self) -> Tool:
        """Convert this ToolCall to an MCP Tool object."""
        input_schema = self._build_mcp_schema(self.input_schema)

        # Build outputSchema from output_schema if present
        output_schema = None
        if self.output_schema:
            output_schema = self._build_mcp_schema(self.output_schema)

        return Tool(
            name=self.name,
            description=self.description or None,
            inputSchema=input_schema,
            outputSchema=output_schema,
        )


def main():
    """Test function to demonstrate ToolCall serialization and deserialization."""
    data = {
        "id": "call_0fb6077ad56f4647b0b04a",
        "function": {
            "arguments": '{"symbol": "ZETA"}',
            "name": "get_stock_info",
        },
        "type": "function",
        "index": 0,
    }
    tool_call = ToolCall(**data)
    output_data = tool_call.simple_output_dump()
    assert output_data == data
    print(json.dumps(output_data, ensure_ascii=False))

    data = {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "It is very useful when you want to check the weather of a specified city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Cities or counties, such as Beijing, Hangzhou, Yuhang District, etc.",
                    },
                },
                "required": ["location"],
            },
        },
    }
    tool_call = ToolCall(**data)
    input_data = tool_call.simple_input_dump()
    assert input_data == data
    print(json.dumps(input_data, ensure_ascii=False))


if __name__ == "__main__":
    main()
