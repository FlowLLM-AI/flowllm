import asyncio
import json

from loguru import logger

from flowllm.context import FlowContext, C
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import extract_content


@C.register_op(register_app="FlowLLM")
class ExtractQueryOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(
        self,
        llm: str = "qwen3_30b_instruct",
        # llm: str = "qwen25_max_instruct",
        save_answer: bool = True,
        **kwargs,
    ):
        super().__init__(llm=llm, save_answer=save_answer, **kwargs)

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "从query中提取金融实体，包括“股票”、“债券”、“基金”、“加密货币”、“指数”、“商品”、“ETF”等类型。对于股票或ETF基金等实体，请查找其对应的代码。最后，返回查询中出现的金融实体，包括其类型和代码。",
                "input_schema": {
                    "query": {
                        "type": "string",
                        "description": "query",
                        "required": True,
                    },
                },
            },
        )

    async def get_entity_code(self, entity: str, entity_type: str):
        query = f"{entity}的{entity_type}代码"
        search_op = self.ops[0].copy()
        assert isinstance(search_op, BaseAsyncToolOp)
        await search_op.async_call(context=FlowContext(query=query))
        logger.info(f"entity={entity} search_op.output={search_op.output}")

        extract_code_prompt: str = self.prompt_format(
            prompt_name="extract_code_prompt",
            entity=entity,
            text=search_op.output,
        )

        def callback_fn(message: Message):
            logger.info(f"message.content={message.content}")
            result = extract_content(message.content)
            if not result:
                return []

            result = [x for x in result if isinstance(x, str)]
            return result

        assistant_result = await self.llm.achat(
            messages=[Message(role=Role.USER, content=extract_code_prompt)],
            callback_fn=callback_fn,
        )
        return {"entity": entity, "codes": assistant_result}

    async def async_execute(self):
        query = self.input_dict["query"]
        extract_entities_prompt: str = self.prompt_format(prompt_name="extract_query_prompt", query=query)
        logger.info(f"extract_entities_prompt={extract_entities_prompt}")

        def callback_fn(message: Message):
            logger.info(f"message.content={message.content}")
            result = extract_content(message.content)
            if not result:
                return []

            if isinstance(result, dict):
                result = [result]
            return result

        assistant_result = await self.llm.achat(
            messages=[Message(role=Role.USER, content=extract_entities_prompt)],
            callback_fn=callback_fn,
        )
        logger.info(json.dumps(assistant_result, ensure_ascii=False))

        entity_list = []
        for entity_info in assistant_result:
            if entity_info["type"].lower() in ["stock", "股票", "etf", "基金", "bond", "债券"]:
                entity_list.append(entity_info["entity"])
                self.submit_async_task(
                    self.get_entity_code,
                    entity=entity_info["entity"],
                    entity_type=entity_info["type"],
                )

        for t_result in await self.join_async_task():
            entity = t_result["entity"]
            codes = t_result["codes"]
            for entity_info in assistant_result:
                if entity_info["entity"] == entity:
                    entity_info["codes"] = codes

        self.set_result(json.dumps(assistant_result, ensure_ascii=False))


async def main():
    from flowllm.app import FlowLLMApp
    from flowllm.op.search import TongyiMcpSearchOp

    async with FlowLLMApp(args=["config=fin_research"]):
        query = "茅台和五粮液哪个好？现在适合买入以太坊吗？"
        # query = "中概etf？"
        context = FlowContext(query=query)
        op = ExtractQueryOp() << TongyiMcpSearchOp()
        await op.async_call(context=context)
        logger.info(op.output)


if __name__ == "__main__":
    asyncio.run(main())
