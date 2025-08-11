# Configuration Guide

This guide provides comprehensive information about configuring flowllm applications, including pipeline definitions, component settings, and environment variables.

## Table of Contents

- [Configuration Overview](#configuration-overview)
- [Configuration File Structure](#configuration-file-structure)
- [Pipeline Configuration](#pipeline-configuration)
- [Component Configuration](#component-configuration)
- [Environment Variables](#environment-variables)
- [Advanced Configuration](#advanced-configuration)
- [Configuration Examples](#configuration-examples)
- [Troubleshooting](#troubleshooting)

## Configuration Overview

flowllm uses a hierarchical configuration system that supports:

- **YAML Configuration Files**: Primary configuration method
- **Command Line Arguments**: Override configuration values
- **Environment Variables**: Secure credential management
- **Runtime Configuration**: Dynamic configuration updates

### Configuration Priority

Configuration values are resolved in the following order (highest to lowest priority):

1. Command line arguments
2. Runtime configuration (request-level config)
3. YAML configuration files
4. Environment variables
5. Default values

## Configuration File Structure

### Basic Structure

```yaml
# HTTP Service Configuration
http_service:
  host: "0.0.0.0"
  port: 8001
  timeout_keep_alive: 600
  limit_concurrency: 64

# Thread Pool Configuration
thread_pool:
  max_workers: 10

# API Pipeline Definitions
api:
  retriever: recall_vector_store_op
  summarizer: update_vector_store_op
  vector_store: vector_store_action_op
  agent: react_v1_op

# Operation Definitions
op:
  operation_name:
    backend: operation_type
    llm: llm_config_name
    vector_store: vector_store_config_name
    params: {}

# LLM Configurations
llm:
  config_name:
    backend: provider_type
    model_name: model_identifier
    params: {}

# Embedding Model Configurations
embedding_model:
  config_name:
    backend: provider_type
    model_name: model_identifier
    params: {}

# Vector Store Configurations
vector_store:
  config_name:
    backend: storage_type
    embedding_model: embedding_config_name
    params: {}
```

## Pipeline Configuration

### Pipeline Syntax

flowllm uses an intuitive string-based syntax for defining operation pipelines:

#### Serial Execution
Operations execute sequentially, one after another:
```yaml
api:
  retriever: op1->op2->op3
```

#### Parallel Execution
Operations within brackets execute simultaneously:
```yaml
api:
  summarizer: op1->[op2|op3]->op4
```

#### Complex Pipelines
Combine serial and parallel execution:
```yaml
api:
  agent: op1->[op2->op3|op4->op5]->[op6|op7]
```

### Pipeline Examples

**Simple Retrieval Pipeline:**
```yaml
api:
  retriever: recall_vector_store_op->summarizer_op
```

**Complex Agent Pipeline:**
```yaml
api:
  agent: react_v1_op->[search_op|code_op]->summarizer_op
```

**Parallel Processing Pipeline:**
```yaml
api:
  summarizer: [embedding_op|preprocessing_op]->llm_op->postprocessing_op
```

## Component Configuration

### HTTP Service Configuration

```yaml
http_service:
  host: "0.0.0.0"              # Server host address
  port: 8001                   # Server port
  timeout_keep_alive: 600      # Keep-alive timeout in seconds
  limit_concurrency: 64        # Maximum concurrent connections
```

### Thread Pool Configuration

```yaml
thread_pool:
  max_workers: 10              # Maximum number of worker threads
```

### MCP Configuration

```yaml
mcp_transport: "stdio"         # MCP transport method: "stdio" or "sse"
```

## LLM Configuration

### OpenAI Compatible LLMs

```yaml
llm:
  default:
    backend: openai_compatible
    model_name: "gpt-4"
    params:
      temperature: 0.7
      max_retries: 5
      top_p: 0.9
      presence_penalty: 0.0
      seed: 42
      enable_thinking: true
      tool_choice: "auto"
      parallel_tool_calls: true
      raise_exception: false
      stream_options:
        include_usage: true
```

### Multiple LLM Configurations

```yaml
llm:
  fast_model:
    backend: openai_compatible
    model_name: "gpt-3.5-turbo"
    params:
      temperature: 0.3
      
  reasoning_model:
    backend: openai_compatible
    model_name: "gpt-4"
    params:
      temperature: 0.1
      enable_thinking: true
      
  creative_model:
    backend: openai_compatible
    model_name: "gpt-4"
    params:
      temperature: 0.9
      top_p: 0.95
```

## Embedding Model Configuration

### OpenAI Compatible Embeddings

```yaml
embedding_model:
  default:
    backend: openai_compatible
    model_name: "text-embedding-3-large"
    params:
      dimensions: 1024
      
  small_model:
    backend: openai_compatible
    model_name: "text-embedding-3-small"
    params:
      dimensions: 512
```

## Vector Store Configuration

### Local File Storage

```yaml
vector_store:
  default:
    backend: local_file
    embedding_model: default
    params:
      store_dir: "./vector_store_data"
      batch_size: 1024
```

### Elasticsearch

```yaml
vector_store:
  elasticsearch:
    backend: elasticsearch
    embedding_model: default
    params:
      hosts: ["http://localhost:9200"]
      basic_auth: null
      retrieve_filters: []
      batch_size: 1000
```

### ChromaDB

```yaml
vector_store:
  chroma:
    backend: chroma
    embedding_model: default
    params:
      persist_directory: "./chroma_db"
      collection_name: "default_collection"
      batch_size: 1000
```

## Operation Configuration

### ReAct Agent Operation

```yaml
op:
  react_v1_op:
    backend: react_v1_op
    llm: default
    vector_store: default
    params:
      max_steps: 10
      tool_names: "code_tool,tavily_search_tool,terminate_tool"
    prompt_dict:
      role_prompt: |
        You are a helpful assistant.
        Current time: {time}
        Available tools: {tools}
        
        User query: {query}
```

### Vector Store Operations

```yaml
op:
  recall_vector_store_op:
    backend: recall_vector_store_op
    vector_store: default
    params:
      default_top_k: 5
      
  update_vector_store_op:
    backend: update_vector_store_op
    vector_store: default
    params:
      batch_size: 100
      
  vector_store_action_op:
    backend: vector_store_action_op
    vector_store: default
    params:
      supported_actions: ["copy", "delete", "dump", "load"]
```

### Custom Operation

```yaml
op:
  custom_op:
    backend: custom_op
    llm: reasoning_model
    vector_store: elasticsearch
    prompt_file_path: "./prompts/custom_prompt.yaml"
    params:
      custom_param1: "value1"
      custom_param2: 42
      custom_param3: true
```

## Environment Variables

### Required Variables

```bash
# LLM Configuration
LLM_API_KEY=sk-your-llm-api-key
LLM_BASE_URL=https://your-llm-endpoint/v1

# Embedding Model Configuration
EMBEDDING_API_KEY=sk-your-embedding-api-key
EMBEDDING_BASE_URL=https://your-embedding-endpoint/v1
```

### Optional Variables

```bash
# Elasticsearch
ES_HOSTS=http://localhost:9200

# Search Tools
DASHSCOPE_API_KEY=sk-your-dashscope-key
TAVILY_API_KEY=your-tavily-key

# OpenAI (if using OpenAI directly)
OPENAI_API_KEY=sk-your-openai-key
OPENAI_BASE_URL=https://api.openai.com/v1
```

### Environment Variable Loading

flowllm automatically loads environment variables from:
1. System environment
2. `.env` file in the current directory
3. `.env` file in the project root

## Advanced Configuration

### Dynamic Configuration

Override configuration at runtime using request-level config:

```python
response = requests.post('http://localhost:8001/agent', json={
    "query": "What is AI?",
    "config": {
        "llm": {
            "default": {
                "params": {
                    "temperature": 0.9
                }
            }
        }
    }
})
```

### Command Line Configuration

Override any configuration value from the command line:

```bash
flowllm \
  http_service.port=8002 \
  llm.default.model_name=gpt-4 \
  llm.default.params.temperature=0.5 \
  vector_store.default.backend=elasticsearch \
  vector_store.default.params.hosts="http://localhost:9200"
```

### Prompt Customization

#### Inline Prompt Configuration

```yaml
op:
  react_v1_op:
    backend: react_v1_op
    llm: default
    prompt_dict:
      role_prompt: |
        You are a specialized assistant for {domain}.
        Current time: {time}
        Available tools: {tools}
        
        Please help with: {query}
      
      next_prompt: |
        Based on the context, determine if you need more information.
        If yes, use appropriate tools.
        If no, use the terminate tool.
```

#### External Prompt Files

```yaml
op:
  custom_op:
    backend: custom_op
    prompt_file_path: "./prompts/custom_prompts.yaml"
```

**prompts/custom_prompts.yaml:**
```yaml
system_prompt: |
  You are an expert in {field}.
  Current context: {context}

user_prompt: |
  Please analyze: {query}

follow_up_prompt: |
  Based on your analysis, provide recommendations.
```

### Multi-Environment Configuration

#### Development Configuration

```yaml
# config/dev.yaml
http_service:
  host: "127.0.0.1"
  port: 8001

llm:
  default:
    model_name: "gpt-3.5-turbo"
    params:
      temperature: 0.7

vector_store:
  default:
    backend: local_file
```

#### Production Configuration

```yaml
# config/prod.yaml
http_service:
  host: "0.0.0.0"
  port: 8080
  limit_concurrency: 128

llm:
  default:
    model_name: "gpt-4"
    params:
      temperature: 0.3
      max_retries: 10

vector_store:
  default:
    backend: elasticsearch
    params:
      hosts: ["http://es-cluster:9200"]
```

## Configuration Examples

### Complete RAG System

```yaml
http_service:
  host: "0.0.0.0"
  port: 8001

thread_pool:
  max_workers: 20

api:
  retriever: recall_vector_store_op
  summarizer: update_vector_store_op
  agent: react_v1_op->[recall_vector_store_op|tavily_search_op]->summarizer_op

op:
  recall_vector_store_op:
    backend: recall_vector_store_op
    vector_store: knowledge_base
    params:
      default_top_k: 10
      
  update_vector_store_op:
    backend: update_vector_store_op
    vector_store: knowledge_base
    llm: summarizer_llm
    
  react_v1_op:
    backend: react_v1_op
    llm: agent_llm
    params:
      max_steps: 15
      tool_names: "code_tool,tavily_search_tool,terminate_tool"

llm:
  agent_llm:
    backend: openai_compatible
    model_name: "gpt-4"
    params:
      temperature: 0.2
      
  summarizer_llm:
    backend: openai_compatible
    model_name: "gpt-3.5-turbo"
    params:
      temperature: 0.1

embedding_model:
  default:
    backend: openai_compatible
    model_name: "text-embedding-3-large"
    params:
      dimensions: 1536

vector_store:
  knowledge_base:
    backend: elasticsearch
    embedding_model: default
    params:
      hosts: ["http://localhost:9200"]
      batch_size: 1000
```

### Multi-Agent System

```yaml
api:
  research_agent: research_op->[web_search_op|paper_search_op]->synthesis_op
  coding_agent: code_analysis_op->code_generation_op->code_review_op
  writing_agent: outline_op->draft_op->review_op->polish_op

op:
  research_op:
    backend: react_v1_op
    llm: research_llm
    params:
      tool_names: "tavily_search_tool,terminate_tool"
      
  coding_agent:
    backend: react_v1_op
    llm: coding_llm
    params:
      tool_names: "code_tool,terminate_tool"
      
  writing_agent:
    backend: react_v1_op
    llm: writing_llm
    params:
      tool_names: "terminate_tool"

llm:
  research_llm:
    backend: openai_compatible
    model_name: "gpt-4"
    params:
      temperature: 0.3
      
  coding_llm:
    backend: openai_compatible
    model_name: "gpt-4"
    params:
      temperature: 0.1
      
  writing_llm:
    backend: openai_compatible
    model_name: "gpt-4"
    params:
      temperature: 0.7
```

## Troubleshooting

### Common Configuration Issues

#### 1. Missing API Keys

**Error:**
```
ValueError: LLM_API_KEY environment variable is required
```

**Solution:**
```bash
export LLM_API_KEY=your-api-key
# or add to .env file
echo "LLM_API_KEY=your-api-key" >> .env
```

#### 2. Invalid Pipeline Syntax

**Error:**
```
RuntimeError: op=nonexistent_op config is missing!
```

**Solution:**
Ensure all operations in your pipeline are defined in the `op` section:
```yaml
api:
  retriever: existing_op->another_existing_op

op:
  existing_op:
    backend: recall_vector_store_op
  another_existing_op:
    backend: update_vector_store_op
```

#### 3. Backend Not Registered

**Error:**
```
AssertionError: backend=unknown_backend is not registered!
```

**Solution:**
Use only registered backends or implement custom ones:
```yaml
# Valid backends
llm:
  default:
    backend: openai_compatible  # ✓ Valid
    
vector_store:
  default:
    backend: local_file        # ✓ Valid
    # backend: elasticsearch   # ✓ Valid
    # backend: chroma         # ✓ Valid
```

#### 4. Configuration Validation Errors

**Error:**
```
ValidationError: embedding_model=nonexistent is not existed
```

**Solution:**
Ensure referenced configurations exist:
```yaml
vector_store:
  default:
    embedding_model: default  # Must exist in embedding_model section

embedding_model:
  default:  # ✓ Referenced configuration exists
    backend: openai_compatible
    model_name: "text-embedding-3-small"
```

### Configuration Validation

Use the built-in validation to check your configuration:

```bash
# Validate configuration
flowllm --validate-config

# Test specific configuration
flowllm --config-file=config/test.yaml --validate-config
```

### Debugging Configuration

Enable debug logging to see configuration resolution:

```bash
export LOG_LEVEL=DEBUG
flowllm http_service.port=8001
```

This will show how configuration values are resolved and merged.

For more information, see the [API Documentation](api.md) and [Operations Development](operations.md) guides.
