import json
from typing import Dict, List

from mcp.types import Tool
from pydantic import BaseModel, Field, model_validator


class ParamAttrs(BaseModel):
    type: str = Field(default="str", description="tool parameter type")
    description: str = Field(default="", description="tool parameter description")
    required: bool = Field(default=True, description="tool parameter required")
    enum: List[str] | None = Field(default=None, description="tool parameter enum")

    def simple_dump(self) -> dict:
        result: dict = {
            "type": self.type,
            "description": self.description,
        }

        if self.enum:
            result["enum"] = self.enum

        return result

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
        tool_type = data.get("type", "")
        tool_type_dict = data.get(tool_type, {})

        for key in ["name", "arguments"]:
            if key not in data:
                data[key] = tool_type_dict.get(key, "")
        return data

    @property
    def argument_dict(self) -> dict:
        return json.loads(self.arguments)

    def simple_input_dump(self, version: str = "v1") -> dict:
        if version == "v1":
            required_list = [name for name, tool_param in self.input_schema.items() if tool_param.required]
            properties = {name: tool_param.simple_dump() for name, tool_param in self.input_schema.items()}

            return {
                "type": self.type,
                self.type: {
                    "name": self.name,
                    "description": self.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required_list
                    },
                },
            }

        else:
            raise NotImplementedError(f"version {version} not supported")

    def simple_output_dump(self, version: str = "v1") -> dict:
        if version == "v1":
            return {
                "index": self.index,
                "id": self.id,
                self.type: {
                    "arguments": self.arguments,
                    "name": self.name
                },
                "type": self.type,
            }
        else:
            raise NotImplementedError(f"version {version} not supported")

    def update_by_output(self, data: dict, version: str = "v1"):
        if version == "v1":
            self.index = data.get("index", 0)
            self.id = data.get("id", "")
            tool_type = data.get("type", "")
            tool_type_dict = data.get(tool_type, {})
            if tool_type_dict:
                name = tool_type_dict.get("name", "")
                arguments = tool_type_dict.get("arguments", "")
                if name:
                    self.name = name
                if arguments:
                    self.arguments = arguments
        else:
            raise NotImplementedError(f"version {version} not supported")

        return self

    @classmethod
    def from_mcp_tool(cls, tool: Tool) -> "ToolCall":
        input_schema = {}
        properties = tool.inputSchema["properties"]
        required = tool.inputSchema["required"]
        for name, attr_dict in properties.items():
            param_attrs = ParamAttrs()

            if name in required:
                param_attrs.required = True
            param_attrs.type = attr_dict.get("type", "str")
            param_attrs.description = attr_dict.get("description", "")
            if "enum" in attr_dict:
                param_attrs.enum = attr_dict["enum"]
            input_schema[name] = param_attrs

        return cls(name=tool.name,
                   description=tool.description,
                   input_schema=input_schema)


if __name__ == "__main__":
    tool_call = ToolCall(**{
        "id": "call_0fb6077ad56f4647b0b04a",
        "function": {
            "arguments": "{\"symbol\": \"ZETA\"}",
            "name": "get_stock_info"
        },
        "type": "function",
        "index": 0
    })
    print(tool_call.simple_output_dump())
