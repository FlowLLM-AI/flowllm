# 🔒 安全最佳实践

## 环境变量管理

本项目使用环境变量来管理敏感信息，如 API 密钥。**永远不要将真实的 API 密钥提交到版本控制系统中。**

### 设置环境变量

1. **创建 `.env` 文件**：
   ```bash
   cp env.example .env
   ```

2. **编辑 `.env` 文件**，填入真实的 API 密钥：
   ```bash
   VITE_API_KEY=sk-your-actual-api-key-here
   VITE_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
   VITE_MODEL=qwen-max
   ```

3. **验证 `.gitignore`**：
   确保 `.env` 文件在 `.gitignore` 中（已配置）：
   ```
   .env
   .env.local
   ```

### 环境变量说明

- `VITE_API_KEY`：LLM 服务的 API 密钥（必需）
- `VITE_API_BASE`：API 端点的基础 URL（可选，有默认值）
- `VITE_MODEL`：使用的模型名称（可选，有默认值）

### Vite 环境变量规则

- 只有以 `VITE_` 为前缀的环境变量才会暴露给客户端代码
- 通过 `import.meta.env.VITE_*` 访问环境变量
- 开发模式下从 `.env` 文件自动加载
- 生产构建时会将环境变量值内联到代码中

### 安全注意事项

1. ✅ **正确做法**：
   - 使用 `.env` 文件存储 API 密钥
   - 将 `.env` 添加到 `.gitignore`
   - 提供 `env.example` 作为模板
   - 定期轮换 API 密钥

2. ❌ **错误做法**：
   - 在代码中硬编码 API 密钥
   - 将 `.env` 文件提交到 Git
   - 在公开仓库中暴露真实密钥
   - 在日志或错误信息中打印密钥

### 团队协作

如果在团队中工作：

1. 每个开发者创建自己的 `.env` 文件
2. 通过安全渠道（如密码管理器）共享 API 密钥
3. 在 README 中记录需要哪些环境变量
4. 使用 `env.example` 作为参考模板

### CI/CD 配置

在持续集成/部署环境中：

1. 不要将 `.env` 文件上传到 CI/CD 服务器
2. 使用 CI/CD 平台的密钥管理功能
3. 通过环境变量或密钥存储注入配置

### 紧急响应

如果不小心泄露了 API 密钥：

1. **立即撤销**：在 API 提供商处撤销泄露的密钥
2. **生成新密钥**：创建新的 API 密钥
3. **更新配置**：更新本地 `.env` 文件
4. **清理历史**：如果提交到 Git，需要清理提交历史（使用 `git filter-branch` 或 BFG Repo-Cleaner）
5. **通知团队**：告知相关人员更新密钥

## 参考资源

- [Vite 环境变量文档](https://vitejs.dev/guide/env-and-mode.html)
- [GitHub 安全最佳实践](https://docs.github.com/en/code-security/getting-started/best-practices-for-preventing-data-leaks-in-your-organization)

