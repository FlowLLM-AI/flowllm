# 安装指南

本文介绍如何安装和配置 FlowLLM。

---

## 一、从 PyPI 安装（推荐）

使用 pip 从 PyPI 安装 FlowLLM：

```bash
pip install flowllm
```

---

## 二、从源码安装

如果你想从源码安装或参与开发，可以按以下步骤操作：

### 1. 克隆仓库

```bash
git clone https://github.com/flowllm-ai/flowllm.git
cd flowllm
```

### 2. 安装依赖

```bash
# 安装基础版本
pip install .

# 或安装开发版本（包含开发依赖）
pip install -e ".[dev]"
```

### 3. 验证安装

安装完成后，可以通过以下命令验证：

```bash
# 检查版本
python -c "import flowllm; print(flowllm.__version__)"

# 查看帮助信息
flowllm --help
```

---

## 三、环境配置

FlowLLM 使用环境变量进行配置。你需要创建一个 `.env` 文件来设置必要的参数。

### 1. 创建环境配置文件

将项目根目录下的 `example.env` 复制为 `.env`：

```bash
cp example.env .env
```

### 2. 配置环境变量

编辑 `.env` 文件，填入你的配置信息：

```bash
# LLM API 配置（必需）
FLOW_LLM_API_KEY=sk-xxxx
FLOW_LLM_BASE_URL=https://xxxx/v1

# Embedding API 配置（必需）
FLOW_EMBEDDING_API_KEY=sk-xxxx
FLOW_EMBEDDING_BASE_URL=https://xxxx/v1
```

### 3. 环境变量说明

- **FLOW_LLM_API_KEY**: LLM API 的密钥
- **FLOW_LLM_BASE_URL**: LLM API 的基础 URL（OpenAI 兼容格式）
- **FLOW_EMBEDDING_API_KEY**: Embedding API 的密钥
- **FLOW_EMBEDDING_BASE_URL**: Embedding API 的基础 URL

### 4. 使用环境变量

FlowLLM 会自动读取项目根目录下的 `.env` 文件。如果 `.env` 文件不在项目根目录，可以手动导出环境变量：

```bash
export FLOW_LLM_API_KEY=your_api_key
export FLOW_LLM_BASE_URL=your_base_url
export FLOW_EMBEDDING_API_KEY=your_embedding_key
export FLOW_EMBEDDING_BASE_URL=your_embedding_url
```
