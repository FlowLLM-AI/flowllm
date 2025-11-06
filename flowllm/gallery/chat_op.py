"""LLM chat operation for interactive conversations with LLM."""

from loguru import logger

from ..core.context import C
from ..core.enumeration import Role
from ..core.op import BaseAsyncOp
from ..core.schema import Message


@C.register_op()
class ChatOp(BaseAsyncOp):
    """Operation for conducting chat conversations with LLM.

    This operation combines system prompt and user messages, sends them to the LLM,
    and stores the response in context.response.answer. It requires both messages
    and system_prompt to be present in the context.
    """

    file_path: str = __file__

    def __init__(
        self,
        llm: str = "qwen3_30b_instruct",
        **kwargs,
    ):
        """Initialize the ChatOp.

        Args:
            llm: Name of the LLM to use for chat.
            **kwargs: Additional arguments passed to BaseAsyncOp.
        """
        super().__init__(llm=llm, **kwargs)

    async def async_execute(self):
        """Execute the LLM chat operation.

        Combines system prompt and messages, sends to LLM, and stores the response
        in context.response.answer. Requires context.messages (list of Message) and
        context.system_prompt (str) to be set.
        """
        messages = self.context.messages
        assert isinstance(messages, list) and all(
            isinstance(m, Message) for m in messages
        ), "`messages` must be a list of Message objects!"

        system_prompt = self.context.system_prompt
        assert system_prompt, "`system_prompt` is required!"

        messages = [Message(role=Role.SYSTEM, content=system_prompt)] + messages
        logger.info(f"messages={messages}")

        response = await self.llm.achat(messages=messages, tools=None)
        assert isinstance(response, Message), "Response must be a Message object!"

        self.context.response.answer = response.content.strip()
