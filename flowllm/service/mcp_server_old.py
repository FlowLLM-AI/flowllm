import sys
from typing import List

from fastmcp import FastMCP

from flowllm.service.flowllm_service import FlowLLMService
from flowllm.utils.common_utils import load_env

load_env()

mcp = FastMCP("FlowLLMService")
service = FlowLLMService(sys.argv[1:])


@mcp.tool
def call_fin(query: str,
              messages: List[dict] = None,
             code_infos: dict = None,
             flow_name: str = "default",
              workspace_id: str = "default",
              config: dict = None) -> dict:
    return service(api="retriever", request={
        "query": query,
        "messages": messages if messages else [],
        "code_infos": code_infos if code_infos else {},
        "flow_name": flow_name,
        "workspace_id": workspace_id,
        "config": config if config else {},
    }).model_dump()


def main():
    mcp.run(**service.mcp_config_dict)


if __name__ == "__main__":
    main()
