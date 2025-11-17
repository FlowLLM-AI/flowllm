"""Simple script to exercise OpenAIToken.token_count."""

from flowllm.core.enumeration import Role
from flowllm.core.schema import Message


def main():
    """Create a couple of messages and print their token usage."""

    # from flowllm.core.token import OpenAIToken
    # token_counter = OpenAIToken(model_name="gpt-4o-mini")

    from flowllm.core.token import HuggingFaceToken

    token_counter = HuggingFaceToken(use_mirror=True, model_name="Qwen/Qwen3-Next-80B-A3B-Instruct")

    messages = [
        Message(role=Role.SYSTEM, content="你是一个乐于助人的助手。"),
        Message(role=Role.USER, content="请简单回答：token计数好吗？"),
    ]
    count = token_counter.token_count(messages=messages)
    print(f"Token count result: {count}")


if __name__ == "__main__":
    main()
