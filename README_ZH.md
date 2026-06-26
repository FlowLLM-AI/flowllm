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

FlowLLM 是一个配置驱动的 LLM 应用框架，用 **Service、Job、Step、Component** 组织工作流、服务入口和长期组件。

## 🧠 FlowLLM 开发 Skill

FlowLLM 提供面向编程 Agent 的开发 Skill，覆盖框架约定、仓库地图、扩展点、测试流程和 review checklist。

修改或扩展代码库时从这里开始：[FlowLLM 开发 Skill](skills/flowllm_dev/SKILL.md)。

## ✨ 核心特性

- **配置驱动**：默认从 `flowllm/config/default.yaml` 启动，支持配置文件和 dot notation 覆盖。
- **统一链路**：`CLI / Client -> Service -> Application -> Job -> Step -> Component`。
- **多种 Job 形态**：支持同步、流式、后台和定时任务，并可通过 HTTP 或 MCP 暴露。
- **可插拔组件**：通过注册表 `R` 扩展 Step、Service、Client、LLM、Embedding、Embedding Store 和 Agent Wrapper。

<p align="center">
  <img src="docs/figure/flowllm-architecture.svg" alt="FlowLLM Architecture" width="92%">
</p>

## 🚀 快速开始

### 安装

FlowLLM 要求 Python 3.11+。

从 pip 安装：

```bash
pip install flowllm
```

从源码安装：

```bash
git clone https://github.com/flowllm-ai/flowllm.git
cd flowllm
pip install -e .
```

### 启动服务

```bash
flowllm start
```

默认服务地址是 `127.0.0.1:2333`，默认 workspace 是 `.flowllm/`。可以用 dot notation 覆盖配置：

```bash
flowllm start service.port=8181 enable_logo=false
flowllm start workspace_dir=/tmp/flowllm-demo service.host=127.0.0.1 service.port=8181
```

更多启动和调用示例见 [快速开始](docs/zh/quick_start.md)。

## 🧩 使用 FlowLLM

```bash
flowllm version
flowllm health_check
flowllm help
flowllm demo query="Hello FlowLLM" min_score=0.8
flowllm add a=1 b=2
```

CLI 的非 `start` 命令会调用服务端同名 Job。HTTP 入口是 `POST /<job_name>`：

```bash
curl -s http://127.0.0.1:2333/add \
  -H 'Content-Type: application/json' \
  -d '{"a":1,"b":2}'
```

服务、CLI、HTTP 和流式调用示例见 [快速开始](docs/zh/quick_start.md)。

## ⚙️ 构建应用

FlowLLM 应用可以从 `flowllm/config/default.yaml` 或你自己的 YAML/JSON 配置启动。新增能力时，注册 Step 或
Component，再把它暴露成 Job：

```yaml
jobs:
  reverse:
    backend: base
    description: "reverse text"
    steps:
      - backend: reverse_step
```

配置支持 `.env`、`${VAR}`、`${VAR:-default}`、dot notation 覆盖和直接指定配置文件：

```bash
flowllm start config=/path/to/app.yaml
```

具体实现规则和示例优先看 [FlowLLM 开发 Skill](skills/flowllm_dev/SKILL.md)
。简版架构说明见 [代码框架](docs/zh/framework.md)。

## 🆕 极简 CLI Flow

对于不需要完整服务框架的脚本，`flowllm.lite` 可以把 `fl --action --field value` 映射到 Pydantic config 和顺序执行的
`BaseFlow`。见 [FlowLLM Lite](flowllm/lite/README.md)。

## 🗺️ Roadmap

| 项目               | 说明                                                                       |
|------------------|--------------------------------------------------------------------------|
| Agent wrapper 集成 | 将 FlowLLM 集成到 Agent wrapper 中，让 Agent 可以根据你的想法自动开发 FlowLLM 的 Step 和 Job。 |
| TypeScript 前端    | 增加 TypeScript 前端，支持通过前端界面开发 FlowLLM 应用。                                  |

## 📚 文档

- [快速开始](docs/zh/quick_start.md)
- [代码框架](docs/zh/framework.md)
- [开源与贡献](docs/zh/contributing.md)
- [FlowLLM 开发 Skill](skills/flowllm_dev/SKILL.md)

## 🤝 开源与贡献

FlowLLM 使用 Apache 2.0 许可证。贡献前请阅读 [贡献指南](docs/zh/contributing.md)
和 [开发 Skill](skills/flowllm_dev/SKILL.md)。

从源码安装开发依赖：

```bash
pip install -e ".[dev]"
```

提交改动前请尽量运行：

```bash
pre-commit run --all-files
pytest
```

## 📄 License

This project is open source under the Apache License 2.0. See [LICENSE](./LICENSE) for details.

## ⭐ Star 历史

[![Star History Chart](https://api.star-history.com/svg?repos=flowllm-ai/flowllm&type=Date)](https://www.star-history.com/#flowllm-ai/flowllm&Date)
