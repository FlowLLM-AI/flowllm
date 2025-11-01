import asyncio
import json

from loguru import logger

from flowllm.context import FlowContext, C
from flowllm.enumeration.role import Role
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.op.search import DashscopeSearchOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall
from flowllm.utils.common_utils import extract_content


@C.register_op(register_app="FlowLLM")
class ExtractEntitiesCodeOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(self, llm: str = "qwen3_30b_instruct", **kwargs):
        super().__init__(llm=llm, **kwargs)

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": """
Extract financial entities from the query, including types such as "stock", "bond", "fund", "cryptocurrency", "index", "commodity", "etf", etc.
For entities like stocks or ETF funds, search for their corresponding codes. Finally, return the financial entities appearing in the query, including their types and codes.
            """.strip(),
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
        query = f"the {entity_type} code of {entity}"
        search_op = self.ops[0].copy()
        assert isinstance(search_op, BaseAsyncToolOp)
        await search_op.async_call(context=FlowContext(query=query))

        extract_code_prompt: str = self.prompt_format(
            prompt_name="extract_code_prompt",
            entity=entity,
            text=search_op.output,
        )

        def callback_fn(message: Message):
            return extract_content(message.content)

        assistant_result = await self.llm.achat(
            messages=[Message(role=Role.USER, content=extract_code_prompt)],
            callback_fn=callback_fn,
        )
        logger.info(f"entity={entity} response={search_op.output} {json.dumps(assistant_result, ensure_ascii=False)}")
        return {"entity": entity, "codes": assistant_result}

    async def async_execute(self):
        query = self.input_dict["query"]
        extract_entities_prompt: str = self.prompt_format(
            prompt_name="extract_entities_prompt",
            example=self.get_prompt(prompt_name="extract_entities_example"),
            query=query,
        )

        def callback_fn(message: Message):
            return extract_content(message.content)

        assistant_result = await self.llm.achat(
            messages=[Message(role=Role.USER, content=extract_entities_prompt)],
            callback_fn=callback_fn,
        )
        logger.info(json.dumps(assistant_result, ensure_ascii=False))

        entity_list = []
        for entity_info in assistant_result:
            if entity_info["type"] in ["stock", "股票", "etf", "fund"]:
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

    async with FlowLLMApp(load_default_config=True):
        # query = "茅台和五粮液哪个好？现在适合买入以太坊吗？"
        query = "中概etf？"
        context = FlowContext(query=query)
        op = ExtractEntitiesCodeOp() << DashscopeSearchOp()
        await op.async_call(context=context)
        logger.info(op.output)


if __name__ == "__main__":
    asyncio.run(main())
