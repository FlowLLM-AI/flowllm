# 🛠️ Installation Guide

## Install from PyPI (Recommended)

```bash
pip install flowllm
```

## Install with Optional Dependencies

```bash
# For financial data support
pip install flowllm[fin]

# For distributed computing
pip install flowllm[dist]

# For Qwen model support
pip install flowllm[qwen]

# Install all features
pip install flowllm[all]
```

## Install from Source

```bash
git clone https://github.com/your-org/flowllm.git
cd flowllm
pip install .
```

## Environment Configuration

Copy `example.env` to `.env` and modify the corresponding parameters:

```bash
FLOW_APP_NAME=FlowLLM

# LLM Configuration
FLOW_LLM_API_KEY=sk-xxxx
FLOW_LLM_BASE_URL=https://xxxx/v1
FLOW_LLM_MODEL=qwen3-max

# Embedding Configuration
FLOW_EMBEDDING_API_KEY=sk-xxxx
FLOW_EMBEDDING_BASE_URL=https://xxxx/v1

# Optional: Elasticsearch
# FLOW_ES_HOSTS=http://0.0.0.0:9200

# Optional: Additional API Keys
# FLOW_DASHSCOPE_API_KEY=sk-xxxx
# FLOW_TAVILY_API_KEY=sk-xxxx
```

## Verify Installation

After installation, you can verify that FlowLLM is installed correctly:

```bash
# Check version
python -c "import flowllm; print(flowllm.__version__)"

# Run help command
flowllm --help
```

## Troubleshooting

### Common Issues

#### 1. Import Error

If you encounter import errors, make sure you have installed all required dependencies:

```bash
pip install -r requirements.txt
```

#### 2. Environment Variables Not Found

Ensure your `.env` file is in the correct location (project root) or export environment variables manually:

```bash
export FLOW_LLM_API_KEY=your_api_key
export FLOW_LLM_BASE_URL=your_base_url
```

#### 3. Port Already in Use

If the default port (8002) is already in use, specify a different port:

```bash
flowllm backend=http http.port=8003
```

## Next Steps

- Read the [Quick Start Guide](QUICKSTART.md) to get started
- Check out the [README](README.md) for architecture overview
- Explore the [documentation](doc/) for detailed guides

