## 配置文件 default.yaml 指南

本文介绍如何使用 `flowllm/flowllm/config/default.yaml` 进行服务配置。你将看到一个可直接复制使用的完整示例，并逐段讲解每一项配置的作用与常见用法。

> **注意**：关于 Flow（流程）配置的详细说明，请参考 [Flow 配置指南](flow_guide.md)。

---

### 一、完整配置示例（可直接使用）

将下面内容保存为 `flowllm/flowllm/config/default.yaml`，即可启动一个包含 HTTP 与 MCP 的最小可用环境：

```yaml
backend: http
thread_pool_max_workers: 128

mcp:
  transport: sse
  host: "0.0.0.0"
  port: 8001

http:
  host: "0.0.0.0"
  port: 8002

# Flow 配置请参考 flow_guide.md
# flow:
#   demo_http_flow:
#     flow_content: GenSystemPromptOp() >> ChatOp()
#     description: "ai chat assistant"
#     input_schema:
#       query:
#         type: string
#         description: "user query"
#         required: true

llm:
  default:
    backend: openai_compatible
    model_name: qwen3-30b-a3b-instruct-2507
    params:
      temperature: 0.6
    token_count: # 可选，配置 token 计数后端
      backend: openai  # 支持 base、openai、hf 等
      model_name: qwen3-30b-a3b-instruct-2507

  qwen3_30b_instruct:
    backend: openai_compatible
    model_name: qwen3-30b-a3b-instruct-2507

  qwen3_30b_thinking:
    backend: openai_compatible
    model_name: qwen3-30b-a3b-thinking-2507

  qwen3_235b_instruct:
    backend: openai_compatible
    model_name: qwen3-235b-a22b-instruct-2507

  qwen3_235b_thinking:
    backend: openai_compatible
    model_name: qwen3-235b-a22b-thinking-2507

  qwen3_80b_instruct:
    backend: openai_compatible
    model_name: qwen3-next-80b-a3b-instruct

  qwen3_80b_thinking:
    backend: openai_compatible
    model_name: qwen3-next-80b-a3b-thinking

  qwen3_max_instruct:
    backend: openai_compatible
    model_name: qwen3-max

  qwen25_max_instruct:
    backend: openai_compatible
    model_name: qwen-max-2025-01-25

embedding_model:
  default:
    backend: openai_compatible
    model_name: text-embedding-v4
    params:
      dimensions: 1024

vector_store:
  default:
    backend: elasticsearch
    embedding_model: default
#    params:
#      hosts: "http://localhost:9200"
```

---

### 二、配置结构与含义

- backend
  - 决定应用主服务形态。当前示例使用 `http`，表示以 HTTP 服务为主入口（配合 `http` 段）。

- thread_pool_max_workers
  - 线程池并发上限。异步场景下用于提交同步任务的线程数量上限，通常按 CPU 与任务特性调优。

- mcp
  - `transport`: 传输方式，示例使用 `sse`（Server-Sent Events）。
  - `host`/`port`: MCP 服务监听地址与端口。若你有外部 MCP 工具或希望通过 MCP 集成，保持该段开启。
  - `flow` 相关：在 MCP 模式下，各 Flow 的 `input_schema` 为**必填**，需精确描述输入参数（类型、必填与否、描述等），以便 MCP 客户端进行参数校验与能力展示。

- http
  - `host`/`port`: HTTP 服务监听地址与端口。默认 `0.0.0.0:8002` 便于容器与本机调试。
  - `flow` 相关：在 HTTP 模式（包括 `stream: true` 的流式模式）下，`input_schema` **可选**；建议填写以获得更好的入参校验与自动文档生成体验。

- flow
  - 定义一组可被调用的流程（Flow）。每个 Flow 都由若干 Op 组合而成，可顺序（`>>`）或并行（`|`）组织。
  - **详细说明请参考 [Flow 配置指南](flow_guide.md)**，该文档包含完整的语法说明、示例和最佳实践。

- llm
  - 语言模型配置集合。
  - `default`: 全局默认模型，未指定时各 Op 使用该项。
  - 任意命名条目（如 `qwen3_30b_instruct`）可作为备用或按需切换的模型配置。
  - 字段说明：
    - `backend`: LLM 后端类型（如 `openai_compatible`）。
    - `model_name`: 具体模型名称。
    - `params`: 传递给后端的参数，如 `temperature` 等。
    - `token_count`（可选）：Token 计数配置，用于 `self.token_count()` 方法。
      - `backend`: Token 计数后端类型，支持 `base`（基于字符数估算）、`openai`（使用 tiktoken）、`hf`（使用 HuggingFace tokenizer）等。
      - `model_name`: Token 计数使用的模型名称（通常与 LLM 模型名称相同或对应）。
      - `params`: 传递给 Token 计数后端的参数（如 `use_mirror: true` 用于 HuggingFace）。

- embedding_model
  - 嵌入模型配置集合。
  - `default`: 默认嵌入模型，向量检索与相关任务会引用此项。
  - 字段说明类似 `llm`：`backend`、`model_name`、`params`。

- vector_store
  - 向量库配置集合。
  - `default`: 默认向量库配置。
  - `backend`: 向量库后端（如 `elasticsearch`）。
  - `embedding_model`: 指定使用哪一个嵌入模型条目（此处引用上面的 `embedding_model.default`）。
  - `params`: 后端连接参数（注释示例给出 `hosts`）。
