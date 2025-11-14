## 异步 Op 中使用 LLM 和 Prompt 指南

这是一个完整的示例，展示如何在异步 Op 中使用 LLM 和 Prompt，包括 prompt 文件创建、格式化、LLM 调用以及响应处理。

---

### 完整示例

#### 1. Prompt 文件：`qa_op_prompt.yaml`

**文件命名规则**：Op 文件名 `qa_op.py` → Prompt 文件名 `qa_op_prompt.yaml`（放在同一目录）

```yaml
# Prompt 模板，使用 {variable_name} 进行变量替换
qa_prompt: |
  # Task
  Please answer the following question:
  {question}

  # Requirements
  1. Answer should be accurate and professional
  2. If you don't know, please be honest
  3. Answer should be concise and clear
  4. For complex questions, provide detailed explanations

# 多语言支持：通过 _zh 等后缀区分
qa_prompt_zh: |
  # 任务
  请回答以下问题：
  {question}

  # 要求
  1. 回答要准确、专业
  2. 如果不知道，请诚实说明
  3. 回答要简洁明了
  4. 如果问题复杂，可以提供详细解释
```

#### 2. Op 文件：`qa_op.py`

```python
from flowllm.core.context import C
from flowllm.core.op import BaseAsyncOp
from flowllm.core.schema import Message
from flowllm.core.enumeration import Role
from flowllm.main import FlowLLMApp
import asyncio
import json


@C.register_op()
class QAOp(BaseAsyncOp):
    file_path: str = __file__  # 必须设置，用于自动查找 prompt 文件

    async def async_execute(self):
        """执行问答逻辑"""
        # 1. 读取输入
        question = self.context.get("question", "")
        assert question, "question 不能为空"

        # 2. 渲染 prompt 模板
        # prompt_format 支持：变量替换：{question} 会被替换为实际值
        prompt = self.prompt_format("qa_prompt", question=question)

        # 3. 构建 messages
        # 可以添加 system prompt、对话历史等
        messages = [Message(role=Role.USER, content=prompt)]

        # 4. 定义 callback_fn 处理响应（可选）
        # 用于从 LLM 响应中提取或转换特定格式的内容
        def parse_response(message: Message) -> str:
            """处理 LLM 响应"""
            content = message.content.strip()

            # 如果需要 JSON 格式，尝试从响应中提取 JSON
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                json_str = content[start:end].strip()
                try:
                    # 验证 JSON 格式
                    json.loads(json_str)
                    return json_str
                except:
                    pass

            return content

        # 5. 调用 LLM
        # achat 支持：
        #   - messages: 消息列表
        #   - callback_fn: 响应处理函数（可选）
        #   - default_value: 失败时的默认值（可选）
        #   - enable_stream_print: 流式输出（可选）
        #   - tools: 工具调用（可选）
        response = await self.llm.achat(
            messages=messages,
            callback_fn=parse_response,
            default_value="抱歉，我无法回答这个问题")

        # 6. 获取响应内容
        # 如果使用了 callback_fn，response 是 callback_fn 的返回值
        # 否则 response 是 Message 对象，通过 response.content 获取内容
        if isinstance(response, Message):
            answer = response.content.strip()
        else:
            answer = response

        # 7. 写回输出
        self.context.response.answer = answer
        self.context["answer"] = answer  # 也可以写到 context 供其他 Op 使用

        return answer


# 使用示例
async def main():
    async with FlowLLMApp() as app:
        # 基本使用
        result = await QAOp().async_call(question="什么是 Python？")
        print(f"答案：{result}")

        # 使用自定义 LLM
        result2 = await QAOp(llm="qwen3_30b_instruct").async_call(
            question="什么是异步编程？"
        )
        print(f"答案：{result2}")

        # 使用条件标志和 callback_fn
        result3 = await QAOp().async_call(
            question="解释一下 Python 的装饰器",
            need_json=True
        )
        print(f"答案：{result3}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 关键要点

1. **Prompt 文件命名**：`xxx_op.py` → `xxx_prompt.yaml`，放在同一目录
2. **变量替换**：在 prompt 中使用 `{variable_name}`，调用 `prompt_format` 时传入对应变量
3. **多语言支持**：通过 `_zh`、`_en` 等后缀支持多语言 prompt，系统自动选择
4. **构建 Messages**：使用 `Message(role=Role.USER/SYSTEM/ASSISTANT, content=...)`
5. **调用 LLM**：使用 `await self.llm.achat(messages=messages, ...)`
6. **处理响应**：使用 `callback_fn` 处理或转换响应，返回处理后的结果
7. **应用上下文**：必须在 `FlowLLMApp()` 上下文里调用
8. **file_path**：Op 类中必须设置 `file_path = __file__`，用于自动查找 prompt 文件

---

### 参考示例

实际项目中的示例：

- `flowllm/flowllm/gallery/gen_system_prompt_op.py` - 使用 prompt 和 callback_fn 的完整示例
- `flowllm/flowllm/gallery/chat_op.py` - 简单的聊天 Op
- `flowllm/flowllm/gallery/mock_search_op.py` - 使用 callback_fn 解析 JSON 的示例

