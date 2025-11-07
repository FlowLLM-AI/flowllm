"""Test script for BaseContext.

This script provides test functions for BaseContext class.
It can be run directly with: python test_base_context.py
"""

from flowllm.core.context.base_context import BaseContext


def main():
    """Test function for BaseContext."""
    ctx = BaseContext(**{"name": "Alice", "age": 30, "city": "New York"})

    print(ctx.name)
    print(ctx.age)
    print(ctx.city)

    ctx.email = "alice@example.com"
    ctx["email"] = "alice@example.com"
    print(ctx.email)

    print(ctx.keys())
    print(ctx)


if __name__ == "__main__":
    main()
