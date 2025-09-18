from openai import OpenAI

"""
export CUDA_VISIBLE_DEVICES=1,2
python -m vllm.entrypoints.openai.api_server \
    --model /mnt/data_cpfs/xielipeng.xlp/models/Qwen3-8B \
    --served-model-name Qwen3-8B \
    --host 0.0.0.0 \
    --port 8010 \
    --tensor-parallel-size 2 \
    --max-model-len 40960

curl --location 'http://8.130.105.202:8010/v1/chat/completions' \
    --header 'Content-Type: application/json'                      \
    --data '{
        "model" : "Qwen3-8B",
        "messages" : [
            {"role": "system", "content": "You are a helpful assistant."}, 
            {"role": "user", "content": "what is your name?"}
        ]
    }'
"""

try:
    client = OpenAI(
        base_url="http://8.130.105.202:8010/v1",
        api_key="",
    )

    completion = client.chat.completions.create(
        model="Qwen3-8B",  # 模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': '你是谁？'}
        ]
    )
    print(completion.choices[0].message.content)
except Exception as e:
    print(f"错误信息：{e}")
    print("请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code")
