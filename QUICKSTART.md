# 🚀 Quick Start Guide

## 30-Second Setup

```bash
# Install
pip install flowllm

# Set environment variables
export FLOW_LLM_API_KEY=sk-xxx
export FLOW_LLM_BASE_URL=https://api.openai.com/v1

# Start HTTP service (includes pre-built flows)
flowllm backend=http http.port=8002

# Or start MCP service
flowllm backend=mcp mcp.transport=stdio
```

That's it! Pre-built flows are now available as HTTP endpoints or MCP tools.

## Using Pre-built Services

```bash
# Use built-in LLM flow
curl -X POST http://localhost:8002/llm_flow \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'

# With streaming
curl -X POST http://localhost:8002/llm_flow_stream \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Tell me a story"}]}'
```

## Creating Your First Custom Service

### Step 1: Write an Operation (Python)

```python
# my_ops.py
from flowllm import BaseOp, C

class SummarizeOp(BaseOp):
    """Summarize text using LLM"""
    def call(self, text: str, max_length: int = 100) -> dict:
        llm = C.get_llm("default")
        prompt = f"Summarize this in {max_length} words: {text}"
        summary = llm.call(messages=[{"role": "user", "content": prompt}])
        return {"summary": summary}
```

### Step 2: Configure as Service (YAML)

```yaml
# my_config.yaml
import_config: default

backend: http
http:
  port: 8002

op:
  summarize_op:
    backend: base_op
    class: SummarizeOp

flow:
  summarize:
    description: "Summarize long text into concise format"
    flow_content: summarize_op
    tool:
      parameters:
        text:
          type: string
          description: "Text to summarize"
          required: true
        max_length:
          type: integer
          description: "Maximum summary length in words"
          required: false
          default: 100
```

### Step 3: Launch

```bash
flowllm config=my_config
```

### Step 4: Use

```bash
# HTTP endpoint automatically created
curl -X POST http://localhost:8002/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Long article text here...",
    "max_length": 50
  }'
```

**No FastAPI routes, no manual validation, no extra code - just configuration!**

## Using HTTP Client

### Python Requests

```python
import requests

# Execute a flow
response = requests.post("http://localhost:8002/my_custom_flow", json={
    "input_text": "Hello, FlowLLM!"
})

print(response.json())
```

### curl

```bash
curl -X POST http://localhost:8002/my_custom_flow \
  -H "Content-Type: application/json" \
  -d '{
    "input_text": "Hello, FlowLLM!"
  }'
```

### Node.js

```javascript
fetch("http://localhost:8002/my_custom_flow", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    input_text: "Hello, FlowLLM!"
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

## Using Python Client

### Synchronous Execution

```python
from flowllm import FlowLLMApp

# Initialize app
with FlowLLMApp(load_default_config=True) as app:
    # Execute flow synchronously
    result = app.execute_flow(
        "my_custom_flow",
        input_text="Hello, FlowLLM!"
    )
    print(result)
```

### Async Usage

```python
import asyncio
from flowllm import FlowLLMApp

async def main():
    async with FlowLLMApp(load_default_config=True) as app:
        # Execute flow asynchronously
        result = await app.async_execute_flow(
            "my_custom_flow",
            input_text="Hello, FlowLLM!"
        )
        print(result)

asyncio.run(main())
```

## Next Steps

- **Learn More**: Check out the [Configuration-Driven Development](README.md#-configuration-driven-development) section
- **Explore Examples**: See the [Example Workflows](README.md#-example-workflows) section
- **Advanced Features**: Read about [Core Features](README.md#-core-features)
- **Deep Dive**: Browse the [documentation](doc/) directory for detailed guides
- **Build**: Follow the complete example in [Configuration-Driven Development](README.md#-configuration-driven-development)

## Common Patterns

### Simple LLM Chat

```python
from flowllm import BaseOp, FlowLLMApp, C

class ChatOp(BaseOp):
    def call(self, message: str) -> dict:
        llm = C.get_llm("default")
        response = llm.call(messages=[
            {"role": "user", "content": message}
        ])
        return {"response": response}

with FlowLLMApp(load_default_config=True) as app:
    result = app.execute_flow("chat", message="Hello!")
    print(result)
```

### Sequential Workflow

```yaml
flow:
  research_flow:
    description: "Multi-step research workflow"
    flow_content: "search_op >> summarize_op >> validate_op"
```

### Parallel Processing

```yaml
flow:
  parallel_analysis:
    description: "Analyze from multiple perspectives"
    flow_content: "(sentiment_op | keywords_op | summary_op)"
```

## Getting Help

- **Documentation**: [doc/](doc/) directory
- **Issues**: [GitHub Issues](https://github.com/your-org/flowllm/issues)
- **Email**: jinli.yl@alibaba-inc.com

