import asyncio
from abc import ABC
from functools import partial
from typing import Union, Optional

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_async_op import BaseAsyncOp
from flowllm.op.base_op import BaseOp
from flowllm.op.parallel_op import ParallelOp
from flowllm.op.sequential_op import SequentialOp
from flowllm.schema.flow_response import FlowResponse
from flowllm.schema.flow_stream_chunk import FlowStreamChunk
from flowllm.utils.common_utils import camel_to_snake


class BaseFlow(ABC):

    def __init__(self,
                 name: str = "",
                 stream: bool = False,
                 **kwargs):
        self.name: str = name or camel_to_snake(self.__class__.__name__)
        self.stream: bool = stream
        self.flow_params: dict = kwargs

        self._flow_op: Optional[BaseOp] = None
        self.flow_printed: bool = False

    @property
    def async_mode(self) -> bool:
        return self.flow_op.async_mode

    def build_flow(self) -> BaseOp:
        ...

    @property
    def flow_op(self):
        if self._flow_op is None:
            self._flow_op = self.build_flow()
        return self._flow_op

    def print_flow(self):
        if not self.flow_printed:
            logger.info(f"---------- start print flow={self.name} ----------")
            self._print_operation_tree(self.flow_op, indent=0)
            logger.info(f"---------- end print flow={self.name} ----------")
            self.flow_printed = True

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
                logger.info(f"{prefix} Step {i + 1}:")
                self._print_operation_tree(sub_op, indent + 2)

        elif isinstance(op, ParallelOp):
            logger.info(f"{prefix}Parallel Execution:")
            for i, sub_op in enumerate(op.ops):
                logger.info(f"{prefix} Branch {i + 1}:")
                self._print_operation_tree(sub_op, indent + 2)

        else:
            logger.info(f"{prefix}Operation: {op.name}")
            if op.ops:
                for i, sub_op in enumerate(op.ops):
                    logger.info(f"{prefix} Sub {i + 1}:")
                    self._print_operation_tree(sub_op, indent + 2)

    async def async_call(self, **kwargs) -> Union[FlowResponse | FlowStreamChunk | None]:
        self.print_flow()

        kwargs["stream"] = self.stream
        context = FlowContext(**kwargs)
        logger.info(f"request.params={kwargs}")

        try:
            # each time rebuilding
            flow_op: BaseOp = self.build_flow()

            if self.async_mode:
                assert isinstance(flow_op, BaseAsyncOp)
                await flow_op.async_call(context=context)

            else:
                loop = asyncio.get_event_loop()
                op_call_fn = partial(flow_op.call, context=context)
                await loop.run_in_executor(executor=C.thread_pool, func=op_call_fn)  # noqa

            if self.stream:
                await context.add_stream_done()

        except Exception as e:
            logger.exception(f"flow_name={self.name} async call encounter error={e.args}")

            if self.stream:
                await context.add_stream_error(e)
            else:
                context.add_response_error(e)

        if self.stream:
            return context.stream_queue
        else:
            return context.response

    def call(self, **kwargs) -> FlowResponse:
        self.print_flow()

        kwargs["stream"] = self.stream
        context = FlowContext(**kwargs)
        logger.info(f"request.params={kwargs}")

        try:
            # each time rebuilding
            flow_op: BaseOp = self.build_flow()

            if self.async_mode:
                assert isinstance(flow_op, BaseAsyncOp)
                asyncio.run(flow_op.async_call(context=context))

            else:
                flow_op.call(context=context)

        except Exception as e:
            logger.exception(f"flow_name={self.name} call encounter error={e.args}")
            context.add_response_error(e)

        return context.response
