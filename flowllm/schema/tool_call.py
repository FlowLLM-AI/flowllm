import json
from typing import Dict

from pydantic import BaseModel, Field


class ParamAttrs(BaseModel):
    type: str = Field(default="str", description="tool parameter type")
    description: str = Field(default="", description="tool parameter description")
    required: bool = Field(default=True, description="tool parameter required")


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

    arguments: dict = Field(default_factory=dict, description="tool execution arguments")

    description: str = Field(default="")
    input_schema: Dict[str, ParamAttrs] = Field(default_factory=dict)
    output_schema: Dict[str, ParamAttrs] = Field(default_factory=dict)

    def simple_input_dump(self, version: str = "v1") -> dict:
        if version == "v1":
            required_list = [name for name, tool_param in self.input_schema.items() if tool_param.required]
            properties = {name: {
                "type": tool_param.type,
                "description": tool_param.description
            } for name, tool_param in self.input_schema.items()}

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
                    "arguments": json.dumps(self.arguments, ensure_ascii=False),
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
                    self.arguments = json.loads(arguments)
        else:
            raise NotImplementedError(f"version {version} not supported")

        return self
