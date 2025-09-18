## 快速开始

### 环境准备

#### 1. 克隆项目
```shell
git clone git@gitlab.alibaba-inc.com:OpenRepo/flowllm.git
```

#### 2. 准备环境变量
从 `example.env` 复制一份为 `.env`，填入自己的API密钥和URL：
```shell
cp example.env .env
# 编辑.env文件，填入相关配置
```

#### 3. 安装依赖
要求 Python >= 3.12
```shell
pip install .[fin]
```

### 启动服务

#### SSE模式启动
```shell
flowllm --config=fin_supply
```

#### MCP Server配置（stdio模式）

配置文件示例：
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
