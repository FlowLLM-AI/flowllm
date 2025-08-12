from abc import ABC

from loguru import logger
from pydantic import BaseModel, Field


class sfasdfasdfTool(BaseModel):
    tool_id: str = Field(default="")
    name: str = Field(..., description="tool name")
    description: str = Field(..., description="tool description")
    tool_type: str = Field(default="function")
    parameters: dict = Field(default_factory=dict, description="tool parameters")


    def simple_dump(self) -> dict:
        """
        It may be in other different tool params formats; different versions are completed here.
        """
        return {
            "type": self.tool_type,
            self.tool_type: {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @property
    def input_schema(self) -> dict:
        return self.parameters.get("properties", {})

    @property
    def output_schema(self) -> dict:
        raise NotImplementedError

    def refresh(self):
        # for mcp
        raise NotImplementedError

    def get_cache_id(self, **kwargs) -> str:
        raise NotImplementedError
