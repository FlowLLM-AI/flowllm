# Fin Supply Quick Start

## git clone
```shell
git clone git@gitlab.alibaba-inc.com:OpenRepo/flowllm.git
```

## 准备 `.env`
从sample.env复制一份，填入自己的sk和url

## 确认配置
确认[配置](../flowllm/config/fin_supply.yaml)
- **get_a_stock_infos**: fin_supply.yaml注册，标注desc&schema
- **get_a_stock_news**: fin_supply.yaml注册，标注desc&schema
- **ant_search**: 远程mcp注册，desc&schema从远程拉取
- **ant_investment**: 远程mcp注册，desc&schema从远程拉取
- **tavily_search_tool_flow**: 代码注册
- **dashscope_search_tool_flow**: 代码注册

## 安装flowllm

要求py>=3.12
```shell
pip install -e .
```

## 启动flowllm
```shell
flowllm --config=fin_supply
```
1. 看到logo了就证明成功了
2. 看到下面的打印就证明开启了多少mcp服务
```
2025-09-08 14:19:12 | INFO | integrate endpoint=ant_investment
2025-09-08 14:19:12 | INFO | integrate endpoint=ant_search
2025-09-08 14:19:12 | INFO | integrate endpoint=dashscope_search_tool_flow
2025-09-08 14:19:12 | INFO | integrate endpoint=get_a_stock_infos
2025-09-08 14:19:12 | INFO | integrate endpoint=get_a_stock_news
2025-09-08 14:19:12 | INFO | integrate endpoint=tavily_search_tool_flow
```

## mcp server config json

```json
{
  "mcpServers": {
    "asio-fin-supply-server": {
      "command": "flowllm",
      "args": [
        "--config=fin_supply",
        "--mcp.transport=stdio"
      ],
      "env": {
        "FLOW_EMBEDDING_API_KEY": "sk-xxxx",
        "FLOW_EMBEDDING_BASE_URL": "xxxx"
      }
    }
  }
}
```

## 使用mcp服务
标准的mcp服务使用方法
Demo [mcp_client_test.py](../test/mcp_client_test.py)

