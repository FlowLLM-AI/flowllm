## 异步 Op 高级功能指南

这是一个完整的示例，展示如何在异步 Op 中使用 Embedding、VectorStore 和并发执行等高级功能。

---

### 完整示例

#### Op 文件：`rag_search_op.py`

```python
from flowllm.core.context import C
from flowllm.core.op.base_async_op import BaseAsyncOp
from flowllm.core.schema import VectorNode
from flowllm.main import FlowLLMApp
import asyncio


@C.register_op()
class RAGSearchOp(BaseAsyncOp):
    """RAG 搜索 Op，展示 embedding、vectorstore 和并发能力"""

    async def async_execute(self):
        """执行 RAG 搜索逻辑"""
        # 1. 读取输入
        query = self.context.get("query", "")
        workspace_id = self.context.get("workspace_id", "default")
        top_k = self.context.get("top_k", 3)

        assert query, "query 不能为空"

        # 2. 使用 Embedding 生成查询向量（一行代码示意 emb）
        query_vector = await self.embedding_model.get_embeddings_async(query)

        # 3. 使用 VectorStore 进行语义搜索（一行代码示意 vectorstore）
        nodes = await self.vector_store.async_search(query=query, workspace_id=workspace_id, top_k=top_k)

        # 4. 并发处理多个查询（两行代码示意并发）
        # 提交多个并发任务
        for node in nodes:
            self.submit_async_task(self._process_node, node)
        # 等待所有任务完成
        results = await self.join_async_task()

        # 5. 写回输出
        self.context.response.nodes = nodes
        self.context.response.results = results
        return results

    async def _process_node(self, node: VectorNode):
        """并发处理单个节点的辅助方法"""
        # 模拟一些异步处理，比如进一步分析节点内容
        await asyncio.sleep(0.1)  # 模拟异步操作
        return {"node_id": node.unique_id, "content": node.content[:50]}


# 使用示例
async def main():
    async with FlowLLMApp() as app:
        # 基本使用
        result = await RAGSearchOp().async_call(
            query="什么是机器学习？",
            workspace_id="knowledge_base",
            top_k=5
        )
        print(f"搜索结果：{result}")

        # 使用自定义 embedding_model 和 vector_store
        result2 = await RAGSearchOp(
            embedding_model="openai_compatible",
            vector_store="memory"
        ).async_call(
            query="深度学习",
            workspace_id="ai_knowledge"
        )
        print(f"搜索结果：{result2}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 关键要点

1. **Embedding 使用**：
   - 通过 `self.embedding_model.get_embeddings_async(text)` 生成文本向量
   - 支持单个文本或文本列表的批量处理
   - 返回向量列表（单个文本返回单个向量）

2. **VectorStore 使用**：
   - 通过 `self.vector_store.async_search(query, workspace_id, top_k)` 进行语义搜索
   - 通过 `self.vector_store.async_insert(nodes, workspace_id)` 插入向量节点
   - 返回 `VectorNode` 列表，每个节点包含 `content`、`vector`、`metadata` 等信息

3. **并发执行**：
   - 使用 `self.submit_async_task(fn, *args, **kwargs)` 提交异步任务
   - 使用 `await self.join_async_task(timeout=..., return_exceptions=True)` 等待所有任务完成
   - 支持超时控制和异常处理

4. **VectorNode 结构**：
   - `unique_id`: 唯一标识符
   - `workspace_id`: 工作空间 ID
   - `content`: 文本内容
   - `vector`: 向量嵌入（可选）
   - `metadata`: 元数据字典

5. **配置方式**：
   - 可以在 Op 初始化时传入 `embedding_model` 和 `vector_store` 参数
   - 支持字符串配置名（从服务配置中读取）或直接传入实例

---

### 参考示例

实际项目中的示例：

- `flowllm/flowllm/core/embedding_model/` - Embedding 模型实现
- `flowllm/flowllm/core/vector_store/` - VectorStore 实现
- `flowllm/flowllm/core/op/base_async_op.py` - 异步 Op 基类，包含并发执行方法

