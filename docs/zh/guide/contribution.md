# 贡献到 FlowLLM

## 欢迎！🎉

感谢对 FlowLLM 项目的关注和支持。我们欢迎并鼓励来自社区的贡献，无论是修复错误、添加新功能、改进文档还是分享想法。

## 如何贡献

### 1. 检查现有计划和问题

在开始贡献之前，请查看：
- **查看 [Issues](https://github.com/flowllm-ai/flowllm/issues)** 了解现有的开发任务
- **如果存在相关问题**：请在 issue 下评论，表达您的参与意愿
- **如果不存在相关问题**：请创建新 issue 描述您的更改或功能

### 2. 提交信息格式

FlowLLM 遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

**格式：**
```
<type>(<scope>): <subject>
```

**类型：**
- `feat:` 新功能
- `fix:` 错误修复
- `docs:` 仅文档更改
- `style:` 不影响代码含义的更改
- `refactor:` 代码重构
- `perf:` 性能优化
- `test:` 测试相关
- `chore:` 构建或工具更改

**示例：**
```bash
feat(op): add new async tool op
fix(flow): resolve context sharing issue
docs(guide): update flow configuration guide
```

### 3. 代码开发指南

#### a. 提交前检查

安装并运行 pre-commit 钩子：

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

#### b. 关于代码中的 Import

FlowLLM 遵循**懒加载导入原则**：

- **推荐做法**：仅在实际使用时导入模块
  ```python
  def some_function():
      import openai
      # 在此处使用 openai 库
  ```

#### c. 单元测试

- 所有新功能都应包含适当的单元测试
- 提交 PR 前确保现有测试通过
- 运行测试：`pytest tests`

#### d. 文档

- 为新功能更新相关文档
- 在适当的地方包含代码示例
- 如果更改影响用户功能，请更新 README.md

## 贡献类型

### 添加新的 Op

FlowLLM 的核心是 Op（算子）体系。添加新 Op 时：

1. **选择合适的基类**：
   - `BaseOp`：基础同步/异步 Op
   - `BaseAsyncOp`：异步 Op（推荐）
   - `BaseAsyncToolOp`：工具调用 Op
   - `BaseMcpOp`：MCP 工具 Op
   - `BaseRayOp`：分布式并行 Op

2. **实现位置**：
   - **核心 Op**：放在 `flowllm/core/op/` 目录
   - **示例 Op**：放在 `flowllm/gallery/` 目录
   - **扩展 Op**：放在 `flowllm/extension/` 目录

3. **实现要求**：
   - 实现 `execute()`（同步）或 `async_execute()`（异步）方法
   - 遵循 Op 组合规范（支持 `>>`、`|` 运算符）
   - 提供清晰的文档和示例

### 添加新的示例

请将示例添加到 `flowllm/gallery/` 目录，并附上清晰的注释说明。

示例结构：
```
flowllm/gallery/
└── your_op.py  # Op 实现
    └── your_prompt.yaml  # 可选的提示词配置
```

### 添加新的服务类型

如需添加新的服务类型（如新的协议支持），请：
1. 在 `flowllm/core/service/` 下实现 `BaseService` 的子类
2. 更新配置解析逻辑
3. 添加相应的文档和示例

## Do's and Don'ts

### ✅ DO

- **从小处着手**：从小的、可管理的贡献开始
- **及早沟通**：在实现主要功能之前进行讨论
- **编写测试**：确保代码经过充分测试
- **添加代码注释**：帮助他人理解贡献内容
- **遵循提交约定**：使用约定式提交消息
- **保持尊重**：遵守我们的行为准则

### ❌ DON'T

- **不要用大型 PR 让我们措手不及**：大型 PR 难以审查，请先开启 issue 讨论
- **不要忽略 CI 失败**：修复持续集成标记的任何问题
- **不要混合关注点**：保持 PR 专注于单一功能的实现或修复
- **不要忘记更新测试**：功能的更改应反映在测试中
- **不要破坏现有 API**：在可能的情况下保持向后兼容性
- **不要添加不必要的依赖项**：保持核心库轻量级
- **不要绕过懒加载导入原则**：确保 FlowLLM 在导入阶段不至于臃肿

## 获取帮助

如果需要帮助或有疑问：

- 💬 开启一个 [Discussion](https://github.com/flowllm-ai/flowllm/discussions)
- 🐛 通过 [Issues](https://github.com/flowllm-ai/flowllm/issues) 报告错误
- 📧 联系开发团队（链接在 README.md 中）

---

感谢为 FlowLLM 做出贡献！🚀

