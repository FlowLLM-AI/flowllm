# Quick Start

FlowLLM is a configuration-driven LLM application framework: configuration defines Services, Components, and Jobs; Jobs execute Steps in order; Services expose Jobs through CLI, HTTP, or MCP.

## Installation

FlowLLM requires Python 3.11+.

```bash
git clone https://github.com/flowllm-ai/flowllm.git
cd flowllm
pip install -e ".[dev]"
```

Install the Claude Code wrapper only when needed:

```bash
pip install -e ".[claude-code]"
```

## Start

```bash
flowllm start
```

The default service address is `127.0.0.1:2333`, and the default workspace is `.flowllm/`. You can override configuration values with dot notation:

```bash
flowllm start service.port=8181 enable_logo=false
flowllm start workspace_dir=/tmp/flowllm-demo service.host=127.0.0.1 service.port=8181
```

FlowLLM creates the following directories automatically on startup:

```text
.flowllm/
├── metadata/
└── session/
```

## Call Jobs

After the service starts, CLI commands other than `start` call server-side Jobs:

```bash
flowllm version
flowllm health_check
flowllm help
flowllm demo query="Hello FlowLLM" min_score=0.8
flowllm add a=1 b=2
```

The HTTP entrypoint is `POST /<job_name>`:

```bash
curl -s http://127.0.0.1:2333/add \
  -H 'Content-Type: application/json' \
  -d '{"a":1,"b":2}'
```

Streaming Jobs return SSE:

```bash
flowllm stream_demo query="Hi" repeat=3 interval=0.05

curl -N http://127.0.0.1:2333/stream_demo \
  -H 'Content-Type: application/json' \
  -d '{"query":"Hi","repeat":3,"interval":0.05}'
```

## Configuration

The default configuration is in `flowllm/config/default.yaml`. You can use `.env` to override LLM, embedding, and other variables:

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

You can also provide a YAML or JSON file:

```bash
flowllm start config=/path/to/app.yaml
```

Minimal Job configuration:

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

Common Job backends:

| backend      | Description                  |
|--------------|------------------------------|
| `base`       | Returns a JSON `Response`    |
| `stream`     | Returns an SSE stream        |
| `background` | Background loop task         |
| `cron`       | Scheduled task               |

For more implementation details, see [Framework](./framework.md).
