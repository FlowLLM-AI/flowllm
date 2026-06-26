# 快速开始

FlowLLM 是一个配置驱动的 LLM 应用框架：配置定义 Service、Component 和 Job；Job 顺序执行 Step；Service 把 Job 暴露给 CLI、HTTP
或 MCP。

## 安装

FlowLLM 要求 Python 3.11+。

```bash
git clone https://github.com/flowllm-ai/flowllm.git
cd flowllm
pip install -e ".[dev]"
```

需要 Claude Code wrapper 时再安装：

```bash
pip install -e ".[claude-code]"
```

## 启动

```bash
flowllm start
```

默认服务地址是 `127.0.0.1:2333`，默认 workspace 是 `.flowllm/`。可以用 dot notation 覆盖配置：

```bash
flowllm start service.port=8181 enable_logo=false
flowllm start workspace_dir=/tmp/flowllm-demo service.host=127.0.0.1 service.port=8181
```

启动时会自动创建：

```text
.flowllm/
├── metadata/
└── session/
```

## 调用 Job

服务启动后，CLI 的非 `start` 命令会调用服务端 Job：

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

## 配置

默认配置在 `flowllm/config/default.yaml`。可通过 `.env` 覆盖 LLM、embedding 等变量：

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

也可以指定 YAML/JSON：

```bash
flowllm start config=/path/to/app.yaml
```

最小 Job 配置：

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

常用 Job backend：

| backend      | 说明                 |
|--------------|--------------------|
| `base`       | 返回 JSON `Response` |
| `stream`     | 返回 SSE 流           |
| `background` | 后台循环任务             |
| `cron`       | 定时任务               |

更多实现细节见 [代码框架](./framework.md)。
