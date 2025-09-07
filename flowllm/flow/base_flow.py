import asyncio
from abc import ABC, abstractmethod
from functools import partial
from typing import Union

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_op import BaseOp
from flowllm.op.parallel_op import ParallelOp
from flowllm.op.sequential_op import SequentialOp
from flowllm.schema.flow_response import FlowResponse
from flowllm.schema.flow_stream_chunk import FlowStreamChunk
from flowllm.utils.common_utils import camel_to_snake


class BaseFlow(ABC):

    def __init__(self,
                 name: str = "",
                 use_async: bool = True,
                 stream: bool = True,
                 service_type: str = "",
                 **kwargs):
        self.name: str = name or camel_to_snake(self.__class__.__name__)
        self.use_async: bool = use_async
        self.stream: bool = stream
        self.service_type: str = service_type
        self.flow_params: dict = kwargs

        self.flow_op = self.build_flow()
        self.print_flow()

    @abstractmethod
    def build_flow(self):
        ...

    def print_flow(self):
        assert self.flow_op is not None, "flow_content is not parsed!"
        logger.info(f"---------- start print flow={self.name} ----------")
        self._print_operation_tree(self.flow_op, indent=0)
        logger.info(f"---------- end print flow={self.name} ----------")

    def _print_operation_tree(self, op: BaseOp, indent: int):
        """
        Recursively print the operation tree structure.

        Args:
            op: The operation to print
            indent: Current indentation level
        """
        prefix = "  " * indent
        if isinstance(op, SequentialOp):
            logger.info(f"{prefix}Sequential Execution:")
            for i, sub_op in enumerate(op.ops):
                logger.info(f"{prefix}  Step {i + 1}:")
                self._print_operation_tree(sub_op, indent + 2)

        elif isinstance(op, ParallelOp):
            logger.info(f"{prefix}Parallel Execution:")
            for i, sub_op in enumerate(op.ops):
                logger.info(f"{prefix}  Branch {i + 1}:")
                self._print_operation_tree(sub_op, indent + 2)

        else:
            logger.info(f"{prefix}Operation: {op.name}")
            if op.sub_op is not None:
                self._print_operation_tree(op.sub_op, indent + 2)

    async def __call__(self, **kwargs) -> Union[FlowResponse | FlowStreamChunk | None]:
        context = FlowContext(stream=self.stream, use_async=self.use_async, service_type=self.service_type, **kwargs)
        logger.info(f"request.params={kwargs}")

        try:
            flow_op: BaseOp = self.build_flow()

            if self.use_async:
                await flow_op.async_call(context=context)

            else:
                loop = asyncio.get_event_loop()
                op_call_fn = partial(flow_op.__call__, context=context)
                await loop.run_in_executor(executor=C.thread_pool, func=op_call_fn)  # noqa

            if self.stream:
                await context.add_stream_done()

        except Exception as e:
            logger.exception(f"flow_name={self.name} encounter error={e.args}")

            if self.stream:
                await context.add_stream_error(e)
            else:
                context.add_response_error(e)

        if self.stream:
            return context.stream_queue
        else:
            return context.response

    def sync_call(self, **kwargs) -> FlowResponse:
        assert self.use_async is False, "sync_call can only be used when use_async is False"
        context = FlowContext(stream=self.stream, use_async=self.use_async, service_type=self.service_type, **kwargs)
        logger.info(f"request.params={kwargs}")

        try:
            flow_op: BaseOp = self.build_flow()
            flow_op(context=context)

        except Exception as e:
            logger.exception(f"flow_name={self.name} encounter error={e.args}")
            context.add_response_error(e)

        return context.response
