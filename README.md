# flowllm

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)

flowllm is a flexible large language model workflow framework that provides a modular pipeline architecture for building complex AI applications. The framework supports multiple LLM providers, vector storage backends, and tool integrations, enabling you to easily build Retrieval-Augmented Generation (RAG), intelligent agents, and other AI-powered applications.

## 🚀 Key Features

### 🔧 Modular Architecture
- **Pipeline System**: Flexible pipeline configuration supporting both serial and parallel operations
- **Operation Registry**: Extensible operation registry with support for custom operations
- **Configuration-Driven**: Manage entire applications through YAML configuration files

### 🤖 LLM Support
- **Multi-Provider Compatible**: Support for OpenAI-compatible APIs
- **Streaming Responses**: Real-time streaming output support
- **Tool Calling**: Built-in tool calling and parallel execution support
- **Reasoning Mode**: Chain-of-thought reasoning support

### 📚 Vector Storage
- **Multi-Backend Support**: 
  - Elasticsearch
  - ChromaDB
  - Local file storage
- **Embedding Models**: Support for multiple embedding models
- **Workspace Management**: Multi-tenant vector storage management

### 🛠️ Rich Tool Ecosystem
- **Code Execution**: Python code execution tool
- **Web Search**: Integrated Tavily and DashScope search
- **MCP Protocol**: Model Context Protocol support
- **Termination Control**: Intelligent conversation termination management

### 🌐 API Services
- **RESTful API**: FastAPI-powered HTTP services
- **MCP Server**: Model Context Protocol server support
- **Multiple Endpoints**: Retriever, summarizer, vector store, agent APIs

## 📦 Installation

### Prerequisites
- Python 3.12+
- pip or poetry

### Installation Steps

```bash
# Clone the repository
git clone https://github.com/your-username/flowllm.git
cd flowllm

# Install dependencies
pip install -e .

# Or using poetry
poetry install
```

### Environment Configuration

Copy the environment template:
```bash
cp example.env .env
```

Edit the `.env` file to configure necessary API keys:

```bash
# LLM Configuration
LLM_API_KEY=sk-your-llm-api-key
LLM_BASE_URL=https://your-llm-endpoint/v1

# Embedding Model Configuration
EMBEDDING_API_KEY=sk-your-embedding-api-key
EMBEDDING_BASE_URL=https://your-embedding-endpoint/v1

# Elasticsearch (Optional)
ES_HOSTS=http://localhost:9200

# DashScope Search (Optional)
DASHSCOPE_API_KEY=sk-your-dashscope-key
```

## 🏃 Quick Start

### 1. Start HTTP Service

```bash
flowllm \
  http_service.port=8001 \
  llm.default.model_name=qwen3-32b \
  embedding_model.default.model_name=text-embedding-v4 \
  vector_store.default.backend=local_file
```

### 2. Start MCP Server

```bash
flowllm_mcp \
  mcp_transport=stdio \
  http_service.port=8001 \
  llm.default.model_name=qwen3-32b \
  embedding_model.default.model_name=text-embedding-v4 \
  vector_store.default.backend=local_file
```

### 3. API Usage Examples

#### Retriever API
```python
import requests

response = requests.post('http://localhost:8001/retriever', json={
    "query": "What is artificial intelligence?",
    "top_k": 5,
    "workspace_id": "default",
    "config": {}
})
print(response.json())
```

#### Agent API
```python
response = requests.post('http://localhost:8001/agent', json={
    "query": "Help me search for the latest AI technology trends",
    "workspace_id": "default",
    "config": {}
})
print(response.json())
```

## ⚙️ Configuration Guide

### Pipeline Configuration Syntax

flowllm uses an intuitive string syntax to define operation pipelines:

```yaml
api:
  # Serial execution: op1 -> op2 -> op3
  retriever: recall_vector_store_op->summarizer_op
  
  # Parallel execution: [op1 | op2] runs in parallel
  summarizer: mock1_op->[mock4_op->mock2_op|mock5_op]->mock3_op
  
  # Mixed mode: combination of serial and parallel
  agent: react_v1_op
```

### Complete Configuration Example

```yaml
# HTTP Service Configuration
http_service:
  host: "0.0.0.0"
  port: 8001
  timeout_keep_alive: 600
  limit_concurrency: 64

# Thread Pool Configuration
thread_pool:
  max_workers: 10

# API Pipeline Definitions
api:
  retriever: recall_vector_store_op
  summarizer: update_vector_store_op
  vector_store: vector_store_action_op
  agent: react_v1_op

# Operation Configuration
op:
  react_v1_op:
    backend: react_v1_op
    llm: default
    params:
      max_steps: 10
      tool_names: "code_tool,tavily_search_tool,terminate_tool"

# LLM Configuration
llm:
  default:
    backend: openai_compatible
    model_name: qwen3-32b
    params:
      temperature: 0.6
      max_retries: 5

# Embedding Model Configuration
embedding_model:
  default:
    backend: openai_compatible
    model_name: text-embedding-v4
    params:
      dimensions: 1024

# Vector Store Configuration
vector_store:
  default:
    backend: local_file  # or elasticsearch, chroma
    embedding_model: default
    params:
      store_dir: "./vector_store_data"
```

## 🧩 Architecture Design

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   MCP Server    │    │  Configuration  │
│                 │    │                 │    │     Parser      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │  flowllm Service │
                    └─────────────────┘
                             │
                    ┌─────────────────┐
                    │    Pipeline     │
                    │    Context      │
                    └─────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Operations  │    │    Tools    │    │Vector Stores│
│             │    │             │    │             │
│ • ReAct     │    │ • Code      │    │ • File      │
│ • Recall    │    │ • Search    │    │ • ES        │
│ • Update    │    │ • MCP       │    │ • Chroma    │
│ • Mock      │    │ • Terminate │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Data Flow

```
Request → Configuration → Pipeline → Operations → Tools/VectorStore → Response
```

## 🔧 Development Guide

### Custom Operations

```python
from flowllm.op import OP_REGISTRY
from flowllm.op.base_op import BaseOp


@OP_REGISTRY.register()
class CustomOp(BaseOp):
    def execute(self):
        # Implement your custom logic
        request = self.context.request
        response = self.context.response

        # Process request
        result = self.process_data(request.query)

        # Update response
        response.metadata["custom_result"] = result
```

### Custom Tools

```python
from flowllm.tool import TOOL_REGISTRY
from flowllm.tool.base_tool import BaseTool


@TOOL_REGISTRY.register()
class CustomTool(BaseTool):
    name: str = "custom_tool"
    description: str = "Custom tool description"
    parameters: dict = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input parameter"}
        },
        "required": ["input"]
    }

    def _execute(self, input: str, **kwargs):
        # Implement tool logic
        return f"Processing result: {input}"
```

### Custom Vector Stores

```python
from flowllm.vector_store import VECTOR_STORE_REGISTRY
from flowllm.vector_store.base_vector_store import BaseVectorStore


@VECTOR_STORE_REGISTRY.register("custom_store")
class CustomVectorStore(BaseVectorStore):
    def search(self, query: str, top_k: int = 10, **kwargs):
        # Implement search logic
        pass

    def insert(self, nodes: List[VectorNode], **kwargs):
        # Implement insertion logic
        pass
```

## 🧪 Testing

```bash
# Run tests
pytest

# Run specific tests
pytest tests/test_pipeline.py

# Generate coverage report
pytest --cov=flowllm tests/
```

## 🤝 Contributing

We welcome community contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Environment Setup

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run code formatting
black flowllm/
isort flowllm/

# Run type checking
mypy flowllm/
```

## 📚 Documentation

- [API Documentation](docs/api.md)
- [Configuration Guide](docs/configuration.md)
- [Operations Development](docs/operations.md)
- [Tools Development](docs/tools.md)
- [Deployment Guide](docs/deployment.md)

## 🐛 Bug Reports

If you find bugs or have feature requests, please create an issue on [GitHub Issues](https://github.com/your-username/flowllm/issues).

## 📄 License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Thanks to all developers and community members who have contributed to the flowllm project.

---

**flowllm** - Making AI workflow development simple and powerful 🚀