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
  <strong>FlowLLM: Build LLM applications with ease.</strong><br>
</p>

FlowLLM is a configuration-driven LLM application framework that organizes workflows, service entrypoints, and
long-lived components with **Service, Job, Step, and Component**.

## 🧠 FlowLLM Development Skill

FlowLLM ships with a development Skill for coding agents. It explains the framework conventions, repository map,
extension points, testing workflow, and review checklist for building or extending FlowLLM applications.

Start here when changing the codebase: [FlowLLM Development Skill](skills/flowllm_dev/SKILL.md).

## ✨ Core Features

- **Configuration-driven**: Starts from `flowllm/config/default.yaml`, with config files and dot-notation overrides.
- **Unified path**: `CLI / Client -> Service -> Application -> Job -> Step -> Component`.
- **Flexible Jobs**: Supports sync, streaming, background, and scheduled tasks exposed through HTTP or MCP.
- **Pluggable components**: Extend Steps, Services, Clients, LLMs, Embeddings, Embedding Stores, and Agent Wrappers
  through registry `R`.

<p align="center">
  <img src="docs/figure/flowllm-architecture.svg" alt="FlowLLM Architecture" width="92%">
</p>

## 🚀 Quick Start

### Installation

FlowLLM requires Python 3.11+.

Install from pip:

```bash
pip install flowllm
```

Install from source:

```bash
git clone https://github.com/flowllm-ai/flowllm.git
cd flowllm
pip install -e .
```

### Start the Service

```bash
flowllm start
```

The default service address is `127.0.0.1:2333`, and the default workspace is `.flowllm/`.
Override configuration with dot notation:

```bash
flowllm start service.port=8181 enable_logo=false
flowllm start workspace_dir=/tmp/flowllm-demo service.host=127.0.0.1 service.port=8181
```

See the [Quick Start](docs/en/quick_start.md) for more startup and invocation examples.

## 🧩 Use FlowLLM

```bash
flowllm version
flowllm health_check
flowllm help
flowllm demo query="Hello FlowLLM" min_score=0.8
flowllm add a=1 b=2
```

CLI commands other than `start` call server-side Jobs with the same name. HTTP uses `POST /<job_name>`:

```bash
curl -s http://127.0.0.1:2333/add \
  -H 'Content-Type: application/json' \
  -d '{"a":1,"b":2}'
```

See [Quick Start](docs/en/quick_start.md) for service, CLI, HTTP, and streaming examples.

## ⚙️ Build Applications

FlowLLM applications are configured from `flowllm/config/default.yaml` or your own YAML/JSON config. Add a capability by
registering a Step or Component, then exposing it as a Job:

```yaml
jobs:
  reverse:
    backend: base
    description: "reverse text"
    steps:
      - backend: reverse_step
```

Configuration supports `.env`, `${VAR}`, `${VAR:-default}`, dot-notation overrides, and direct config files:

```bash
flowllm start config=/path/to/app.yaml
```

For implementation rules and examples, use the [FlowLLM Development Skill](skills/flowllm_dev/SKILL.md). For the compact
architecture reference, see [Code Framework](docs/en/framework.md).

## 🆕 Minimal CLI Flow

For scripts that do not need the full service framework, `flowllm.lite` maps `fl --action --field value` to a Pydantic
config and a small ordered `BaseFlow`. See [FlowLLM Lite](flowllm/lite/README.md).

## 🗺️ Roadmap

| Item                      | Description                                                                                         |
|---------------------------|-----------------------------------------------------------------------------------------------------|
| Agent wrapper integration | Integrate FlowLLM into Agent wrappers so agents can develop FlowLLM Steps and Jobs from your ideas. |
| TypeScript frontend       | Add a TypeScript frontend for building and developing FlowLLM applications through the UI.          |

## 📚 Documentation

- [Quick Start](docs/en/quick_start.md)
- [Code Framework](docs/en/framework.md)
- [Contributing](docs/en/contributing.md)
- [FlowLLM Development Skill](skills/flowllm_dev/SKILL.md)

## 🤝 Open Source and Contributing

FlowLLM is licensed under Apache 2.0. Before contributing, read the [contribution guide](docs/en/contributing.md)
and [development skill](skills/flowllm_dev/SKILL.md).

Install development dependencies from source:

```bash
pip install -e ".[dev]"
```

Before submitting changes, run:

```bash
pre-commit run --all-files
pytest
```

## 📄 License

This project is open source under the Apache License 2.0. See [LICENSE](./LICENSE) for details.

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=flowllm-ai/flowllm&type=Date)](https://www.star-history.com/#flowllm-ai/flowllm&Date)
