# API Documentation

This document provides comprehensive information about LLMFlow's REST API endpoints and MCP server functionality.

## Table of Contents

- [HTTP API Endpoints](#http-api-endpoints)
  - [Retriever API](#retriever-api)
  - [Summarizer API](#summarizer-api)
  - [Vector Store API](#vector-store-api)
  - [Agent API](#agent-api)
- [MCP Server](#mcp-server)
- [Request/Response Schemas](#requestresponse-schemas)
- [Error Handling](#error-handling)
- [Authentication](#authentication)

## HTTP API Endpoints

LLMFlow provides a FastAPI-based HTTP service with multiple endpoints for different functionalities.

### Base URL

```
http://localhost:8001
```

### Retriever API

Retrieve relevant experiences from the vector store based on a query.

**Endpoint:** `POST /retriever`

**Request Body:**
```json
{
  "query": "What is artificial intelligence?",
  "messages": [
    {
      "role": "user",
      "content": "Previous context message"
    }
  ],
  "top_k": 5,
  "workspace_id": "default",
  "config": {
    "vector_store": {
      "default": {
        "params": {
          "retrieve_filters": []
        }
      }
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "experience_list": [
    {
      "workspace_id": "default",
      "content": "AI is a technology that simulates human intelligence...",
      "metadata": {
        "score": 0.95,
        "node_type": "document"
      },
      "node_id": "doc_123"
    }
  ],
  "metadata": {
    "processing_time": 0.245,
    "total_results": 5
  }
}
```

**Parameters:**
- `query` (string, required): The search query
- `messages` (array, optional): Context messages for better retrieval
- `top_k` (integer, optional, default: 1): Number of results to return
- `workspace_id` (string, optional, default: "default"): Workspace identifier
- `config` (object, optional): Additional configuration parameters

### Summarizer API

Summarize trajectories into structured experiences.

**Endpoint:** `POST /summarizer`

**Request Body:**
```json
{
  "traj_list": [
    {
      "role": "user",
      "content": "How do I implement a neural network?"
    },
    {
      "role": "assistant", 
      "content": "To implement a neural network, you need to..."
    }
  ],
  "workspace_id": "default",
  "config": {
    "llm": {
      "default": {
        "params": {
          "temperature": 0.3
        }
      }
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "experience_list": [
    {
      "workspace_id": "default",
      "content": "Neural network implementation guide: ...",
      "metadata": {
        "summary_type": "technical_guide",
        "confidence": 0.92
      },
      "node_id": "summary_456"
    }
  ],
  "metadata": {
    "processing_time": 1.23,
    "input_tokens": 150,
    "output_tokens": 75
  }
}
```

**Parameters:**
- `traj_list` (array, required): List of conversation trajectories
- `workspace_id` (string, optional, default: "default"): Workspace identifier
- `config` (object, optional): Configuration for summarization

### Vector Store API

Perform operations on vector stores (create, delete, copy, etc.).

**Endpoint:** `POST /vector_store`

**Request Body:**
```json
{
  "action": "copy",
  "src_workspace_id": "source_workspace",
  "workspace_id": "target_workspace", 
  "path": "./backup/",
  "config": {
    "vector_store": {
      "default": {
        "backend": "local_file"
      }
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "metadata": {
    "action": "copy",
    "result": "Successfully copied 150 nodes from source_workspace to target_workspace",
    "nodes_processed": 150,
    "processing_time": 2.1
  }
}
```

**Supported Actions:**
- `copy`: Copy workspace data
- `delete`: Delete workspace
- `dump`: Export workspace data
- `load`: Import workspace data
- `create`: Create new workspace

### Agent API

Execute ReAct-style agent workflows with tool calling capabilities.

**Endpoint:** `POST /agent`

**Request Body:**
```json
{
  "query": "Search for the latest AI research papers and summarize the key findings",
  "workspace_id": "default",
  "config": {
    "op": {
      "react_v1_op": {
        "params": {
          "max_steps": 10,
          "tool_names": "tavily_search_tool,code_tool,terminate_tool"
        }
      }
    }
  }
}
```

**Response:**
```json
{
  "success": true,
  "metadata": {
    "steps_taken": 5,
    "tools_used": ["tavily_search_tool", "terminate_tool"],
    "final_answer": "Based on my search, here are the key findings from recent AI research...",
    "processing_time": 15.7
  }
}
```

## MCP Server

LLMFlow also provides a Model Context Protocol (MCP) server for integration with MCP-compatible clients.

### Starting the MCP Server

```bash
llmflow_mcp \
  mcp_transport=stdio \
  llm.default.model_name=qwen3-32b \
  embedding_model.default.model_name=text-embedding-v4
```

### Available MCP Tools

#### retriever
Retrieve experiences from workspace.

**Parameters:**
- `query` (string): Search query
- `messages` (array, optional): Context messages
- `top_k` (integer, optional): Number of results
- `workspace_id` (string, optional): Workspace ID
- `config` (object, optional): Configuration

#### summarizer
Summarize conversation trajectories.

**Parameters:**
- `traj_list` (array): List of trajectories
- `workspace_id` (string, optional): Workspace ID
- `config` (object, optional): Configuration

#### vector_store
Perform vector store operations.

**Parameters:**
- `action` (string): Operation to perform
- `src_workspace_id` (string, optional): Source workspace
- `workspace_id` (string, optional): Target workspace
- `path` (string, optional): File path
- `config` (object, optional): Configuration

## Request/Response Schemas

### Base Request Schema

All API requests inherit from a base schema:

```json
{
  "workspace_id": "string (optional, default: 'default')",
  "config": "object (optional, default: {})"
}
```

### Base Response Schema

All API responses follow this structure:

```json
{
  "success": "boolean",
  "metadata": "object",
  "experience_list": "array (optional)"
}
```

### Message Schema

Messages in trajectories follow this format:

```json
{
  "role": "user|assistant|system",
  "content": "string",
  "tool_calls": "array (optional)",
  "reasoning_content": "string (optional)"
}
```

### Experience Schema

Experiences returned from operations:

```json
{
  "workspace_id": "string",
  "content": "string", 
  "metadata": "object",
  "node_id": "string",
  "vector": "array (optional)"
}
```

## Error Handling

### Error Response Format

```json
{
  "success": false,
  "metadata": {
    "error": "Error description",
    "error_type": "ValidationError|RuntimeError|TimeoutError",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

### Common Error Codes

- **400 Bad Request**: Invalid request parameters
- **404 Not Found**: Workspace or resource not found
- **500 Internal Server Error**: Server processing error
- **503 Service Unavailable**: Service temporarily unavailable

### Error Examples

**Invalid Configuration:**
```json
{
  "success": false,
  "metadata": {
    "error": "llm.default.model_name is required",
    "error_type": "ValidationError"
  }
}
```

**Workspace Not Found:**
```json
{
  "success": false,
  "metadata": {
    "error": "Workspace 'nonexistent' not found",
    "error_type": "RuntimeError"
  }
}
```

## Authentication

Currently, LLMFlow uses API key-based authentication configured through environment variables:

```bash
# LLM Provider Authentication
LLM_API_KEY=your-llm-api-key
LLM_BASE_URL=https://your-llm-endpoint/v1

# Embedding Model Authentication  
EMBEDDING_API_KEY=your-embedding-api-key
EMBEDDING_BASE_URL=https://your-embedding-endpoint/v1

# Search Tool Authentication
DASHSCOPE_API_KEY=your-dashscope-key
```

## Rate Limiting

The HTTP service includes built-in rate limiting:

- **Concurrency Limit**: Configurable via `http_service.limit_concurrency`
- **Timeout**: Configurable via `http_service.timeout_keep_alive`
- **Thread Pool**: Configurable via `thread_pool.max_workers`

## Client Examples

### Python Client

```python
import requests

class LLMFlowClient:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
    
    def retrieve(self, query, workspace_id="default", top_k=5):
        response = requests.post(f"{self.base_url}/retriever", json={
            "query": query,
            "workspace_id": workspace_id,
            "top_k": top_k
        })
        return response.json()
    
    def summarize(self, traj_list, workspace_id="default"):
        response = requests.post(f"{self.base_url}/summarizer", json={
            "traj_list": traj_list,
            "workspace_id": workspace_id
        })
        return response.json()
    
    def agent_query(self, query, workspace_id="default"):
        response = requests.post(f"{self.base_url}/agent", json={
            "query": query,
            "workspace_id": workspace_id
        })
        return response.json()

# Usage
client = LLMFlowClient()
result = client.retrieve("What is machine learning?")
print(result)
```

### cURL Examples

**Retriever:**
```bash
curl -X POST http://localhost:8001/retriever \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is AI?",
    "top_k": 3,
    "workspace_id": "default"
  }'
```

**Agent:**
```bash
curl -X POST http://localhost:8001/agent \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Help me understand neural networks",
    "workspace_id": "default"
  }'
```

## Performance Considerations

- **Streaming**: LLM responses support streaming for better user experience
- **Parallel Processing**: Operations can be executed in parallel where configured
- **Caching**: Vector stores support caching for improved performance
- **Batch Processing**: Vector operations support batch processing for efficiency

For more detailed information, see the [Configuration Guide](configuration.md) and [Operations Development](operations.md) documentation.
