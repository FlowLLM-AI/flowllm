import sys
from typing import List

from dotenv import load_dotenv
from fastmcp import FastMCP

from flowllm.service.flowllm_service import FlowLLMService

load_dotenv()

mcp = FastMCP("ExperienceMaker")
service = ExperienceMakerService(sys.argv[1:])


@mcp.tool
def retriever(query: str,
              messages: List[dict] = None,
              top_k: int = 1,
              workspace_id: str = "default",
              config: dict = None) -> dict:
    """
    Retrieve experiences from the workspace based on a query.

    Args:
        query: Query string
        messages: List of messages
        top_k: Number of top experiences to retrieve
        workspace_id: Workspace identifier
        config: Additional configuration parameters

    Returns:
        Dictionary containing retrieved experiences
    """
    return service(api="retriever", request={
        "query": query,
        "messages": messages if messages else [],
        "top_k": top_k,
        "workspace_id": workspace_id,
        "config": config if config else {},
    }).model_dump()


def main():
    mcp_transport: str = service.init_config.mcp_transport
    if mcp_transport == "sse":
        mcp.run(transport="sse", host=service.http_service_config.host, port=service.http_service_config.port)
    elif mcp_transport == "stdio":
        mcp.run(transport="stdio")
    else:
        raise ValueError(f"Unsupported mcp transport: {mcp_transport}")


if __name__ == "__main__":
    mcp.run(transport="sse", host=service.init_config.host, port=service.http_service_config.port)


