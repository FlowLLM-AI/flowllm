"""Test module for skill_agent_flow functionality.

This module contains a test demonstrating the usage of HttpClient
for executing skill_agent_flow with a PDF filling task.
"""

import asyncio

from flowllm.core.utils import HttpClient


async def main():
    """Test function for skill_agent_flow.

    This function demonstrates how to use HttpClient to execute
    skill_agent_flow with a PDF filling task.
    curl -X POST http://localhost:8002/skill_agent_flow \
      -H "Content-Type: application/json" \
      -d '{
        "query": "xxxx",
        "skill_dir": "../skills"
      }'
    """
    async with HttpClient("http://0.0.0.0:8002") as client:
        query = (
            "Fill Sample-Fillable-PDF.pdf with: name='Alice Johnson', select first choice from dropdown, "
            "check options 1 and 3, dependent name='Bob Johnson', age='12'. Save as filled-sample.pdf"
        )
        # query = "把我做一个简单的述职PPT"
        # query = "帮我创建一个写小说的skills"
        skill_dir = "../skills"
        print("=" * 50)
        print("Testing skill_agent_flow endpoint...")
        response = await client.execute_flow(
            "skill_agent",
            query=query,
            skill_dir=skill_dir,
        )
        print(f"Result: {response.answer}")


if __name__ == "__main__":
    asyncio.run(main())
