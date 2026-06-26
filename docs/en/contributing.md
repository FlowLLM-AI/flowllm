# Open Source and Contributing

FlowLLM repository: **https://github.com/flowllm-ai/flowllm**

For your first local run, see [Quick Start](./quick_start.md). Before changing the runtime, Jobs, Steps, components, services, or configuration, read [Framework](./framework.md).

## Local Development

FlowLLM requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Install the complete optional dependency set when needed:

```bash
pip install -e ".[full]"
```

Main directories:

| Path                          | Description                         |
|-------------------------------|-------------------------------------|
| `flowllm/`                    | Python package source               |
| `flowllm/config/default.yaml` | Default configuration               |
| `flowllm/components/`         | Services, clients, Jobs, components |
| `flowllm/steps/`              | Step implementations                |
| `flowllm/schema/`             | Request, response, and config models |
| `tests/`                      | Unit and integration tests          |
| `docs/zh/`                    | Chinese documentation               |

## Development Conventions

Follow the main runtime path:

```text
CLI / Client -> Service -> Application -> Job -> Step -> Component
```

- Prefer exposing external capabilities as Jobs, then serve them through HTTP or MCP Service.
- Put reusable infrastructure in `flowllm/components/` and inherit from `BaseComponent`.
- Put atomic business operations in `flowllm/steps/` and inherit from `BaseStep`.
- Register new implementations with `@R.register("<backend_name>")`, and make sure the module is imported by `__init__.py`.
- Put default behavior in `flowllm/config/default.yaml`, keeping `flowllm start` runnable.
- Update documentation when changing user-visible behavior.

## Testing

Recommended before submitting:

```bash
pre-commit run --all-files
pytest
```

For focused validation:

```bash
pytest tests/unit
pytest tests/integration
```

Testing guidance:

- Add regression tests when fixing bugs.
- Cover core paths and failure paths when adding Steps, Jobs, or components.
- Cover user entrypoints when changing config parsing, the registry, lifecycle behavior, service exposure, or streaming output.
- For tests that depend on LLMs, embeddings, or external services, document the required environment in the PR.

## Commits and PRs

Conventional Commits are recommended:

```text
<type>(<scope>): <subject>
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`, `style`.

Examples:

```text
feat(step): add reverse text demo
fix(config): preserve leading zero strings
docs(zh): update quick start
test(service): cover stream response
```

PR titles should follow the same format. For larger changes, first describe the background, target behavior, impact scope, and test plan in an Issue.
