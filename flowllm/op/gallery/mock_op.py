import asyncio
import time
from typing import List

from loguru import logger

from flowllm.context import C
from flowllm.context.flow_context import FlowContext
from flowllm.op.base_async_op import BaseAsyncOp
from flowllm.op.base_op import BaseOp
from flowllm.schema.message import Message, Role


@C.register_op(register_app="FlowLLM")
class Mock1Op(BaseOp):
    def execute(self):
        time.sleep(1)
        a = self.context.get("a", 1)
        b = self.context.get("b", 2)
        logger.info(f"enter class={self.name}. a={a} b={b}")

        self.context.response.answer = f"{self.name} a={a} b={b} answer=47"


@C.register_op(register_app="FlowLLM")
class Mock2Op(Mock1Op):
    ...


@C.register_op(register_app="FlowLLM")
class Mock3Op(Mock1Op):
    ...


@C.register_op(register_app="FlowLLM")
class Mock4Op(BaseAsyncOp):
    """使用 LLM 进行简单问答的异步 Op"""
    
    def __init__(self, llm: str = "qwen3_30b_instruct", **kwargs):
        super().__init__(llm=llm, **kwargs)
    
    async def async_execute(self):
        await asyncio.sleep(1)
        a = self.context.get("a", 1)
        b = self.context.get("b", 2)
        logger.info(f"enter class={self.name}. a={a} b={b}")
        
        # 使用 LLM 进行调用
        query = self.context.get("query", f"calculate {a} + {b}")
        messages: List[Message] = [Message(role=Role.USER, content=query)]
        
        # 调用 LLM
        response: Message = await self.llm.achat(messages)
        logger.info(f"LLM response: {response.content}")
        
        # 将 LLM 的响应保存到 context 中，供下一个 op 使用
        self.context.response.answer = response.content
        self.context.set("llm_response", response.content)


@C.register_op(register_app="FlowLLM")
class Mock5Op(BaseAsyncOp):
    """串联使用前一个 Op 的结果作为输入"""
    
    def __init__(self, llm: str = "qwen3_30b_instruct", **kwargs):
        super().__init__(llm=llm, **kwargs)
    
    async def async_execute(self):
        # 获取上一个 op 的结果
        previous_response = self.context.get("llm_response", "no previous response")
        logger.info(f"enter class={self.name}. previous_response={previous_response}")
        
        # 基于上一个结果继续对话
        query = self.context.get("query", f"Based on the previous answer: {previous_response}, please elaborate more.")
        messages: List[Message] = [
            Message(role=Role.USER, content=f"Previous result: {previous_response}"),
            Message(role=Role.USER, content=query)
        ]
        
        response: Message = await self.llm.achat(messages)
        logger.info(f"LLM response in {self.name}: {response.content}")
        
        # 更新 context
        self.context.response.answer = response.content
        self.context.set("llm_response", response.content)


@C.register_op(register_app="FlowLLM")
class Mock6Op(BaseAsyncOp):
    """支持多轮对话的 Mock Op"""
    
    def __init__(self, llm: str = "qwen3_30b_instruct", **kwargs):
        super().__init__(llm=llm, **kwargs)
    
    async def async_execute(self):
        # 获取历史消息
        messages = self.context.get("messages", [])
        if not messages:
            query = self.context.get("query", "Hello, how are you?")
            messages = [Message(role=Role.USER, content=query)]
        else:
            # 将 dict 转换为 Message 对象
            messages = [Message(**m) if isinstance(m, dict) else m for m in messages]
        
        logger.info(f"enter class={self.name}. messages count={len(messages)}")
        
        # 调用 LLM
        response: Message = await self.llm.achat(messages)
        logger.info(f"LLM response in {self.name}: {response.content}")
        
        # 添加助手的回复到消息历史
        messages.append(response)
        
        # 保存消息历史和答案
        self.context.set("messages", [m.model_dump() for m in messages])
        self.context.response.answer = response.content
        self.context.response.messages = messages


async def main():
    """演示多个 Op 之间的串联调用"""
    from flowllm.app import FlowLLMApp
    
    async with FlowLLMApp(load_default_config=True):
        # 示例 1: Mock4Op - 简单的 LLM 调用
        logger.info("=== Example 1: Mock4Op ===")
        context1 = FlowContext(query="What is 42 + 5?")
        op1 = Mock4Op()
        await op1.async_call(context=context1)
        logger.info(f"Mock4Op result: {context1.response.answer}")
        
        # 示例 2: Mock4Op -> Mock5Op - 串联调用
        logger.info("\n=== Example 2: Mock4Op -> Mock5Op ===")
        context2 = FlowContext(query="What is artificial intelligence?", a=10, b=20)
        
        op2 = Mock4Op()
        await op2.async_call(context=context2)
        logger.info(f"Mock4Op result: {context2.response.answer}")
        
        op3 = Mock5Op()
        context2.set("query", "Can you give me a practical example?")
        await op3.async_call(context=context2)
        logger.info(f"Mock5Op result: {context2.response.answer}")
        
        # 示例 3: Mock6Op - 多轮对话
        logger.info("\n=== Example 3: Mock6Op - Multi-turn ===")
        context3 = FlowContext(query="Tell me about Python programming")
        
        op4 = Mock6Op()
        await op4.async_call(context=context3)
        logger.info(f"Turn 1: {context3.response.answer}")
        
        # 第二轮对话
        messages = context3.get("messages", [])
        messages.append({"role": "user", "content": "What are its main features?"})
        context3.set("messages", messages)
        
        op5 = Mock6Op()
        await op5.async_call(context=context3)
        logger.info(f"Turn 2: {context3.response.answer}")


if __name__ == "__main__":
    asyncio.run(main())
