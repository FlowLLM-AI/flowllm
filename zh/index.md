<p align="center">
  <img src="../figure/logo.png" alt="FlowLLM Logo" width="50%">
</p>

<p align="center">
  <strong>FlowLLM：让基于LLM的HTTP/MCP服务开发更简单</strong><br>
  <em><sub>如果觉得有用，欢迎给个 ⭐ Star，您的支持是我们持续改进的动力</sub></em>
</p>

<p align="center">
  <a href="https://pypi.org/project/flowllm/"><img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python Version"></a>
  <a href="https://pypi.org/project/flowllm/"><img src="https://img.shields.io/badge/pypi-0.2.0.0-blue?logo=pypi" alt="PyPI Version"></a>
  <a href="https://github.com/flowllm-ai/flowllm/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-black" alt="License"></a>
  <a href="https://github.com/flowllm-ai/flowllm"><img src="https://img.shields.io/github/stars/flowllm-ai/flowllm?style=social" alt="GitHub Stars"></a>
</p>

---

## 📖 简介

FlowLLM 将 LLM/Embedding/vector_store 能力封装为 HTTP/MCP 服务，适用于 AI 对话助手、RAG 应用、工作流服务等场景，并可集成到支持
MCP 的客户端工具中。

### 🏗️ 架构概览

<p align="center">
  <img src="../figure/framework.png" alt="FlowLLM Framework" width="100%">
</p>


### ⭐ 核心特性
- **简单易用的 Op 开发**：继承 BaseOp 或 BaseAsyncOp 基类，实现业务逻辑即可。FlowLLM提供了延迟初始化的 LLM、Embedding 模型和向量库，开发者只需通过 `self.llm`、`self.embedding_model`、`self.vector_store` 即可轻松使用这些资源。同时FlowLLM提供了完整的 Prompt 模板管理能力，通过 `prompt_format()` 和 `get_prompt()` 方法进行格式化和使用。

- **灵活的 Flow 编排**：通过 YAML 配置文件将 Op 组合成 Flow，支持灵活的编排方式。`>>` 表示串行组合，`|` 表示并行组合，例如 `SearchOp() >> (AnalyzeOp() | TranslateOp()) >> FormatOp()` 可构建复杂的工作流。定义输入输出 Schema 后，使用 `flowllm config=your_config` 命令即可启动服务。

- **自动生成服务**：配置完成后，FlowLLM 会自动生成 HTTP、MCP 和 CMD 服务。HTTP 服务提供标准的 RESTful API，支持同步 JSON 响应和 HTTP Stream 流式响应。MCP 服务会自动注册为 Model Context Protocol 工具，可集成到支持 MCP 的客户端中。CMD 服务支持命令行模式执行单个 Op，适合快速测试和调试。


### 🌟 基于FlowLLM的应用

| 项目名 | 描述 |
|--------|------|
| [ReMe](https://github.com/agentscope-ai/ReMe) | 面向智能体的记忆管理工具包 |

---

## ⚡ 快速开始

### 📦 Step0 安装

#### 📥 From PyPI

```bash
pip install flowllm
```

#### 🔧 From Source

```bash
git clone https://github.com/flowllm-ai/flowllm.git
cd flowllm
pip install -e .
```

详细安装与配置方法请参考 [安装指南](guide/installation.md)。

### ⚙️ 配置

创建 `.env` 文件，配置 API Key。你可以从 `example.env` 复制并修改：

```bash
cp example.env .env
```

然后在 `.env` 文件中配置你的 API Key：

```bash
FLOW_LLM_API_KEY=sk-xxxx
FLOW_LLM_BASE_URL=https://xxxx/v1
FLOW_EMBEDDING_API_KEY=sk-xxxx
FLOW_EMBEDDING_BASE_URL=https://xxxx/v1
```

详细配置说明请参考 [配置指南](guide/config_guide.md)。

### 🛠️ Step1 构建Op

```python
from flowllm.core.context import C
from flowllm.core.op.base_async_op import BaseAsyncOp
from flowllm.core.schema import Message
from flowllm.core.enumeration import Role

@C.register_op()
class SimpleChatOp(BaseAsyncOp):
    async def async_execute(self):
        query = self.context.get("query", "")
        messages = [Message(role=Role.USER, content=query)]
        response = await self.llm.achat(messages=messages)
        self.context.response.answer = response.content.strip()
```

详细内容请参考 [简单 Op 指南](guide/async_op_minimal_guide.md)、[LLM Op 指南](guide/async_op_llm_guide.md) 和 [高级 Op 指南](guide/async_op_advance_guide.md)（包含 Embedding、VectorStore 和并发执行等高级功能）。

### 📝 Step2 配置config

以下示例展示如何构建一个 MCP（Model Context Protocol）服务。创建配置文件 `my_mcp_config.yaml`：

```yaml
backend: mcp

mcp:
  transport: sse
  host: "0.0.0.0"
  port: 8001

flow:
  demo_mcp_flow:
    flow_content: MockSearchOp()
    description: "Search results for a given query."
    input_schema:
      query:
        type: string
        description: "User query"
        required: true

llm:
  default:
    backend: openai_compatible
    model_name: qwen3-30b-a3b-instruct-2507
    params:
      temperature: 0.6
```

### 🚀 Step3 启动 MCP 服务

```bash
flowllm \
  config=my_mcp_config \
  backend=mcp \  # 可选，覆盖config配置
  mcp.transport=sse \  # 可选，覆盖config配置
  mcp.port=8001 \  # 可选，覆盖config配置
  llm.default.model_name=qwen3-30b-a3b-thinking-2507  # 可选，覆盖config配置
```

服务启动后可以参考[Client Guide](guide/client_guide.md)来使用服务，可以直接获取模型所需要的tool_call。
