"""Token counting operation for calculating token usage in messages."""

from loguru import logger

from ..core.context import C
from ..core.op import BaseAsyncOp
from ..core.schema import Message


@C.register_op()
class TokenCountOp(BaseAsyncOp):
    """Operation for counting tokens in messages.

    This operation calculates the total number of tokens in the messages
    from the context using the configured token counter. The token count
    is logged and can be used for monitoring token usage in LLM operations.

    The operation requires messages to be present in the context. It uses
    the token counting backend configured in the LLM service configuration
    to accurately count tokens based on the model being used.
    """

    async def async_execute(self):
        """Execute the token counting operation.

        Reads messages from context, converts them to Message objects,
        calculates the token count using the configured token counter,
        and logs the result.

        Requires:
            context.messages: List of message dictionaries or Message objects
                to count tokens for.

        The token count result is logged at INFO level.
        """
        messages = [Message(**x) for x in self.context.messages]
        cnt = self.token_count(messages)
        logger.info(f"Token count result: {cnt}")
