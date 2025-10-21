# 异步任务处理指南

## 问题背景

在使用 `BaseAsyncOp.submit_async_task()` 和 `join_async_task()` 时，如果提交的任务中有异常或网络超时，可能会导致程序卡死。

### 原因分析

1. **异常传播延迟**：通过 `create_task()` 创建的任务如果抛出异常，不会立即传播，而是在 `await asyncio.gather()` 时才抛出
2. **任务无法取消**：默认的 `gather()` 在遇到异常时不会自动取消其他任务
3. **网络超时问题**：如果任务中有网络请求卡住（如 SSE 连接错误），没有超时机制会导致永久等待

## 解决方案

### 1. 改进的 `join_async_task` 方法

新的 `join_async_task` 方法支持以下功能：

```python
async def join_async_task(self, timeout: float = None, return_exceptions: bool = False):
    """
    等待所有异步任务完成
    
    Args:
        timeout: 超时时间（秒），None表示无限等待
        return_exceptions: 如果为True，异常会作为结果返回；如果为False，第一个异常会被抛出
    
    Returns:
        所有任务的结果列表
    """
```

#### 关键改进：

1. **超时保护**：设置 `timeout` 参数可以避免任务永久等待
2. **异常取消机制**：当任何任务失败或超时时，自动取消所有其他任务
3. **灵活的异常处理**：通过 `return_exceptions` 参数控制异常处理方式

### 2. 使用示例

#### 场景1：严格模式（遇到异常立即停止）

```python
class MyOp(BaseAsyncOp):
    async def async_execute(self):
        # 提交多个任务
        for query in search_queries:
            search_op = self.ops[0].copy()
            self.submit_async_task(search_op.async_call, query=query)
        
        # 如果任何一个任务失败，立即抛出异常并取消其他任务
        await self.join_async_task()
```

#### 场景2：容错模式（收集所有成功的结果）

```python
class MyOp(BaseAsyncOp):
    async def async_execute(self):
        # 提交多个任务
        for query in search_queries:
            search_op = self.ops[0].copy()
            self.submit_async_task(search_op.async_call, query=query)
        
        # 即使部分任务失败，也继续处理成功的结果
        results = await self.join_async_task(return_exceptions=True)
        # results 中会包含成功的结果和异常对象
```

#### 场景3：带超时的任务（推荐）

```python
class MyOp(BaseAsyncOp):
    async def async_execute(self):
        # 提交多个任务
        for query in search_queries:
            search_op = self.ops[0].copy()
            self.submit_async_task(search_op.async_call, query=query)
        
        try:
            # 设置总超时时间为 60 秒
            results = await self.join_async_task(timeout=60.0)
        except asyncio.TimeoutError:
            logger.error("Tasks timeout, some queries may have failed")
            # 所有任务已被自动取消
```

#### 场景4：容错 + 超时（最灵活）

```python
class MyOp(BaseAsyncOp):
    async def async_execute(self):
        # 提交多个任务
        for query in search_queries:
            search_op = self.ops[0].copy()
            self.submit_async_task(search_op.async_call, query=query)
        
        try:
            # 最多等待60秒，部分失败也继续
            results = await self.join_async_task(timeout=60.0, return_exceptions=True)
            
            # 分离成功和失败的结果
            success_results = [r for r in results if not isinstance(r, Exception)]
            failed_results = [r for r in results if isinstance(r, Exception)]
            
            # 异常会自动通过 logger.exception 打印，这里只统计数量
            logger.info(f"Success: {len(success_results)}, Failed: {len(failed_results)}")
            
        except asyncio.TimeoutError:
            logger.error("Tasks timeout")
```

### 3. MCP 客户端的超时配置

对于 MCP 调用，建议在两个层面设置超时：

#### 3.1 MCP 客户端级别

```python
class BaseMcpOp(BaseAsyncToolOp):
    def __init__(self, 
                 mcp_name: str = "",
                 timeout: float = 30.0,  # MCP 调用超时
                 **kwargs):
        self.timeout = timeout
        super().__init__(**kwargs)
    
    async def async_execute(self):
        async with McpClient(name=self.mcp_name, 
                           config=config, 
                           timeout=self.timeout) as client:
            result = await client.call_tool(self.tool_name, arguments=self.input_dict)
```

#### 3.2 任务汇总级别

```python
class CompanySegmentFactorOp(BaseAsyncToolOp):
    async def _execute_searches(self, search_queries: List[str]) -> str:
        for query in search_queries:
            search_op = self.ops[0].copy()
            self.submit_async_task(search_op.async_call, query=query)
        
        # 设置总超时，避免所有搜索任务卡死
        await self.join_async_task(timeout=120.0, return_exceptions=True)
```

## 日志输出

`join_async_task` 使用 `logger.exception` 记录异常信息，会自动打印完整的堆栈跟踪：

### return_exceptions=False（默认）

```python
# 任何任务失败时，会打印异常堆栈并抛出
await self.join_async_task(timeout=60.0)
```

日志输出示例：
```
ERROR | join_async_task failed with SSEError, cancelling remaining tasks...
Traceback (most recent call last):
  File "/path/to/mcp/client/sse.py", line 72, in sse_reader
    ...
httpx_sse._exceptions.SSEError: Expected response header Content-Type to contain 'text/event-stream', got ''
```

### return_exceptions=True（容错模式）

```python
# 每个失败的任务都会单独记录
results = await self.join_async_task(timeout=60.0, return_exceptions=True)
```

日志输出示例：
```
ERROR | Task failed with exception
Traceback (most recent call last):
  ...
httpx_sse._exceptions.SSEError: ...

ERROR | Task failed with exception
Traceback (most recent call last):
  ...
asyncio.TimeoutError: ...
```

## 最佳实践

1. **总是设置超时**：对于网络请求或外部服务调用，一定要设置合理的超时时间
2. **考虑容错**：如果任务之间相对独立，使用 `return_exceptions=True` 提高鲁棒性
3. **日志记录**：`logger.exception` 会自动记录完整的异常堆栈，便于排查问题
4. **分层超时**：
   - 单个 MCP 调用：30-60秒
   - 批量任务汇总：根据任务数量和单个超时计算，留有余地
5. **优雅降级**：即使部分任务失败，也能返回部分结果

## 常见错误场景

### 错误1：SSE 连接错误导致卡死

```python
# 错误：没有超时保护
await self.join_async_task()

# 正确：添加超时
await self.join_async_task(timeout=60.0)
```

### 错误2：一个任务失败导致所有结果丢失

```python
# 错误：任何一个失败就抛异常
results = await self.join_async_task()

# 正确：收集所有成功的结果
results = await self.join_async_task(return_exceptions=True)
success_results = [r for r in results if not isinstance(r, Exception)]
```

### 错误3：没有清理失败的任务

改进后的 `join_async_task` 会自动处理，不需要手动清理。

## 调试建议

如果遇到任务卡死问题：

1. **添加详细日志**：在 `submit_async_task` 前后添加日志
2. **检查超时设置**：确保 MCP 客户端和任务汇总都设置了超时
3. **使用 return_exceptions**：先让程序运行起来，收集异常信息
4. **逐个测试**：将并发任务改为串行执行，定位问题任务

```python
# 调试模式：串行执行，定位问题
for query in search_queries:
    try:
        search_op = self.ops[0].copy()
        result = await search_op.async_call(query=query)
        logger.info(f"Query '{query}' success")
    except Exception as e:
        logger.error(f"Query '{query}' failed: {e}")
```

