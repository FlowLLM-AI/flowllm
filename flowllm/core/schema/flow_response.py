"""Flow response schema for API responses."""

from pydantic import Field, BaseModel


class FlowResponse(BaseModel):
    """Represents a complete flow execution response with answer and messages."""

    answer: str | dict | list = Field(default="")
    success: bool = Field(default=True)
    metadata: dict = Field(default_factory=dict)
