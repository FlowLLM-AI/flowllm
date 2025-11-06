"""Generate system prompt operation for creating optimized system prompts."""

from loguru import logger

from ..core.context import C
from ..core.enumeration import Role
from ..core.op import BaseAsyncOp
from ..core.schema import Message
from ..core.utils import extract_content, format_messages


@C.register_op()
class GenSystemPromptOp(BaseAsyncOp):
    """Operation for generating optimized system prompts using LLM.

    This operation takes user query or messages and generates an optimized system
    prompt using an LLM. The generated prompt is extracted from the LLM response,
    which should contain think and prompt sections in markdown code blocks.
    """

    file_path: str = __file__

    def __init__(
        self,
        llm: str = "qwen3_30b_instruct",
        **kwargs,
    ):
        """Initialize the GenSystemPromptOp.

        Args:
            llm: Name of the LLM to use for prompt generation.
            **kwargs: Additional arguments passed to BaseAsyncOp.
        """
        super().__init__(llm=llm, **kwargs)

    async def async_execute(self):
        """Execute the system prompt generation.

        Reads query or messages from context, formats them, and uses LLM to generate
        an optimized system prompt. The prompt is extracted from the response and
        stored in context.system_prompt.
        """
        query = self.context.get("query")

        if query:
            messages = [Message(role=Role.USER, content=query)]

        else:
            messages = self.context.get("messages", [])
            if messages:
                messages = [Message(**x) for x in messages]

        assert messages, "Both `query` and `messages` are not provided!"
        self.context.messages = messages

        def callback_fn(message: Message):
            """Extract system prompt from LLM response.

            The LLM response should contain think and prompt sections in markdown code blocks.
            If extraction fails, fall back to the full message content.
            """
            think_content = extract_content(message.content, "think")
            prompt_content = extract_content(message.content, "prompt")

            logger.info(f"think_content={think_content}\nprompt_content={prompt_content}")

            # If prompt_content extraction failed, use the full message content as fallback
            if prompt_content is None:
                logger.warning("Failed to extract prompt from code block, using full message content")
                # Get content, handling both str and bytes
                content = message.content
                if isinstance(content, bytes):
                    content = content.decode("utf-8", errors="ignore")
                prompt_content = content.strip()

            return prompt_content

        user_prompt = self.prompt_format("gen_system_prompt_prompt", formated_messages=format_messages(messages))

        system_prompt = await self.llm.achat(
            messages=[Message(role=Role.USER, content=user_prompt)],
            tools=None,
            callback_fn=callback_fn,
        )
        self.context.system_prompt = system_prompt
