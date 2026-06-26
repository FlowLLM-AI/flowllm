# 开源与贡献

FlowLLM 仓库：**https://github.com/flowllm-ai/flowllm**

第一次本地运行请看 [快速开始](./quick_start.md)。修改运行时、Job、Step、组件、服务或配置前，请先看 [代码框架](./framework.md)。

## 本地开发

FlowLLM 要求 Python 3.11+。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

需要完整可选依赖时：

```bash
pip install -e ".[full]"
```

主要目录：

| 路径                            | 说明            |
|-------------------------------|---------------|
| `flowllm/`                    | Python 包源码    |
| `flowllm/config/default.yaml` | 默认配置          |
| `flowllm/components/`         | 服务、客户端、Job、组件 |
| `flowllm/steps/`              | Step 实现       |
| `flowllm/schema/`             | 请求、响应和配置模型    |
| `tests/`                      | 单元和集成测试       |
| `docs/zh/`                    | 中文文档          |

## 开发约定

遵循主链路：

```text
CLI / Client -> Service -> Application -> Job -> Step -> Component
```

- 对外能力优先做成 Job，再由 HTTP 或 MCP Service 暴露。
- 可复用基础设施放在 `flowllm/components/`，继承 `BaseComponent`。
- 业务原子操作放在 `flowllm/steps/`，继承 `BaseStep`。
- 新实现用 `@R.register("<backend_name>")` 注册，并确保模块被 `__init__.py` import。
- 默认行为写入 `flowllm/config/default.yaml`，保持 `flowllm start` 可运行。
- 修改用户可见行为时同步更新文档。

## 测试

提交前建议运行：

```bash
pre-commit run --all-files
pytest
```

局部验证可以先跑：

```bash
pytest tests/unit
pytest tests/integration
```

测试建议：

- 修 Bug 时补回归测试。
- 新增 Step、Job 或组件时覆盖核心路径和失败路径。
- 修改配置解析、注册表、生命周期、服务暴露或流式输出时覆盖用户入口。
- 依赖 LLM、embedding 或外部服务的测试，请在 PR 中说明所需环境。

## 提交与 PR

建议使用 Conventional Commits：

```text
<type>(<scope>): <subject>
```

常用类型：`feat`、`fix`、`docs`、`test`、`refactor`、`chore`、`perf`、`style`。

示例：

```text
feat(step): add reverse text demo
fix(config): preserve leading zero strings
docs(zh): update quick start
test(service): cover stream response
```

PR 标题也建议使用同样格式。较大改动请先在 Issue 中说明背景、目标行为、影响范围和测试计划。
