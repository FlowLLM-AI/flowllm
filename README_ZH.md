<p align="center">
  <img src="docs/figure/logo.png" alt="FlowLLM Logo" width="50%">
</p>

<p align="center">
  <a href="https://pypi.org/project/flowllm/"><img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python Version"></a>
  <a href="https://pypi.org/project/flowllm/"><img src="https://img.shields.io/pypi/v/flowllm.svg?logo=pypi" alt="PyPI Version"></a>
  <a href="https://pepy.tech/project/flowllm/"><img src="https://img.shields.io/pypi/dm/flowllm" alt="PyPI Downloads"></a>
  <a href="https://github.com/flowllm-ai/flowllm"><img src="https://img.shields.io/github/commit-activity/m/flowllm-ai/flowllm?style=flat-square" alt="GitHub commit activity"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-black" alt="License"></a>
  <a href="./README.md"><img src="https://img.shields.io/badge/English-Click-yellow" alt="English"></a>
  <a href="./README_ZH.md"><img src="https://img.shields.io/badge/简体中文-点击查看-orange" alt="简体中文"></a>
  <a href="https://github.com/flowllm-ai/flowllm"><img src="https://img.shields.io/github/stars/flowllm-ai/flowllm?style=social" alt="GitHub Stars"></a>
  <a href="https://deepwiki.com/flowllm-ai/flowllm"><img src="https://img.shields.io/badge/DeepWiki-Ask_Devin-navy.svg" alt="DeepWiki"></a>
</p>

<p align="center">
  <strong>FlowLLM: 轻松构建 LLM 应用。</strong><br>
</p>

FlowLLM 是一个配置驱动的 LLM 应用框架，以 **Service、Job、Step、Component** 作为核心构建块：把工作流声明为 Job，用有序 Step 实现流程，通过 CLI、HTTP 或 MCP 暴露 Job，并将模型、Embedding Store、Agent wrapper 等长期存在的基础设施作为 Component 统一管理生命周期和依赖。

## 核心特性

- **配置驱动**：默认从 `flowllm/config/default.yaml` 启动，也支持 `config=/path/to/app.yaml` 和 `service.port=8181` 这类 dot notation 覆盖。
- **统一运行链路**：`CLI / Client -> Service -> Application -> Job -> Step -> Component`，服务层只负责暴露能力，业务逻辑沉到 Job 和 Step。
- **多种服务形态**：HTTP Service 基于 FastAPI 暴露 `POST /<job_name>`；MCP Service 基于 FastMCP 将非流式 Job 暴露为工具。
- **同步、流式、后台与定时任务**：内置 `base`、`stream`、`background`、`cron` 四类 Job backend。
- **可插拔组件**：通过全局注册表 `R` 注册 Step、Service、Client、LLM、Embedding、Embedding Store 和 Agent Wrapper。
- **AgentScope 集成**：内置 AgentScope LLM/Embedding wrapper，支持 OpenAI、DashScope、Anthropic、DeepSeek、Gemini、Moonshot、Ollama、xAI 等后端。
- **Agent wrapper**：默认提供 AgentScope wrapper，可选安装 Claude Code wrapper，把 Job 作为工具提供给 Agent。

<p align="center">
  <img src="docs/figure/flowllm-architecture.svg" alt="FlowLLM Architecture" width="92%">
</p>

## 快速开始

### 安装

FlowLLM 要求 Python 3.11+。

从源码安装开发依赖：

```bash
git clone https://github.com/flowllm-ai/flowllm.git
cd flowllm
pip install -e ".[dev]"
```

如果需要 Claude Code wrapper，再安装可选依赖：

```bash
pip install -e ".[claude-code]"
```

需要完整可选依赖时：

```bash
pip install -e ".[full]"
```

### 启动服务

```bash
flowllm start
```

默认服务地址是 `127.0.0.1:2333`，默认 workspace 是 `.flowllm/`。启动时会自动创建：

```text
.flowllm/
├── metadata/
└── session/
```

可以用命令行覆盖配置：

```bash
flowllm start service.port=8181 enable_logo=false
flowllm start workspace_dir=/tmp/flowllm-demo service.host=127.0.0.1 service.port=8181
```

更多启动和调用示例见 [快速开始](docs/zh/quick_start.md)。

## 调用 Job

启动服务后，CLI 的非 `start` 命令会通过 client 调用服务端同名 Job：

```bash
flowllm version
flowllm health_check
flowllm help
flowllm demo query="Hello FlowLLM" min_score=0.8
flowllm add a=1 b=2
```

HTTP 入口是 `POST /<job_name>`：

```bash
curl -s http://127.0.0.1:2333/add \
  -H 'Content-Type: application/json' \
  -d '{"a":1,"b":2}'
```

流式 Job 返回 SSE：

```bash
flowllm stream_demo query="Hi" repeat=3 interval=0.05

curl -N http://127.0.0.1:2333/stream_demo \
  -H 'Content-Type: application/json' \
  -d '{"query":"Hi","repeat":3,"interval":0.05}'
```

内置 Job：

| Job | backend | 说明 |
| --- | --- | --- |
| `version` | `base` | 返回 FlowLLM 包版本。 |
| `health_check` | `base` | 返回组件健康检查摘要。 |
| `help` | `base` | 列出已注册 Job 及其 metadata。 |
| `demo` | `base` | 两步 echo 示例。 |
| `add` | `base` | 两数相加示例。 |
| `stream_demo` | `stream` | 将输入按字符流式输出。 |

## 配置

默认配置位于 `flowllm/config/default.yaml`。配置根节点包括应用参数、服务、Job 和 Component：

```yaml
service:
  backend: http

jobs:
  add:
    backend: base
    description: "add two numbers"
    steps:
      - backend: add_step
```

可通过 `.env` 覆盖模型和 embedding 相关变量：

```bash
cat > .env <<'EOF'
LLM_BACKEND=openai
LLM_MODEL_NAME=qwen3.7-plus
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

EMBEDDING_BACKEND=openai
EMBEDDING_MODEL_NAME=text-embedding-v4
EMBEDDING_API_KEY=your_api_key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EOF
```

也可以指定 YAML 或 JSON 配置文件：

```bash
flowllm start config=/path/to/app.yaml
```

配置解析支持 `${VAR}`、`${VAR:-default}`、bool、数字、JSON list/dict 和 `null` 自动转换。

## 代码框架

FlowLLM 的核心分层如下：

```text
CLI / Client -> Service -> Application -> Job -> Step -> Component
```

| 层级 | 作用 |
| --- | --- |
| `Application` | 加载配置，创建 workspace，装配 Service、Component 和 Job，并按依赖顺序启动生命周期。 |
| `Service` | 将可服务的 Job 暴露为 HTTP 路由或 MCP 工具。 |
| `Job` | 外部可调用能力或后台流程的编排单元，按顺序执行 Step。 |
| `Step` | 工作流原子操作，读写 `RuntimeContext`、`Response` 和流式队列。 |
| `Component` | 长期存在的基础设施，例如 LLM、Embedding、Embedding Store、Agent Wrapper。 |
| `Registry` | 全局注册表 `R`，按 `(component_type, backend_name)` 查找实现。 |

新增 Step 的最小示例：

```python
from flowllm.components import R
from flowllm.steps import BaseStep


@R.register("reverse_step")
class ReverseStep(BaseStep):
    async def execute(self):
        text = self.context.get("text", "")
        self.context.response.answer = text[::-1]
        return self.context.response
```

然后在配置中声明 Job：

```yaml
jobs:
  reverse:
    backend: base
    description: "reverse text"
    parameters:
      type: object
      properties:
        text:
          type: string
      required:
        - text
    steps:
      - backend: reverse_step
```

新增实现后要确保模块在包的 `__init__.py` 中被 import，否则注册装饰器不会执行。更多细节见 [代码框架](docs/zh/framework.md)。

## MCP 服务

将 service backend 改成 `mcp` 后，FlowLLM 会把非流式、`enable_serve: true` 的 Job 暴露为 MCP tool。`StreamJob` 不会被 MCP Service 暴露。

```yaml
service:
  backend: mcp
  transport: sse
  host: 127.0.0.1
  port: 2333
```

MCP transport 支持 `stdio`、`sse` 和 `streamable-http`。

## 文档

- [快速开始](docs/zh/quick_start.md)
- [代码框架](docs/zh/framework.md)
- [开源与贡献](docs/zh/contributing.md)
- [FlowLLM 开发 Skill](skills/flowllm_dev/SKILL.md)

## 开源与贡献

FlowLLM 使用 Apache License 2.0 开源。提交改动前建议阅读 [贡献指南](docs/zh/contributing.md) 和 [FlowLLM 开发 Skill](skills/flowllm_dev/SKILL.md)，并尽量运行：

```bash
pre-commit run --all-files
pytest
```

建议使用 Conventional Commits，例如：

```text
feat(step): add reverse text demo
fix(config): preserve leading zero strings
docs(zh): update readme
```

## License

This project is open source under the Apache License 2.0. See [LICENSE](./LICENSE) for details.
