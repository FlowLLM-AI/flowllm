import os
from openai import OpenAI
import base64
from flowllm.utils.common_utils import load_env
load_env()

#  编码函数： 将本地文件转换为 Base64 编码的字符串
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# 将xxxx/eagle.png替换为你本地图像的绝对路径
# base64_image = encode_image("/Users/yuli/Documents/20250924133208.jpg")
base64_image = encode_image("/Users/yuli/Documents/20250924133848.jpg")

client = OpenAI(
    # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    api_key=os.getenv("FLOW_LLM_API_KEY"),
    # 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：https://dashscopep-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

messages = [
       {"role":"system","content":[{"type": "text", "text": "You are a helpful assistant."}]},
       {"role": "user","content": [
           # JPEG图像： f"data:image/jpeg;base64,{base64_image}"
           {"type": "image_url","image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},},
           {"type": "text", "text": "这些图描绘了什么内容，简单介绍下，同时推理用户正在干什么？一句话总结"},
            ],
        }
    ]

completion = client.chat.completions.create(
    model="qwen3-vl-235b-a22b-instruct", # 此处以qwen-vl-max-latest为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/models
    messages=messages,
)

print(completion.choices[0].message.content)