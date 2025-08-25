import dashscope

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "杭州明天天气是什么？"},
]
response = dashscope.Generation.call(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    api_key="sk-d5c95707168b43a59463efd7c025465f",
    model="qwen-plus",
    messages=messages,
    enable_search=True,
    result_format="message",
    search_options={
        "forced_search": True,  # Force web search
        "enable_source": True,  # Include search source information
        "enable_citation": False,  # Enable citation markers
        "search_strategy": "max"
    },
)
print(response)
print(response["output"]["choices"][0]["message"]["content"])
