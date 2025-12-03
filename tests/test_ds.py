import os

from openai import OpenAI

from flowllm.core.utils import load_env

load_env()

# 初始化OpenAI客户端
client = OpenAI(
    # 如果没有配置环境变量，请用阿里云百炼API Key替换：api_key="sk-xxx"
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

messages = [{"role": "user", "content": "你是谁"}]
completion = client.chat.completions.create(
    # 此处以 deepseek-v3.2-exp 为例，可按需更换模型名称为 deepseek-v3.1、deepseek-v3 或 deepseek-r1
    model="deepseek-v3.2-exp",
    messages=messages,
    # 通过 extra_body 设置 enable_thinking 开启思考模式，该参数仅对 deepseek-v3.2-exp 和 deepseek-v3.1 有效。deepseek-v3 和 deepseek-r1 设定不会报错
    extra_body={"enable_thinking": True},
    stream=True,
    stream_options={
        "include_usage": True
    },
)

reasoning_content = ""  # 完整思考过程
answer_content = ""  # 完整回复
is_answering = False  # 是否进入回复阶段
print("\n" + "=" * 20 + "思考过程" + "=" * 20 + "\n")

for chunk in completion:
    if not chunk.choices:
        print("\n" + "=" * 20 + "Token 消耗" + "=" * 20 + "\n")
        print(chunk.usage)
        continue

    delta = chunk.choices[0].delta

    # 只收集思考内容
    if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
        if not is_answering:
            print(delta.reasoning_content, end="", flush=True)
        reasoning_content += delta.reasoning_content

    # 收到content，开始进行回复
    if hasattr(delta, "content") and delta.content:
        if not is_answering:
            print("\n" + "=" * 20 + "完整回复" + "=" * 20 + "\n")
            is_answering = True
        print(delta.content, end="", flush=True)
        answer_content += delta.content
