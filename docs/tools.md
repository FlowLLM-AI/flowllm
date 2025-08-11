# Tools Development Guide

This guide covers how to develop custom tools in LLMFlow, including understanding the tool system, implementing tool functionality, and integrating with LLM operations.

## Table of Contents

- [Tool Overview](#tool-overview)
- [Base Tool Class](#base-tool-class)
- [Built-in Tools](#built-in-tools)
- [Creating Custom Tools](#creating-custom-tools)
- [Tool Integration](#tool-integration)
- [Advanced Features](#advanced-features)
- [Testing Tools](#testing-tools)
- [Best Practices](#best-practices)

## Tool Overview

Tools in LLMFlow are callable functions that LLMs can use to interact with external systems, execute code, search the web, or perform other tasks. They provide a standardized interface for extending LLM capabilities.

### Tool Architecture

```
┌─────────────────┐
│      LLM        │
│   (decides to   │
│   use tools)    │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  Tool Registry  │
│   (manages      │
│   available     │
│   tools)        │
└─────────────────┘
         │
         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Code Tool     │    │  Search Tool    │    │  Custom Tool    │
│                 │    │                 │    │                 │
│ • Execute code  │    │ • Web search    │    │ • Your logic    │
│ • Return result │    │ • Return info   │    │ • Return data   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Tool Characteristics

- **Stateless**: Tools should be stateless and idempotent when possible
- **Error Handling**: Robust error handling with retries and graceful failures
- **Caching**: Optional result caching for expensive operations
- **Validation**: Input parameter validation and sanitization
- **Documentation**: Clear descriptions and parameter schemas

## Base Tool Class

All tools inherit from `BaseTool`, which provides core functionality:

```python
from llmflow.tool.base_tool import BaseTool
from llmflow.tool import TOOL_REGISTRY

@TOOL_REGISTRY.register()
class CustomTool(BaseTool):
    name: str = "custom_tool"
    description: str = "Tool description"
    parameters: dict = {
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "Parameter description"}
        },
        "required": ["param"]
    }
    
    def _execute(self, param: str, **kwargs):
        # Your tool logic here
        return f"Result: {param}"
```

### BaseTool Properties

```python
class BaseTool(BaseModel):
    # Tool identification
    tool_id: str = ""
    name: str                          # Tool name (required)
    description: str                   # Tool description (required)
    tool_type: str = "function"        # Tool type
    
    # Schema definition
    parameters: dict                   # JSON schema for parameters
    arguments: dict = {}               # Runtime arguments
    
    # Caching
    enable_cache: bool = False         # Enable result caching
    cached_result: dict = {}           # Cached results
    
    # Error handling
    max_retries: int = 3               # Maximum retry attempts
    raise_exception: bool = True       # Whether to raise exceptions
    success: bool = True               # Execution success status
```

### BaseTool Methods

```python
# Abstract method - must be implemented
def _execute(self, **kwargs):
    """Core tool execution logic"""
    raise NotImplementedError

# Public execution method (handles retries, caching, etc.)
def execute(self, **kwargs):
    """Execute tool with error handling and caching"""
    
# Utility methods
def reset(self):
    """Reset tool state"""
    
def get_cache_id(self, **kwargs) -> str:
    """Generate cache ID for parameters"""
    
def simple_dump(self) -> dict:
    """Export tool configuration"""
```

## Built-in Tools

### Code Tool

Executes Python code in a sandboxed environment:

```python
@TOOL_REGISTRY.register()
class CodeTool(BaseTool):
    name: str = "python_execute"
    description: str = "Execute python code for analysis or calculation"
    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute"
            }
        },
        "required": ["code"]
    }
    
    def _execute(self, code: str, **kwargs):
        old_stdout = sys.stdout
        redirected_output = sys.stdout = StringIO()
        
        try:
            exec(code)
            result = redirected_output.getvalue()
        except Exception as e:
            self.success = False
            result = str(e)
        finally:
            sys.stdout = old_stdout
        
        return result
```

### Search Tools

#### Tavily Search Tool

```python
@TOOL_REGISTRY.register()
class TavilySearchTool(BaseTool):
    name: str = "tavily_search"
    description: str = "Search the web using Tavily API"
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Maximum results", "default": 5}
        },
        "required": ["query"]
    }
    
    def _execute(self, query: str, max_results: int = 5, **kwargs):
        # Implementation using Tavily API
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = client.search(query=query, max_results=max_results)
        return response
```

#### DashScope Search Tool

```python
@TOOL_REGISTRY.register()
class DashscopeSearchTool(BaseTool):
    name: str = "dashscope_search"
    description: str = "Search using DashScope API"
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        },
        "required": ["query"]
    }
    
    def _execute(self, query: str, **kwargs):
        # Implementation using DashScope API
        headers = {"Authorization": f"Bearer {os.getenv('DASHSCOPE_API_KEY')}"}
        response = requests.post(url, json={"query": query}, headers=headers)
        return response.json()
```

### Terminate Tool

Controls conversation termination:

```python
@TOOL_REGISTRY.register()
class TerminateTool(BaseTool):
    name: str = "terminate"
    description: str = "Terminate the conversation when task is complete"
    parameters: dict = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Completion status",
                "enum": ["success", "failure"]
            }
        },
        "required": ["status"]
    }
    
    def execute(self, status: str):
        self.success = status in ["success", "failure"]
        return f"Conversation terminated with status: {status}"
```

### MCP Tool

Integrates with Model Context Protocol servers:

```python
@TOOL_REGISTRY.register()
class MCPTool(BaseTool):
    server_url: str                    # MCP server URL
    tool_name_list: List[str] = []     # Available tool names
    cache_tools: dict = {}             # Cached tool definitions
    
    def refresh(self):
        """Refresh available tools from MCP server"""
        # Connect to MCP server and fetch tool definitions
        
    def get_tool_description(self, tool_name: str) -> str:
        """Get description for specific MCP tool"""
        
    def _execute(self, tool_name: str, **kwargs):
        """Execute MCP tool"""
        # Forward execution to MCP server
```

## Creating Custom Tools

### Step 1: Define Tool Class

```python
from llmflow.tool import TOOL_REGISTRY
from llmflow.tool.base_tool import BaseTool

@TOOL_REGISTRY.register()
class DatabaseTool(BaseTool):
    name: str = "database_query"
    description: str = "Execute SQL queries on the database"
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "SQL query to execute"
            },
            "database": {
                "type": "string", 
                "description": "Database name",
                "default": "main"
            }
        },
        "required": ["query"]
    }
    
    def _execute(self, query: str, database: str = "main", **kwargs):
        # Validate query for safety
        if not self._is_safe_query(query):
            raise ValueError("Unsafe query detected")
        
        # Execute query
        connection = self._get_connection(database)
        try:
            cursor = connection.execute(query)
            results = cursor.fetchall()
            return {"results": results, "row_count": len(results)}
        except Exception as e:
            self.success = False
            return {"error": str(e)}
    
    def _is_safe_query(self, query: str) -> bool:
        # Implement safety checks
        dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]
        return not any(keyword in query.upper() for keyword in dangerous_keywords)
    
    def _get_connection(self, database: str):
        # Return database connection
        import sqlite3
        return sqlite3.connect(f"{database}.db")
```

### Step 2: Advanced Tool with Configuration

```python
from pydantic import Field
import requests
from typing import Optional, List

@TOOL_REGISTRY.register()
class APITool(BaseTool):
    name: str = "api_call"
    description: str = "Make HTTP API calls"
    
    # Tool-specific configuration
    base_url: str = Field(default="", description="Base API URL")
    api_key: str = Field(default="", description="API key")
    timeout: int = Field(default=30, description="Request timeout")
    
    parameters: dict = {
        "type": "object",
        "properties": {
            "endpoint": {"type": "string", "description": "API endpoint"},
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
            "data": {"type": "object", "description": "Request data"},
            "headers": {"type": "object", "description": "Additional headers"}
        },
        "required": ["endpoint"]
    }
    
    def _execute(self, endpoint: str, method: str = "GET", 
                 data: Optional[dict] = None, headers: Optional[dict] = None, **kwargs):
        
        # Prepare request
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        request_headers = {"Authorization": f"Bearer {self.api_key}"}
        if headers:
            request_headers.update(headers)
        
        try:
            # Make request
            response = requests.request(
                method=method.upper(),
                url=url,
                json=data,
                headers=request_headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            return {
                "status_code": response.status_code,
                "data": response.json() if response.content else None,
                "headers": dict(response.headers)
            }
            
        except requests.RequestException as e:
            self.success = False
            return {"error": str(e), "status_code": getattr(e.response, 'status_code', None)}
```

### Step 3: Tool with Caching

```python
import hashlib
import json

@TOOL_REGISTRY.register()
class ExpensiveComputationTool(BaseTool):
    name: str = "expensive_computation"
    description: str = "Perform expensive computations with caching"
    enable_cache: bool = True  # Enable caching
    
    parameters: dict = {
        "type": "object",
        "properties": {
            "input_data": {"type": "string", "description": "Input data to process"},
            "algorithm": {"type": "string", "enum": ["fast", "accurate"], "default": "fast"}
        },
        "required": ["input_data"]
    }
    
    def get_cache_id(self, **kwargs) -> str:
        """Generate unique cache ID for parameters"""
        cache_key = json.dumps(kwargs, sort_keys=True)
        return hashlib.md5(cache_key.encode()).hexdigest()
    
    def _execute(self, input_data: str, algorithm: str = "fast", **kwargs):
        # Simulate expensive computation
        import time
        time.sleep(2)  # Simulate processing time
        
        if algorithm == "accurate":
            result = self._accurate_computation(input_data)
        else:
            result = self._fast_computation(input_data)
        
        return {"result": result, "algorithm": algorithm, "processed_at": time.time()}
    
    def _fast_computation(self, data: str) -> str:
        return f"Fast result for: {data}"
    
    def _accurate_computation(self, data: str) -> str:
        return f"Accurate result for: {data}"
```

## Tool Integration

### Using Tools in Operations

Tools are typically used within ReAct operations:

```python
@OP_REGISTRY.register()
class CustomAgentOp(BaseOp):
    def execute(self):
        request = self.context.request
        response = self.context.response
        
        # Define available tools
        tool_names = self.op_params.get("tool_names", "database_tool,api_tool,terminate_tool")
        tools = [TOOL_REGISTRY[name.strip()]() for name in tool_names.split(",")]
        
        # Configure tools if needed
        for tool in tools:
            if hasattr(tool, 'configure'):
                tool.configure(self.op_params.get(f"{tool.name}_config", {}))
        
        # Use tools in conversation
        messages = [Message(role=Role.USER, content=request.query)]
        
        for step in range(10):  # Max steps
            # Get LLM response with tool calls
            assistant_message = self.llm.chat(messages, tools=tools)
            messages.append(assistant_message)
            
            # Execute tool calls
            for tool_call in assistant_message.tool_calls:
                tool = next((t for t in tools if t.name == tool_call.name), None)
                if tool:
                    result = tool.execute(**tool_call.argument_dict)
                    # Add tool result to conversation
                    tool_message = Message(
                        role=Role.TOOL,
                        content=str(result),
                        tool_call_id=tool_call.id
                    )
                    messages.append(tool_message)
            
            # Check for termination
            if any(tc.name == "terminate" for tc in assistant_message.tool_calls):
                break
```

### Tool Configuration

Tools can be configured in the operation parameters:

```yaml
op:
  custom_agent_op:
    backend: custom_agent_op
    llm: default
    params:
      tool_names: "database_tool,api_tool,terminate_tool"
      database_tool_config:
        connection_string: "sqlite:///data.db"
        max_results: 100
      api_tool_config:
        base_url: "https://api.example.com"
        api_key: "${API_KEY}"  # From environment
        timeout: 60
```

## Advanced Features

### Async Tool Execution

```python
import asyncio
from typing import Any

@TOOL_REGISTRY.register()
class AsyncTool(BaseTool):
    name: str = "async_operation"
    description: str = "Perform asynchronous operations"
    
    async def _execute_async(self, **kwargs) -> Any:
        """Async execution method"""
        # Async operations here
        await asyncio.sleep(1)
        return "Async result"
    
    def _execute(self, **kwargs):
        """Sync wrapper for async execution"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._execute_async(**kwargs))
```

### Tool Composition

```python
@TOOL_REGISTRY.register()
class ComposeTool(BaseTool):
    name: str = "compose_operations"
    description: str = "Compose multiple operations"
    
    def _execute(self, operations: List[dict], **kwargs):
        results = []
        
        for operation in operations:
            tool_name = operation["tool"]
            tool_params = operation["params"]
            
            # Get and execute tool
            tool = TOOL_REGISTRY[tool_name]()
            result = tool.execute(**tool_params)
            results.append({"tool": tool_name, "result": result})
        
        return {"composed_results": results}
```

### Tool Validation

```python
from pydantic import validator

@TOOL_REGISTRY.register()
class ValidatedTool(BaseTool):
    name: str = "validated_tool"
    description: str = "Tool with parameter validation"
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v) < 3:
            raise ValueError("Tool name must be at least 3 characters")
        return v
    
    def _execute(self, email: str, **kwargs):
        # Validate email format
        if "@" not in email:
            raise ValueError("Invalid email format")
        
        return f"Processed email: {email}"
```

## Testing Tools

### Unit Testing

```python
import pytest
from unittest.mock import patch, Mock
from your_module import DatabaseTool

class TestDatabaseTool:
    def setup_method(self):
        self.tool = DatabaseTool()
    
    def test_safe_query_validation(self):
        assert self.tool._is_safe_query("SELECT * FROM users")
        assert not self.tool._is_safe_query("DROP TABLE users")
    
    @patch('sqlite3.connect')
    def test_execute_query(self, mock_connect):
        # Mock database connection
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [("user1",), ("user2",)]
        mock_connection = Mock()
        mock_connection.execute.return_value = mock_cursor
        mock_connect.return_value = mock_connection
        
        # Execute tool
        result = self.tool.execute(query="SELECT name FROM users")
        
        # Verify results
        assert result["row_count"] == 2
        assert result["results"] == [("user1",), ("user2",)]
    
    def test_unsafe_query_rejection(self):
        with pytest.raises(ValueError, match="Unsafe query detected"):
            self.tool.execute(query="DROP TABLE users")
    
    def test_caching(self):
        # Enable caching
        self.tool.enable_cache = True
        
        # First execution
        result1 = self.tool.execute(query="SELECT 1")
        
        # Second execution (should use cache)
        result2 = self.tool.execute(query="SELECT 1")
        
        # Results should be identical
        assert result1 == result2
```

### Integration Testing

```python
import pytest
from llmflow.tool import TOOL_REGISTRY

class TestToolIntegration:
    def test_tool_registration(self):
        assert "database_query" in TOOL_REGISTRY
        tool_class = TOOL_REGISTRY["database_query"]
        assert issubclass(tool_class, BaseTool)
    
    def test_tool_schema_validation(self):
        tool = DatabaseTool()
        schema = tool.parameters
        
        assert "type" in schema
        assert "properties" in schema
        assert "query" in schema["properties"]
        assert "required" in schema
    
    def test_tool_execution_flow(self):
        tool = DatabaseTool()
        
        # Test successful execution
        result = tool.execute(query="SELECT 1")
        assert tool.success
        assert "results" in result
        
        # Test error handling
        tool.reset()
        result = tool.execute(query="INVALID SQL")
        assert not tool.success
        assert "error" in result
```

## Best Practices

### 1. Input Validation

```python
@TOOL_REGISTRY.register()
class SecureTool(BaseTool):
    def _execute(self, user_input: str, **kwargs):
        # Sanitize input
        sanitized_input = self._sanitize_input(user_input)
        
        # Validate input
        if not self._validate_input(sanitized_input):
            raise ValueError("Invalid input provided")
        
        # Process safely
        return self._safe_process(sanitized_input)
    
    def _sanitize_input(self, input_str: str) -> str:
        # Remove dangerous characters
        import re
        return re.sub(r'[<>"\']', '', input_str)
    
    def _validate_input(self, input_str: str) -> bool:
        # Validate input meets requirements
        return len(input_str) > 0 and len(input_str) < 1000
```

### 2. Error Handling

```python
@TOOL_REGISTRY.register()
class RobustTool(BaseTool):
    max_retries: int = 3
    
    def _execute(self, **kwargs):
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return self._attempt_execution(**kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue
        
        # All attempts failed
        self.success = False
        return {"error": f"Failed after {self.max_retries} attempts: {last_error}"}
    
    def _attempt_execution(self, **kwargs):
        # Actual execution logic
        pass
```

### 3. Resource Management

```python
@TOOL_REGISTRY.register()
class ResourceManagedTool(BaseTool):
    def _execute(self, **kwargs):
        resource = None
        try:
            resource = self._acquire_resource()
            return self._process_with_resource(resource, **kwargs)
        finally:
            if resource:
                self._release_resource(resource)
    
    def _acquire_resource(self):
        # Acquire expensive resource (connection, file handle, etc.)
        pass
    
    def _release_resource(self, resource):
        # Clean up resource
        pass
```

### 4. Documentation

```python
@TOOL_REGISTRY.register()
class WellDocumentedTool(BaseTool):
    """
    A well-documented tool that demonstrates best practices.
    
    This tool performs complex operations and requires careful
    parameter configuration. See the parameters schema for
    detailed information about each parameter.
    """
    
    name: str = "documented_tool"
    description: str = (
        "Performs complex data processing operations. "
        "Supports multiple algorithms and output formats. "
        "Use 'algorithm' parameter to control processing method."
    )
    
    parameters: dict = {
        "type": "object",
        "properties": {
            "data": {
                "type": "string",
                "description": "Input data to process. Must be valid JSON string.",
                "examples": ['{"key": "value"}']
            },
            "algorithm": {
                "type": "string",
                "enum": ["fast", "accurate", "balanced"],
                "default": "balanced",
                "description": (
                    "Processing algorithm to use:\n"
                    "- fast: Quick processing, lower accuracy\n"
                    "- accurate: Slower processing, higher accuracy\n"
                    "- balanced: Good balance of speed and accuracy"
                )
            }
        },
        "required": ["data"]
    }
```

### 5. Performance Optimization

```python
@TOOL_REGISTRY.register()
class OptimizedTool(BaseTool):
    enable_cache: bool = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connection_pool = self._create_connection_pool()
    
    def _create_connection_pool(self):
        # Create connection pool for reuse
        pass
    
    def _execute(self, **kwargs):
        # Use connection from pool
        with self._connection_pool.get_connection() as conn:
            return self._process_with_connection(conn, **kwargs)
    
    def get_cache_id(self, **kwargs) -> str:
        # Efficient cache key generation
        return hashlib.md5(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()
```

For more information, see the [Operations Development](operations.md) and [API Documentation](api.md) guides.
