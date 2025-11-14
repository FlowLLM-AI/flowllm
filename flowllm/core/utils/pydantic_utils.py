"""Pydantic helpers for dynamically creating request models.

This module exposes utilities to construct Pydantic models at runtime based on
Flow input schemas. It maps simple schema types to Python types and builds a
`FlowRequest`-derived model with properly typed, optional/required fields and
helpful descriptions.

Exports:
- `create_pydantic_model`: Build a `pydantic.BaseModel` subclass for a flow's
  input schema, using `FlowRequest` as a base.
"""

from typing import Dict, Optional

from pydantic import create_model, Field

from . import snake_to_camel
from ..schema import ToolAttr, FlowRequest

TYPE_MAPPING = {
    "string": str,
    "array": list,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict,
}


def create_pydantic_model(flow_name: str, input_schema: Dict[str, ToolAttr] = None):
    """Create a Pydantic model class for a flow's input schema.

    The returned model subclasses `FlowRequest` and includes one field per
    parameter in ``input_schema``. Parameter types are inferred from a fixed
    mapping of schema type strings to Python types, and optionality is respected
    according to each parameter's ``required`` flag. Field descriptions are
    preserved via ``pydantic.Field``.

    Args:
        flow_name: The name of the flow. Used to derive the generated model
            class name in CamelCase.
        input_schema: A mapping from parameter name to its attributes.
            If ``None`` or empty, only the fields from the `FlowRequest` base are present.

    Returns:
        A dynamically created `pydantic.BaseModel` subclass named
        ``{SnakeToCamel(flow_name)}Model`` that inherits from `FlowRequest` and
        contains fields described by ``input_schema``.

    Raises:
        AssertionError: If a parameter's type is not one of the supported keys
        in ``TYPE_MAPPING``.
    """
    fields = {}

    if input_schema:
        for param_name, param_config in input_schema.items():
            assert (
                param_config.type in TYPE_MAPPING
            ), f"flow_name={flow_name} had invalid type: {param_config.type}! supported={sorted(TYPE_MAPPING.keys())}"
            field_type = TYPE_MAPPING[param_config.type]

            if not param_config.required:
                fields[param_name] = (Optional[field_type], Field(default=None, description=param_config.description))
            else:
                fields[param_name] = (field_type, Field(default=..., description=param_config.description))

    return create_model(f"{snake_to_camel(flow_name)}Model", __base__=FlowRequest, **fields)
