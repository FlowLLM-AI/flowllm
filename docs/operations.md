# Operations Development Guide

This guide covers how to develop custom operations in flowllm, including understanding the operation lifecycle, implementing custom logic, and integrating with the pipeline system.

## Table of Contents

- [Operation Overview](#operation-overview)
- [Base Operation Class](#base-operation-class)
- [Operation Lifecycle](#operation-lifecycle)
- [Built-in Operations](#built-in-operations)
- [Creating Custom Operations](#creating-custom-operations)
- [Advanced Features](#advanced-features)
- [Testing Operations](#testing-operations)
- [Best Practices](#best-practices)

## Operation Overview

Operations are the core building blocks of flowllm pipelines. They encapsulate specific functionality and can be chained together to create complex workflows. Each operation:

- Inherits from `BaseOp`
- Has access to the pipeline context
- Can use LLMs, vector stores, and other resources
- Supports custom prompts and parameters
- Can execute tasks in parallel

### Operation Architecture

```
┌─────────────────┐
│  Pipeline       │
│  Context        │
└─────────────────┘
         │
         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Operation     │───▶│      LLM        │    │  Vector Store   │
│   Instance      │    │   Instance      │    │   Instance      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐
│   Task Pool     │
│  (Parallel      │
│   Execution)    │
└─────────────────┘
```

## Base Operation Class

All operations inherit from `BaseOp`, which provides core functionality:

```python
from old.op.base_op import BaseOp
from old.op import OP_REGISTRY


@OP_REGISTRY.register()
class CustomOp(BaseOp):
    def execute(self):
        # Your operation logic here
        pass
```

### BaseOp Properties and Methods

#### Core Properties

```python
class BaseOp:
    # Configuration
    self.context: PipelineContext  # Pipeline execution context
    self.op_config: OpConfig  # Operation configuration
    self.op_params: dict  # Operation parameters

    # Resources (lazy-loaded)
    self.llm: BaseLLM  # LLM instance
    self.embedding_model: BaseEmbeddingModel  # Embedding model
    self.vector_store: BaseVectorStore  # Vector store instance

    # Utilities
    self.timer: Timer  # Performance timer
    self.task_list: List[Future]  # Parallel task list
    self.name: str  # Operation class name in snake_case
```

#### Core Methods

```python
# Abstract method - must be implemented
def execute(self):
    """Main operation logic"""
    pass

# Resource access methods
def get_llm(self, llm_name: str = None) -> BaseLLM:
    """Get LLM instance"""
    
def get_embedding_model(self, model_name: str = None) -> BaseEmbeddingModel:
    """Get embedding model instance"""
    
def get_vector_store(self, store_name: str = None) -> BaseVectorStore:
    """Get vector store instance"""

# Parallel execution
def submit_task(self, fn, *args, **kwargs) -> Future:
    """Submit task for parallel execution"""
    
def wait_for_tasks(self):
    """Wait for all submitted tasks to complete"""

# Prompt management (from PromptMixin)
def prompt_format(self, prompt_name: str, **kwargs) -> str:
    """Format prompt template with variables"""
```

## Operation Lifecycle

### 1. Initialization

When an operation is created during pipeline execution:

```python
def __init__(self, context: PipelineContext, op_config: OpConfig):
    self.context = context
    self.op_config = op_config
    self.timer = Timer(name=self.name)

    # Load prompts from file or config
    self._prepare_prompt()

    # Initialize resource references (lazy-loaded)
    self._llm = None
    self._embedding_model = None
    self._vector_store = None

    # Initialize task list for parallel execution
    self.task_list = []
```

### 2. Execution Wrapper

Operations are executed through a wrapper that handles timing and error management:

```python
def execute_wrap(self):
    with self.timer:
        try:
            self.execute()  # Your custom logic
        except Exception as e:
            logger.exception(f"Operation {self.name} failed")
            raise
        finally:
            # Wait for any parallel tasks to complete
            self.wait_for_tasks()
```

### 3. Resource Access

Resources are lazy-loaded when first accessed:

```python
@property
def llm(self) -> BaseLLM:
    if self._llm is None:
        llm_config_name = self.op_config.llm or "default"
        llm_config = self.context.app_config.llm[llm_config_name]
        llm_cls = LLM_REGISTRY[llm_config.backend]
        self._llm = llm_cls(model_name=llm_config.model_name, **llm_config.params)
    return self._llm
```

## Built-in Operations

### ReAct Agent Operation

The `ReactV1Op` implements a ReAct (Reasoning and Acting) agent:

```python
@OP_REGISTRY.register()
class ReactV1Op(BaseOp):
    current_path: str = __file__  # For prompt file resolution
    
    def execute(self):
        request: AgentRequest = self.context.request
        response: AgentResponse = self.context.response
        
        max_steps = int(self.op_params.get("max_steps", 10))
        tool_names = self.op_params.get("tool_names", "terminate_tool")
        tools = [TOOL_REGISTRY[name.strip()]() for name in tool_names.split(",")]
        
        # Initial prompt
        user_prompt = self.prompt_format(
            prompt_name="role_prompt",
            time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            tools=",".join([t.name for t in tools]),
            query=request.query
        )
        
        messages = [Message(role=Role.USER, content=user_prompt)]
        
        # ReAct loop
        for i in range(max_steps):
            # Get LLM response with tools
            assistant_message = self.llm.chat(messages, tools=tools)
            messages.append(assistant_message)
            
            # Execute tool calls in parallel
            for tool_call in assistant_message.tool_calls:
                if tool_call.name in [t.name for t in tools]:
                    tool = next(t for t in tools if t.name == tool_call.name)
                    self.submit_task(tool.execute, **tool_call.argument_dict)
            
            # Check for termination
            if any(tc.name == "terminate" for tc in assistant_message.tool_calls):
                break
```

### Vector Store Operations

#### Recall Operation

```python
@OP_REGISTRY.register()
class RecallVectorStoreOp(BaseOp):
    def execute(self):
        request: RetrieverRequest = self.context.request
        response: RetrieverResponse = self.context.response
        
        # Search vector store
        results = self.vector_store.search(
            query=request.query,
            workspace_id=request.workspace_id,
            top_k=request.top_k
        )
        
        # Convert to experiences
        experience_list = []
        for result in results:
            experience = Experience(
                workspace_id=result.workspace_id,
                content=result.content,
                metadata=result.metadata,
                node_id=result.node_id
            )
            experience_list.append(experience)
        
        response.experience_list = experience_list
```

#### Update Operation

```python
@OP_REGISTRY.register()
class UpdateVectorStoreOp(BaseOp):
    def execute(self):
        request: SummarizerRequest = self.context.request
        response: SummarizerResponse = self.context.response
        
        # Process trajectories
        insert_nodes = []
        for traj in request.traj_list:
            # Convert trajectory to vector node
            content = self._process_trajectory(traj)
            node = VectorNode(
                workspace_id=request.workspace_id,
                content=content,
                metadata={"type": "summary", "timestamp": datetime.now().isoformat()}
            )
            insert_nodes.append(node)
        
        # Insert into vector store
        if insert_nodes:
            self.vector_store.insert(insert_nodes, workspace_id=request.workspace_id)
        
        response.experience_list = [
            Experience(
                workspace_id=node.workspace_id,
                content=node.content,
                metadata=node.metadata,
                node_id=node.node_id
            ) for node in insert_nodes
        ]
```

## Creating Custom Operations

### Step 1: Define Operation Class

```python
from old.op import OP_REGISTRY
from old.op.base_op import BaseOp


@OP_REGISTRY.register("my_custom_op")  # Optional: specify registry name
class MyCustomOp(BaseOp):
    current_path: str = __file__  # For prompt file resolution

    def execute(self):
        # Access request and response
        request = self.context.request
        response = self.context.response

        # Access configuration parameters
        param1 = self.op_params.get("param1", "default_value")
        param2 = self.op_params.get("param2", 42)

        # Your custom logic here
        result = self.process_data(request.query, param1, param2)

        # Update response
        response.metadata["custom_result"] = result

    def process_data(self, query: str, param1: str, param2: int):
        # Custom processing logic
        return f"Processed {query} with {param1} and {param2}"
```

### Step 2: Create Configuration

```yaml
op:
  my_custom_op:
    backend: my_custom_op
    llm: default
    vector_store: default
    params:
      param1: "custom_value"
      param2: 100
```

### Step 3: Use in Pipeline

```yaml
api:
  custom_pipeline: my_custom_op->recall_vector_store_op
```

### Example: Text Processing Operation

```python
@OP_REGISTRY.register()
class TextProcessingOp(BaseOp):
    current_path: str = __file__
    
    def execute(self):
        request = self.context.request
        response = self.context.response
        
        # Get processing parameters
        operation_type = self.op_params.get("operation", "summarize")
        max_length = self.op_params.get("max_length", 500)
        
        # Process based on operation type
        if operation_type == "summarize":
            result = self.summarize_text(request.query, max_length)
        elif operation_type == "analyze":
            result = self.analyze_text(request.query)
        elif operation_type == "translate":
            target_lang = self.op_params.get("target_language", "en")
            result = self.translate_text(request.query, target_lang)
        else:
            raise ValueError(f"Unknown operation: {operation_type}")
        
        # Update response
        response.metadata["processed_text"] = result
        response.metadata["operation_type"] = operation_type
    
    def summarize_text(self, text: str, max_length: int) -> str:
        prompt = self.prompt_format(
            prompt_name="summarize_prompt",
            text=text,
            max_length=max_length
        )
        
        messages = [Message(role=Role.USER, content=prompt)]
        response = self.llm.chat(messages)
        return response.content
    
    def analyze_text(self, text: str) -> dict:
        prompt = self.prompt_format(
            prompt_name="analyze_prompt",
            text=text
        )
        
        messages = [Message(role=Role.USER, content=prompt)]
        response = self.llm.chat(messages)
        
        # Parse structured response
        return {"analysis": response.content, "sentiment": "neutral"}
    
    def translate_text(self, text: str, target_lang: str) -> str:
        prompt = self.prompt_format(
            prompt_name="translate_prompt",
            text=text,
            target_language=target_lang
        )
        
        messages = [Message(role=Role.USER, content=prompt)]
        response = self.llm.chat(messages)
        return response.content
```

**Corresponding prompt file (text_processing_prompt.yaml):**

```yaml
summarize_prompt: |
  Please summarize the following text in no more than {max_length} characters:
  
  {text}

analyze_prompt: |
  Please analyze the following text and provide insights about:
  - Main themes
  - Sentiment
  - Key points
  - Writing style
  
  Text: {text}

translate_prompt: |
  Please translate the following text to {target_language}:
  
  {text}
```

## Advanced Features

### Parallel Task Execution

Operations can execute tasks in parallel using the thread pool:

```python
@OP_REGISTRY.register()
class ParallelProcessingOp(BaseOp):
    def execute(self):
        request = self.context.request
        response = self.context.response
        
        # Submit multiple tasks in parallel
        tasks = []
        for item in request.items:
            future = self.submit_task(self.process_item, item)
            tasks.append(future)
        
        # Collect results
        results = []
        for future in tasks:
            result = future.result()  # This will block until complete
            results.append(result)
        
        response.metadata["results"] = results
    
    def process_item(self, item):
        # Process individual item
        return f"Processed: {item}"
```

### Multi-LLM Operations

Use different LLMs for different tasks:

```python
@OP_REGISTRY.register()
class MultiLLMOp(BaseOp):
    def execute(self):
        request = self.context.request
        response = self.context.response
        
        # Use fast model for classification
        fast_llm = self.get_llm("fast_model")
        classification = self.classify_query(request.query, fast_llm)
        
        # Use reasoning model for complex analysis
        if classification == "complex":
            reasoning_llm = self.get_llm("reasoning_model")
            result = self.complex_analysis(request.query, reasoning_llm)
        else:
            result = self.simple_processing(request.query, fast_llm)
        
        response.metadata["classification"] = classification
        response.metadata["result"] = result
    
    def classify_query(self, query: str, llm: BaseLLM) -> str:
        prompt = f"Classify this query as 'simple' or 'complex': {query}"
        messages = [Message(role=Role.USER, content=prompt)]
        response = llm.chat(messages)
        return response.content.strip().lower()
```

### Vector Store Integration

Operations can interact with multiple vector stores:

```python
@OP_REGISTRY.register()
class MultiVectorStoreOp(BaseOp):
    def execute(self):
        request = self.context.request
        response = self.context.response
        
        # Search in knowledge base
        knowledge_results = self.get_vector_store("knowledge_base").search(
            query=request.query,
            workspace_id=request.workspace_id,
            top_k=5
        )
        
        # Search in conversation history
        history_results = self.get_vector_store("conversation_history").search(
            query=request.query,
            workspace_id=request.workspace_id,
            top_k=3
        )
        
        # Combine and rank results
        all_results = knowledge_results + history_results
        ranked_results = self.rank_results(all_results, request.query)
        
        response.experience_list = ranked_results
```

## Testing Operations

### Unit Testing

```python
import pytest
from unittest.mock import Mock, MagicMock
from old.pipeline.pipeline_context import PipelineContext
from old.schema.app_config import OpConfig
from your_module import MyCustomOp


class TestMyCustomOp:
    def setup_method(self):
        # Mock context
        self.context = Mock(spec=PipelineContext)
        self.context.request = Mock()
        self.context.response = Mock()
        self.context.app_config = Mock()

        # Mock operation config
        self.op_config = Mock(spec=OpConfig)
        self.op_config.params = {"param1": "test_value", "param2": 123}
        self.op_config.llm = "default"
        self.op_config.vector_store = "default"

        # Create operation instance
        self.op = MyCustomOp(context=self.context, op_config=self.op_config)

    def test_execute_basic(self):
        # Setup request
        self.context.request.query = "test query"

        # Execute operation
        self.op.execute()

        # Verify response was updated
        assert "custom_result" in self.op.context.response.metadata

    def test_process_data(self):
        result = self.op.process_data("test", "param1", 42)
        assert "Processed test with param1 and 42" == result

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        # Test parallel task execution
        self.context.thread_pool = Mock()
        future_mock = Mock()
        future_mock.result.return_value = "task_result"
        self.context.thread_pool.submit.return_value = future_mock

        # Submit task
        future = self.op.submit_task(lambda x: x, "test")

        # Verify task was submitted
        self.context.thread_pool.submit.assert_called_once()
        assert future == future_mock
```

### Integration Testing

```python
import pytest
from old.service.flowllm_service import flowllmService
from old.schema.request import AgentRequest


class TestOperationIntegration:
    def setup_method(self):
        # Use test configuration
        self.service = flowllmService(["--config-file=test_config.yaml"])

    def test_custom_operation_in_pipeline(self):
        request = AgentRequest(
            query="test query",
            workspace_id="test",
            config={}
        )

        response = self.service(api="custom_pipeline", request=request)

        assert response.success
        assert "custom_result" in response.metadata
```

## Best Practices

### 1. Error Handling

```python
@OP_REGISTRY.register()
class RobustOp(BaseOp):
    def execute(self):
        try:
            result = self.risky_operation()
            self.context.response.metadata["result"] = result
        except Exception as e:
            logger.exception(f"Operation {self.simple_name} failed")
            self.context.response.success = False
            self.context.response.metadata["error"] = str(e)
    
    def risky_operation(self):
        # Operation that might fail
        pass
```

### 2. Resource Management

```python
@OP_REGISTRY.register()
class ResourceAwareOp(BaseOp):
    def execute(self):
        # Check if resources are available
        if not hasattr(self.context.app_config, 'llm'):
            raise ValueError("LLM configuration required")
        
        # Use resources efficiently
        with self.timer.child("llm_call"):
            result = self.llm.chat(messages)
        
        # Clean up if necessary
        self.cleanup_resources()
    
    def cleanup_resources(self):
        # Clean up temporary resources
        pass
```

### 3. Configuration Validation

```python
@OP_REGISTRY.register()
class ValidatedOp(BaseOp):
    def __init__(self, context, op_config):
        super().__init__(context, op_config)
        self._validate_config()
    
    def _validate_config(self):
        required_params = ["param1", "param2"]
        for param in required_params:
            if param not in self.op_params:
                raise ValueError(f"Required parameter {param} not found")
        
        # Validate parameter values
        if self.op_params["param2"] <= 0:
            raise ValueError("param2 must be positive")
```

### 4. Logging and Monitoring

```python
from loguru import logger

@OP_REGISTRY.register()
class MonitoredOp(BaseOp):
    def execute(self):
        logger.info(f"Starting {self.simple_name} with params: {self.op_params}")
        
        start_time = time.time()
        try:
            result = self.process()
            logger.info(f"Operation completed successfully in {time.time() - start_time:.2f}s")
            return result
        except Exception as e:
            logger.error(f"Operation failed after {time.time() - start_time:.2f}s: {e}")
            raise
```

### 5. Prompt Management

```python
@OP_REGISTRY.register()
class PromptManagedOp(BaseOp):
    current_path: str = __file__
    
    def execute(self):
        # Use structured prompts
        system_prompt = self.prompt_format("system_prompt", domain="AI")
        user_prompt = self.prompt_format("user_prompt", query=self.context.request.query)
        
        messages = [
            Message(role=Role.SYSTEM, content=system_prompt),
            Message(role=Role.USER, content=user_prompt)
        ]
        
        response = self.llm.chat(messages)
        # Process response...
```

For more information, see the [Tools Development](tools.md) and [Configuration Guide](configuration.md) documentation.
