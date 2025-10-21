<p align="center">
 <img src="docs/figure/logo.png" alt="FlowLLM Logo" width="50%">
</p>

<p align="center">
  <strong>FlowLLM: A Flexible Framework for Building LLM-Powered Flows</strong><br>
  <em>Flow with Intelligence, Build with Simplicity.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/flowllm/"><img src="https://img.shields.io/badge/python-3.12+-blue" alt="Python Version"></a>
  <a href="https://pypi.org/project/flowllm/"><img src="https://img.shields.io/badge/pypi-v0.1.10-blue?logo=pypi" alt="PyPI Version"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-black" alt="License"></a>
</p>

---

FlowLLM is a **configuration-driven** framework for building LLM-powered applications. Write operations once, compose them via YAML configuration, and automatically get HTTP APIs and MCP tools—no boilerplate code needed.

## 📖 Table of Contents

- [Why FlowLLM?](#-why-flowllm)
- [Getting Started](#-getting-started)
- [Core Workflow](#-core-workflow)
- [Architecture](#-architecture)
- [Features](#-features)
- [Resources](#-resources)

---

## 💡 Why FlowLLM?

**The Problem**: Building LLM services traditionally requires writing boilerplate routes, validation, documentation, and orchestration code for each endpoint.

**The Solution**: FlowLLM's configuration-driven approach lets you:

- ✅ **Write Operations Once** - Focus on business logic in reusable Python ops
- ✅ **Configure, Don't Code** - Compose workflows using YAML configuration
- ✅ **Auto-Generate Services** - HTTP and MCP endpoints created automatically
- ✅ **Built-in Orchestration** - Sequential (`>>`), parallel (`|`), and nested flows
- ✅ **Zero Boilerplate** - No routes, validators, or service code needed

| Feature | Traditional Approach | FlowLLM Approach |
|---------|---------------------|------------------|
| **Service Creation** | Write FastAPI/Flask routes, handlers, validation | Write YAML config - auto-registers HTTP + MCP |
| **API Documentation** | Manually write OpenAPI specs | Auto-generated from config |
| **Workflow Changes** | Modify Python code, test, redeploy | Update config, restart service |
| **Orchestration** | Write custom coordination code | Use expressions: `>>`, `\|`, `()` |

**Perfect For**: Rapid prototyping, microservices, AI agent tools, data pipelines, enterprise AI applications.

---

## 🚀 Getting Started

### Installation

```bash
pip install flowllm
```

For detailed setup instructions, see the [Installation Guide](INSTALLATION.md).

### Quick Start

See the [Quick Start Guide](QUICKSTART.md) to build your first LLM service in 30 seconds.

---

## 🎯 Core Workflow

```
┌─────────────────┐      ┌──────────────────┐      ┌──────────────────────────┐
│   Build Ops     │      │  Configure YAML  │      │    Auto-Register         │
│   (Python)      │  →   │   (Workflows)    │  →   │    Services              │
│                 │      │                  │      │                          │
│  • BaseOp       │      │  flow:           │      │  ┌────────────────────┐  │
│  • BaseAsyncOp  │      │    workflow:     │      │  │  HTTP Service      │  │
│  • BaseMcpOp    │      │      description │      │  │  POST /workflow    │  │
│  • BaseRayOp    │      │      flow_content│      │  │  OpenAPI docs      │  │
│                 │      │      tool:       │      │  └────────────────────┘  │
│                 │      │        parameters│      │                          │
│                 │      │                  │      │  ┌────────────────────┐  │
│                 │      │  backend: http   │      │  │  MCP Service       │  │
│                 │      │     or mcp       │      │  │  Tool: workflow    │  │
│                 │      │                  │      │  │  Auto-discovered   │  │
│                 │      │                  │      │  └────────────────────┘  │
└─────────────────┘      └──────────────────┘      └──────────────────────────┘
```

**Three Simple Steps:**

1. **Create an Op** - Write a Python class implementing your business logic
2. **Configure in YAML** - Define workflow and service endpoints
3. **Launch** - Run one command to start your HTTP or MCP service

**No manual routing, no endpoint definitions, no service code - just configuration!**

---

## ✨ Architecture

FlowLLM adopts a **three-layer configuration-driven architecture**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Service Layer (外层)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ HTTP Service │  │  MCP Service │  │  CMD Service │              │
│  │   FastAPI    │  │   FastMCP    │  │  Command Line│              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                 Auto-Register from Configuration                    │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────────┐
│                         Flow Layer (中层)                            │
│  • Sequential: op1 >> op2 >> op3                                    │
│  • Parallel: (op1 | op2 | op3)                                      │
│  • Nested: op1 >> (op2 | op3) >> op4                                │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────────┐
│                    Foundation Layer (底层)                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Op Lib   │  │ LLM Lib  │  │Embedding │  │ Storage  │            │
│  ├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤            │
│  │ BaseOp   │  │ OpenAI   │  │ OpenAI   │  │ElasticS. │            │
│  │BaseAsync │  │ LiteLLM  │  │Compatible│  │ChromaDB  │            │
│  │BaseTool  │  │DashScope │  │          │  │  Local   │            │
│  │BaseMcpOp │  │  Custom  │  │  Custom  │  │  Cache   │            │
│  │BaseRayOp │  │          │  │          │  │          │            │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Separation of Concerns** - Ops (business logic), Flows (orchestration), Services (protocol handling)
2. **Configuration over Code** - Ops in Python, Flows in YAML, Services auto-generated
3. **Dependency Injection** - ServiceContext manages shared resources (LLM, VectorStore, etc.)
4. **Registry Pattern** - Dynamic loading and discovery based on configuration

### Complete Data Flow

```
Request → Service Layer (HTTP/MCP)
       ↓
Flow Layer (Parse expression → Build DAG)
       ↓
Foundation Layer (Execute ops with context)
       ↓
Response (JSON/MCP result)
```

---

## 🎯 Features

### 📦 Pre-built Operations

**Gallery Ops**: `SimpleLLMOp`, `ReactLLMOp`, `ExecuteCodeOp`, `TranslateCodeOp`  
**Search Ops**: `TavilySearchOp`, `DashScopeSearchOp`, `McpSearchOp`  
**Research Ops**: `DashScopeDeepResearchOp`, `LangChainDeepResearchOp`  
**Data Ops**: Various extraction and processing operations

### 🔧 Advanced Capabilities

- **Multi-LLM Support** - OpenAI, LiteLLM (100+ providers), DashScope, custom providers
- **Vector Storage** - Elasticsearch, ChromaDB, local file-based, in-memory
- **Async/Streaming** - Full async support with SSE streaming responses
- **Distributed Computing** - Ray integration for scaling operations
- **Caching** - Intelligent caching with TTL and automatic serialization
- **Web Crawling** - Integrated `crawl4ai` for content extraction

### 🧪 Workflow Patterns

- **Simple LLM Chat** - Direct model interaction
- **Multi-Step Research** - Sequential search, summarization, validation
- **Parallel Processing** - Concurrent sentiment analysis, keyword extraction
- **Complex Pipelines** - Nested sequential and parallel operations

---

## 📚 Resources

### Documentation

- **[Installation Guide](INSTALLATION.md)** - Setup and environment configuration
- **[Quick Start Guide](QUICKSTART.md)** - Build your first service
- **Specialized Guides** in `doc/`:
  - [Deep Research Guide](docs/deep_research.md)
  - [Financial Supply Guide](docs/fin_supply_readme.md)
  - [Vector Store Guide](docs/vector_store.md)

### Examples & Configuration

- **Examples**: `test/` directory for practical examples
- **Configuration**: `flowllm/config/` for sample configs

### Latest Updates

- **[2025-10]** FlowLLM v0.1.10 - Enhanced async support and stability
- **[2025-09]** Financial data modules with 26+ pre-built flows
- **[2025-09]** Deep research with multiple search backends
- **[2025-08]** MCP (Model Context Protocol) support
- **[2025-06]** Multi-backend vector storage

---


## ⚖️ License

Apache License 2.0 - see [LICENSE](./LICENSE) file for details.

---

## 🌟 Star History

If you find FlowLLM useful, please consider giving it a star!
