---
name: flowllm-dev
description: FlowLLM repository development guidance. Use when working in the flowllm codebase to implement, debug, test, review, or document FlowLLM runtime behavior, including CLI/client calls, services, application wiring, jobs, steps, components, configuration, streaming, registry registration, and tests.
---

# FlowLLM Development

Use this skill when changing or reviewing the FlowLLM repository. Treat the project as a configuration-driven LLM application framework whose execution path is:

```text
CLI / Client -> Service -> Application -> Job -> Step -> Component
```

Prefer small, framework-shaped changes over ad hoc shortcuts. Read the local files before editing; the repository may move faster than this skill.

## Start Here

Read these files first for most development tasks:

- `docs/zh/framework.md` for the architecture and extension model.
- `docs/zh/contributing.md` for development, tests, and contribution conventions.
- `flowllm/config/default.yaml` for built-in jobs, components, defaults, and env-var placeholders.
- The target implementation and nearby tests before making edits.

Use `rg` / `rg --files` for discovery. Do not assume a backend is available just because it appears in config; confirm it is registered and imported.

## Repository Map

- `flowllm/application.py`: application lifecycle, workspace setup, component/job instantiation, dependency ordering, CLI dispatch.
- `flowllm/config/config_parser.py`: config file loading, dot-notation overrides, env-var expansion, scalar conversion.
- `flowllm/config/default.yaml`: default HTTP service, jobs, and model/embedding/agent components.
- `flowllm/components/base_component.py`: `BaseComponent`, lifecycle hooks, `bind()` dependency declaration, workspace paths.
- `flowllm/components/component_registry.py`: global registry `R`, keyed by `(ComponentEnum, backend_name)`.
- `flowllm/components/runtime_context.py`: per-request `data`, `response`, stream queue, and mapping behavior.
- `flowllm/components/job/`: `BaseJob`, `StreamJob`, background jobs, cron jobs.
- `flowllm/components/service/`: HTTP and MCP service exposure.
- `flowllm/components/client/`: CLI-side clients.
- `flowllm/steps/base_step.py`: `BaseStep`, `Ref`, prompt loading, mapping, dispatch steps, job calls.
- `flowllm/steps/common/`: built-in example/status steps.
- `flowllm/schema/`: pydantic models for config, requests, responses, and stream chunks.
- `flowllm/enumeration/`: component and chunk enums.
- `tests/unit/` and `tests/integration/`: preferred examples for test style and coverage boundaries.

## Development Rules

- Implement externally callable behavior as a `Job` configured under `jobs:` and exposed by the active service.
- Implement workflow atoms as `BaseStep` subclasses under `flowllm/steps/`.
- Implement reusable long-lived infrastructure as `BaseComponent` subclasses under `flowllm/components/`.
- Register every backend with `@R.register("<backend_name>")`.
- Ensure the module containing a new registration is imported by the relevant package `__init__.py`; registration happens at import time.
- Put default user-visible behavior in `flowllm/config/default.yaml` when `flowllm start` should expose it.
- Keep service, application, job, step, and component responsibilities separate.
- Update docs when CLI behavior, config keys, service endpoints, public jobs, or user-visible defaults change.
- Add focused tests for bug fixes, new steps, new jobs, config parsing, registry behavior, lifecycle ordering, service exposure, and streaming behavior.

## Common Implementation Patterns

### Add a Step and Job

Create a step:

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

Expose it in config:

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

Then verify the package import path registers the step.

### Add a Component

Subclass `BaseComponent`, set a non-`BASE` `component_type`, register it, and put startup/cleanup in `_start()` and `_close()`:

```python
from flowllm.components import BaseComponent, R
from flowllm.enumeration import ComponentEnum


@R.register("my_backend")
class MyComponent(BaseComponent):
    component_type = ComponentEnum.EMBEDDING_STORE

    async def _start(self) -> None:
        ...

    async def _close(self) -> None:
        ...
```

Declare component dependencies with `BaseComponent.bind()` so `Application` can start components in topological order:

```python
self.embedding_store = self.bind("default", BaseEmbeddingStore, optional=False)
```

### Use Components From Steps

Use `BaseStep.Ref` / existing descriptors when a step needs configured infrastructure. `BaseStep` already provides:

- `self.as_llm`: resolved to the configured AS LLM model.
- `self.agent_wrapper`: optional agent wrapper.

For tests, pass concrete objects through step kwargs when possible; `Ref` checks kwargs and context before resolving from the application context.

### Streaming

Use `StreamJob` for SSE output. Streaming steps should enqueue chunks through `RuntimeContext`:

```python
await self.context.add_stream_string(text, ChunkEnum.CONTENT)
```

`StreamJob` always emits a final `DONE` chunk. On exceptions it emits an `ERROR` chunk before `DONE`.

### Config and CLI

FlowLLM config supports:

- Default loading from `flowllm/config/default.yaml`.
- `config=/path/to/app.yaml` for YAML/JSON config.
- Dot-notation overrides such as `service.port=8181`.
- `${VAR}` and `${VAR:-default}` env-var expansion.
- Automatic conversion for booleans, numbers, JSON lists/dicts, and null, while preserving leading-zero strings.

The CLI entry point is `flowllm.application:main`. `flowllm start` starts the service; other actions call a server-side job of the same name through the selected client backend.

## Testing

Run the narrowest useful checks first, then broaden when touching shared surfaces:

```bash
pytest tests/unit
pytest tests/integration
pytest
pre-commit run --all-files
```

Use unit tests for pure behavior such as config parsing, registry behavior, steps, mapping, and lifecycle helpers. Use integration tests when startup, service/client behavior, application wiring, streaming, or external-facing CLI behavior is involved.

If LLM, embedding, Claude Code, MCP, network, or external service credentials are required and unavailable, state exactly which checks were skipped and why.

## Review Checklist

Before finishing a FlowLLM change, confirm:

- New backends are registered with `R` and imported at package import time.
- Config keys match constructor parameters and pydantic schema expectations.
- `enable_serve` and job type match the intended HTTP/MCP exposure.
- Async lifecycle hooks are idempotent enough for start/close/restart paths.
- Required dependencies use `optional=False`; optional dependencies handle `None`.
- Steps mutate `RuntimeContext` intentionally and return/update `context.response` for non-stream jobs.
- Streaming paths emit content/error chunks and allow the final `DONE` marker.
- User-visible behavior is documented.
- Tests cover both the main path and the most likely failure path.
