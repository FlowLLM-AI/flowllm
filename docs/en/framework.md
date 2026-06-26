# FlowLLM Framework

FlowLLM's runtime path:

```text
CLI / Client -> Service -> Application -> Job -> Step -> Component
```

`Application` assembles services, components, and Jobs from configuration; `Service` exposes serveable Jobs; `Job` executes Steps in order; `Step` shares request data, responses, and streaming queues through `RuntimeContext`.

<p align="center">
  <img src="../figure/flowllm-framework.svg" alt="FlowLLM framework architecture" width="92%">
</p>

## Directory

```text
flowllm/
  application.py              # CLI entrypoint and Application lifecycle
  config/default.yaml         # Default service / jobs / components
  config/config_parser.py     # config=, dot notation, environment variable expansion
  components/
    base_component.py         # BaseComponent and bind dependency declarations
    component_registry.py     # Global registry R
    runtime_context.py        # Per-Job execution context
    job/                      # base / stream / background / cron
    service/                  # http / mcp
    client/                   # http / mcp
    as_llm/ as_embedding/     # Model wrappers
    embedding_store/
    agent_wrapper/
  steps/
    base_step.py              # BaseStep, Ref, dispatch_steps
    common/                   # version, help, health_check, demo, add, stream_demo
  schema/                     # Request, Response, StreamChunk, configuration models
  enumeration/                # ComponentEnum, ChunkEnum
```

Default workspace:

```text
.flowllm/
├── metadata/
└── session/
```

## Startup

`flowllm/application.py::main()` handles three command types:

| action         | Behavior                                                       |
|----------------|----------------------------------------------------------------|
| `start`        | Load `.env` and configuration, create `Application`, start Service |
| `find_flowllm` | Find the project path                                          |
| Other actions  | Call the server-side Job with the same name through the client |

Configuration parsing supports:

- Loading `flowllm/config/default.yaml` by default.
- `config=/path/to/app.yaml` for a YAML/JSON file.
- Dot notation overrides such as `service.port=8181`.
- Environment variable expansion with `${VAR}` and `${VAR:-default}`.
- Automatic conversion for bools, numbers, JSON lists/dicts, and null.

## Service

The HTTP service registers Jobs as endpoints:

| Job type              | HTTP behavior                                      |
|-----------------------|----------------------------------------------------|
| `BaseJob`             | `POST /<job.name>`, returns `Response` JSON        |
| `StreamJob`           | `POST /<job.name>`, returns `text/event-stream`    |
| `enable_serve: false` | Not registered                                     |

The MCP service exposes only non-streaming serveable Jobs. Background and scheduled Jobs are not exposed by default.

## Registry

FlowLLM uses the global registry `R`:

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

The registry key is `(component_type, backend_name)`. The same backend name can exist under different types; for example, `http` can be both a service backend and a client backend.

Registration happens when modules are imported. After adding a Step or Component, make sure its package `__init__.py` imports the new module; otherwise the `backend` configured in YAML cannot find its implementation.

## Component

Long-lived infrastructure inherits from `BaseComponent`. Common lifecycle methods:

- `start()`: resolve dependencies and call `_start()`.
- `close()`: call `_close()` and close owned components in reverse order.
- `restart()`: close and then start again.

Component dependencies are declared with `BaseComponent.bind()`, and `Application` starts components in dependency-topological order:

```python
self.embedding_store = self.bind("default", BaseEmbeddingStore, optional=False)
```

## Job

A Job is an orchestration unit for an externally callable capability or a background workflow. Jobs are configured under `jobs:`.

- `BaseJob`: creates a `RuntimeContext` for each call, executes Steps in order, and returns `context.response`.
- `StreamJob`: Steps write `StreamChunk` values to `stream_queue`, and the service layer outputs SSE.
- `BackgroundJob`: executes repeatedly based on `interval`.
- `CronJob`: executes on a cron expression.

Job configuration example:

```yaml
jobs:
  reverse:
    backend: base
    description: "reverse text"
    steps:
      - backend: reverse_step
```

## Step

A Step is an atomic workflow operation. It reads and writes `RuntimeContext`:

| Field          | Description                                 |
|----------------|---------------------------------------------|
| `data`         | Request parameters and shared inter-step data |
| `response`     | Final return value                          |
| `stream_queue` | Streaming output queue                      |

Streaming output:

```python
await self.context.add_stream_string(text, ChunkEnum.CONTENT)
```

Step configuration also supports `input_mapping`, `output_mapping`, `prompt_dict`, `dispatch_steps`, and `language`. Use `BaseStep.Ref` to access application components; `as_llm` and the optional `agent_wrapper` are provided by default.

## Default Capabilities

`flowllm/config/default.yaml` includes:

- `version`, `health_check`, `help`
- `demo`, `add`
- `stream_demo`
- Default `as_llm`, `as_embedding`, `embedding_store`, and `agent_wrapper`
