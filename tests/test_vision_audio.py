"""Test script for vision and audio capabilities with OpenAI-compatible LLM."""

import base64

from flowllm.core.llm import OpenAICompatibleLLM
from flowllm.core.schema import Message


def run_sync_openai_image():
    """Test image understanding with Qwen VL model."""

    def encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    # 将xxxx/eagle.png替换为你本地图像的绝对路径
    base64_image = encode_image("/Users/yuli/Documents/20251128144329.jpg")

    llm = OpenAICompatibleLLM(model_name="qwen3-vl-plus")
    messages = [
        Message(
            **{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            # "url": "https://img.alicdn.com/imgextra/
                            # i1/O1CN01gDEY8M1W114Hi3XcN_!!6000000002727-0-tps-1024-406.jpg"
                            "url": f"data:[image/jpeg];base64,{base64_image}",
                        },
                    },
                    # {"type": "text", "text": "这道题怎么解答？"},
                    {"type": "text", "text": "看看用户在干什么？"},
                ],
            },
        ),
    ]

    print(messages)

    print(llm.chat(messages, enable_stream_print=True))


def run_sync_openai_audio():
    """Test audio understanding with Qwen Omni model."""

    def encode_audio(audio_path):
        with open(audio_path, "rb") as audio_file:
            return base64.b64encode(audio_file.read()).decode("utf-8")

    # 请将 ABSOLUTE_PATH/welcome.mp3 替换为本地音频的绝对路径
    audio_file_path = "/Users/yuli/Documents/111.wav"
    base64_audio = encode_audio(audio_file_path)

    messages = [
        Message(
            **{
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            # "data": "https://help-static-aliyun-doc.aliyuncs.com/
                            # file-manage-files/zh-CN/20250211/tixcef/cherry.wav",
                            "data": f"data:;base64,{base64_audio}",
                        },
                    },
                    {
                        "type": "text",
                        "text": '这段音频在说什么? 语气是什么样的？以json格式输出{"content": "", "tone": ""}',
                    },
                ],
            },
        ),
    ]
    llm = OpenAICompatibleLLM(model_name="qwen3-omni-flash")

    print(llm.chat(messages, enable_stream_print=True))


if __name__ == "__main__":
    run_sync_openai_image()
    run_sync_openai_audio()
