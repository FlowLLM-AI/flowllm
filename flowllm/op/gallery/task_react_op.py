from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from loguru import logger

from flowllm.client.fastmcp_client import FastmcpClient as McpClient
from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.enumeration.chunk_enum import ChunkEnum
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message
from flowllm.schema.message import Role
from flowllm.schema.tool_call import ToolCall


def tools_schema_to_qwen_prompt(tools_schema: List[ToolCall]):
    """
    将 tools_schema 转换为符合 Qwen 模型 chat_template 的工具描述 prompt。

    Args:
        tools_schema (list): 工具列表，格式如下：
            [
                {
                    "name": "tool_name",
                    "description": "工具描述",
                    "parameters": {
                        "type": "object",
                        "properties": { ... },
                        "required": [ ... ]
                    }
                }
            ]

    Returns:
        str: 包含 <tools> 标签的完整 system 工具描述 prompt
    """
    if not tools_schema:
        return ""

    lines = []
    # lines.append("\n\n# Tools\n")
    lines.append("You may call one or more functions to assist with the user query.\n")
    lines.append("You are provided with function signatures within <tools></tools> XML tags:")
    lines.append("<tools>")
    # 逐个添加工具定义（JSON 格式，不转义）
    for tool in tools_schema:
        tool_json = tool.simple_input_dump()
        tool_json = json.dumps(
            tool_json,
            ensure_ascii=False,
            separators=(',', ':')  # 紧凑格式，不加空格
        )
        lines.append(tool_json)
    lines.append("</tools>\n")
    lines.append("For each function call, return a json object with function name and arguments within <tool_call> and <tool_call> XML tags:")
    lines.append("<tool_call>")
    lines.append('{\"name\": <function-name>, \"arguments\": <args-json-object>}')
    lines.append("</tool_call>")

    return "\n".join(lines)


from typing import Any, Dict, List
def parse_tool_calls(text: str):
    """
    从包含 <tool_call>...</tool_call> 的文本中解析工具调用信息。

    返回:
      calls:       按出现顺序的调用列表，元素形如 {"name": str, "arguments": Any}
    """
    # 提取每个 <tool_call> 块中包裹的 JSON（允许跨行）
    pattern = re.compile(r"<tool_call>\s*({.*?})\s*</tool_call>", re.DOTALL)
    json_blobs = pattern.findall(text)

    calls = []
    for blob in json_blobs:
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError:
            # 无法解析的块直接跳过
            continue

        name = obj.get("name")
        arguments = obj.get("arguments")
        if name is None:
            # 必须有 name 字段
            continue
        tool_call_dict = {"name": name, "arguments": arguments}

        calls.append(tool_call_dict)

    return calls

import re
import json
from typing import Tuple

def parse_final_query_and_type(text: str) -> Tuple[str, str]:
    """
    从包含 <answer> ... </answer> 的字符串中解析出 final_query 与 type。
    返回 (final_query, type)。解析失败会抛出 ValueError。
    """
    # 1) 提取 <answer>...JSON...</answer> 内的内容
    m = re.search(r"<answer>\s*(\{.*?\})\s*</answer>", text, flags=re.S | re.I)
    if not m:
        raise ValueError("未找到 <answer> ... </answer> 块")

    json_str = m.group(1).strip()

    # 2) 解析 JSON
    try:
        obj = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e.msg}") from e

    # 3) 取字段并做校验
    if not isinstance(obj, dict):
        raise ValueError("answer 块不是一个 JSON 对象")
    if "final_query" not in obj or "type" not in obj or "simplified_query" not in obj:
        raise ValueError("JSON 中缺少 final_query, simplified_query 或 type 字段")

    return obj


def print_message_list(messages, *, max_content_chars: int = 800):
    """Pretty-print a list of FlowLLM `Message` objects.

    - Safely handles Role enums and missing fields
    - Displays tool calls with parsed JSON arguments (when possible)
    - Truncates long content to `max_content_chars`
    """
    import json as _json

    divider = "-" * 60
    print("=" * 60)
    for i, m in enumerate(messages):
        role = getattr(m, "role", None)
        role_str = getattr(role, "value", str(role))
        time_created = getattr(m, "time_created", None) or "-"
        print(f"[{i}] role={role_str} time={time_created}")

        def _emit(label: str, text: str):
            if not text:
                return
            if max_content_chars and len(text) > max_content_chars:
                text = text[: max_content_chars] + "…"
            print(f"  {label}: {text}")

        _emit("content", getattr(m, "content", ""))
        _emit("reasoning", getattr(m, "reasoning_content", ""))

        tool_calls = getattr(m, "tool_calls", None) or []
        if tool_calls:
            print(f"  tool_calls ({len(tool_calls)}):")
            for tc in tool_calls:
                # Support both direct fields and tc.function.* shape
                name = getattr(tc, "name", None)
                _type = getattr(tc, "type", None) or "function"
                tc_id = getattr(tc, "id", "")
                args = getattr(tc, "arguments", {})

                fn = getattr(tc, "function", None)
                if fn and not name:
                    name = getattr(fn, "name", None)
                    args = getattr(fn, "arguments", args)

                if isinstance(args, str):
                    try:
                        args_fmt = _json.dumps(_json.loads(args), ensure_ascii=False)
                    except Exception:
                        args_fmt = args
                else:
                    try:
                        args_fmt = _json.dumps(args, ensure_ascii=False)
                    except Exception:
                        args_fmt = str(args)

                print(f"    - {_type} {name} id={tc_id}")
                if args_fmt:
                    print(f"      args: {args_fmt}")

        tool_call_id = getattr(m, "tool_call_id", "")
        if tool_call_id:
            print(f"  tool_call_id: {tool_call_id}")

        metadata = getattr(m, "metadata", None)
        if metadata:
            try:
                meta_str = _json.dumps(metadata, ensure_ascii=False)
            except Exception:
                meta_str = str(metadata)
            print(f"  metadata: {meta_str}")

        print(divider)


# -------------------- 序列化 & 写入工具 --------------------
def serialize_message(msg: Message) -> Dict[str, Any]:
    """把 SDK 的 Message 转成可 JSON 序列化的简洁结构。"""
    return {
        "role": getattr(msg, "role", None),
        "content": getattr(msg, "content", None),
    }

def serialize_trajectory(history: List[Message]) -> List[Dict[str, Any]]:
    return [serialize_message(m) for m in history]

def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()

def load_existing_queries_from_jsonl(
    path: str,
    field: str = "final_query",
):
    """
    读取 jsonl 文件，顺序返回已存在的 `final_query` 列表（去掉 None/空字符串）。
    若文件不存在，返回空列表。
    """
    exists: List[str] = []
    if not os.path.exists(path):
        return exists
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            val = obj.get(field)
            if isinstance(val, str) and val.strip():
                exists.append(val.strip())
    return exists

TASK_AGENT_PROMPT = """
你是一个【任务生成智能体】，目标是在了解一个特定的智能体应用（下称“目标 Agent”）及其可用工具后，先探索再出题，最后仅输出一个高质量模拟用户问题（Task/Query），供训练该“目标 Agent”使用。

当前时间: {time_stamp}

[输入]
1) 目标 Agent 应用描述：
{application_description}
2) 可用工具：
{tools}
3) 题目范围与类型（可选）：
{topic}
4) 已存在的题目（请勿生成重复问题）：
{exist_tasks}

[你的任务]
A. 构思：你必须从构思开始，根据“应用描述+范围”，在草稿中列出 1-3 个潜在出题方向，也可以通过热点搜索来确定方向。
B. 探索：**按需**调用工具（0–N 次均可），以提升问题质量与可回答性。你可以自由决定调用顺序与组合。
C. 迭代：交替进行“构思 ⇄ 探索”，收敛并打磨问题，使其：
   - 清晰、具体、可被目标 Agent 在其工具边界内解答；
   - 明确必要上下文，但不要过多或过于具体（具体信息需要目标Agent在解答时自行收集）；
   - 具训练价值（避免过宽或一搜即得；鼓励结构化信息需求与可检验标准）。
D. 输出：仅产出一个问题（必要）；可附元数据（可选）.

[工具使用——灵活指引（非强制，供你自由选择与组合）]
- 热点捕捉：检索最近一段时间（如近 7–30 天）与主题相关的新闻/事件/政策，识别可转化为问题的变化点或冲突点。
- 实时脉冲：对涉时效主题，拉取最新关键数据点（如 CPI/利率/价格/产能），并在问题中固化时间点或区间。
- 口径校准：当问题涉及统计口径/定义（如 TTM/年度、含税口径、地区边界）时，做一次轻量确认以避免歧义。
- 范围界定：需要对比时，生成候选实体清单（公司/子行业/指标），并据此在问题里限定范围或点名对象。
- 证据线索：为后续回答留出可验证的证据维度（来源类型/指标表/公告字段），但不要在输出中暴露任何工具细节。
- 细化与降噪：若发现问题过宽或不可答，借助工具结果收缩到可操作的时间窗、对象清单、指标集合或假设边界。
- 失败降级：工具不可用/受限时，改写为无需实时数据也能回答的版本（例如改为区间回溯、方法论对比或结构化框架题）。

[注意事项]
1. 你有完全的调用自主权：是否调用、调用多少次、调用哪个工具、以何种顺序，都由你决定。
2. 优先以更好问题为目标，而非收集更多信息；在最少必要信息下形成可执行、可检验的问题陈述。
3. 注意生成问题的多样性，不限于内容、问法等方面。
4. 合规边界（必要）：不得诱导违法/不当请求，不得要求内幕信息或操纵市场；避免侵犯隐私；避免医疗/法律等高风险建议的结论性指令；如使用时效数据，仅作构题的合理事实校验，并在问题中固化时间点或区间。

[输出格式]
在**最终问题尚未确定之前**：请先以如下格式输出思考过程，并适当调用工具。
<think> 思考过程 </think><tool_call> 工具调用 </tool_call>
**当且仅当**你已确定最终问题后，输出以下格式的JSON对象。
<answer>
{{
  "final_query": "<给出的单个高质量问题，1–2句>",
  "simplified_query": "<final_query的简化版，只做措辞压缩，不要丢失关键主体信息，1句>",
  "type": "<问题种类，具体选项参考目标应用描述>"
}}
</answer>

[严格要求]
- 如果探索表明问题过于宽泛或不可答，请主动收敛并补充限定。
- 若涉及时效性数据，请在问题中明确时间点或区间（示例：“截至 2025-06 的…”、“2023Q4–2025Q2”）。
- 如工具不可用或超时，必须进行范围收缩或改写为无需实时数据亦可回答的问题。
"""


FIN_DEEPRESEARCH_DESCRIPTION = """
【应用名称】金融 deepresearch
【使命】
以有洞察力、可复核、可落地的研究框架回答金融相关问题，覆盖行业研究、事件解读、个股分析、宏观分析与股票检索五大场景。
【覆盖场景与示例】
1) 行业研究
   - 中国电解铝是否具备中长期投资价值？核心标的与优劣对比
   - 磷化工/氟化工竞争格局与胜出因子，优选公司及理由
   - 半导体上行期，“铲子股”vs“耗材股”的取舍与公司推荐
   - 上市黄金企业的储量、成本与估值梳理；优选标的
   - 快递行业竞争态势与龙头护城河评估
2) 事件解读
   - 最近一次美国CPI结构拆解及对资产定价/风格的影响
   - “反内卷”导向对高竞争行业盈利与估值的影响
   - 外卖补贴战对三家平台估值的分化路径
   - 关税政策变化的受益板块与A股映射
   - 宠物经济兴起的底层动因与可投资标的
   - 阶段性A股上涨的驱动因素剖析
3) 个股分析
   - 紫金矿业增长的可持续性与边际驱动
   - 海尔估值合理性与同业对标
   - 申通快递相对同业的优势/劣势与催化
   - 藏格矿业、赤峰黄金的股价驱动因素
   - 中宠股份在当前价位的性价比评估
4) 宏观分析
   - 利率下行对大宗商品的影响路径与机会
   - 社零与工业数据对风格与板块轮动的含义
   - 全球实际利率中枢对权益估值的作用
   - 名义增速缺口对沪深300的影响量化
   - 股债利差/倒挂对A股风险偏好的影响
   - 上证指数突破关键位所需条件复盘
5) 股票检索（情报/线索）
   - 海外油服设备供应商认证与相关企业清单
   - 在越南有产能布局的A股出口公司盘点
   - 关税重构背景下“铲子”赛道受益环节与公司列表
   - 电力/电气设备领域具寡头力的出海企业
   - 汽车产业链全球化龙头与品牌出海的产品型公司
"""


# -------------------- Batch item --------------------
@dataclass
class BatchItem:
    topic: str


# -------------------- Op: TaskReActOP (Agent merged into Op) --------------------
@C.register_op()
class TaskReactOp(BaseAsyncToolOp):

    def __init__(
        self,
        llm: str = "qwen3_max_instruct",
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(llm=llm, **kwargs)
        self.system_prompt = system_prompt

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "description": "Run dedup batch of Task ReAct agents and stream results (Agent merged). Provide exist_list to dedup; no jsonl read.",
            "input_schema": {
                "items": {
                    "type": "array",
                    "description": "list of objects with field 'topic'",
                    "required": True
                },
                "exist_list": {
                    "type": "array",
                    "description": "existing simplified queries to deduplicate against",
                    "required": False
                },
                "jsonl_path": {
                    "type": "string",
                    "description": "path to append results jsonl",
                    "required": False
                },
                "mcp_transport": {"type": "string", "required": False},
                "mcp_host": {"type": "string", "required": False},
                "mcp_port": {"type": "integer", "required": False},
                "max_steps": {"type": "integer", "required": False},
                "dedup_field": {"type": "string", "required": False},
                "exist_task_prompt_limit": {"type": "integer", "required": False},
                "per_item_timeout": {"type": "number", "required": False},
                "include_trajectory": {"type": "boolean", "required": False},
            }
        })

    # -------------------- Agent logic (as a helper method) --------------------
    async def _agent_execute(
        self,
        input_topic: str,
        *,
        mcp: McpClient,
        max_steps: int = 30,
        stream: bool = False,
        exist_tasks: Optional[List[str]] = None,
        max_tool_result_char: int = int(5e4),
    ) -> Dict[str, Any]:
        """
        Agent logic merged into the Op as a coroutine method. LLM calls remain non-streaming per requirement.
        Returns final_query_and_type with trajectory.
        """
        # llm = OpenAICompatibleBaseLLM(model_name=self.model_name)

        # 1) 读取可用工具
        tools_schema = await mcp.list_tool_calls() or []
        tools_prompt = tools_schema_to_qwen_prompt(tools_schema)

        # 2) 最小对话历史
        task_prompt = TASK_AGENT_PROMPT.format(
            time_stamp=datetime.now().strftime("%Y%m%d-%H%M%S"),
            application_description=FIN_DEEPRESEARCH_DESCRIPTION,
            tools=tools_prompt,
            topic=input_topic,
            exist_tasks=json.dumps(exist_tasks or [], ensure_ascii=False),
        )

        history: List[Message] = []
        if self.system_prompt:
            history.append(Message(role=Role.SYSTEM, content=self.system_prompt))
        history.append(Message(role=Role.USER, content=task_prompt))

        last_reply: Optional[Message] = None
        final_query_and_type: Dict[str, Any] = {}

        # 3) 多步循环
        for step_idx in range(1, max_steps + 1):
            last_reply = await self.llm.achat(
                history,
                [],
                enable_stream_print=stream,
            )
            history.append(last_reply)

            content = getattr(last_reply, "content", None) or []
            await self.context.add_stream_chunk_and_type(
                    chunk=json.dumps({"event": "llm", "content": content}, ensure_ascii=False),
                    chunk_type=ChunkEnum.THINK,
                )
            tool_calls = parse_tool_calls(content)

            if not tool_calls:
                final_query_and_type = parse_final_query_and_type(content) or {}
                break

            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("arguments")
                if not name:
                    continue

                try:
                    result = await mcp.call_tool(name, args)

                    text = None
                    if getattr(result, "content", None):
                        try:
                            text = result.content[0].text
                        except Exception:
                            text = str(result.content)
                    if not text and getattr(result, "structured_content", None):
                        text = json.dumps(result.structured_content, ensure_ascii=False)
                    if not text:
                        text = str(result)

                    if isinstance(text, str) and len(text) > max_tool_result_char:
                        text = text[:max_tool_result_char] + "...[truncated]"

                    history.append(
                        Message(
                            role=Role.USER,
                            content=f"[tool:{name}]" + text,
                        )
                    )
                except Exception as e:
                    history.append(
                        Message(
                            role=Role.USER,
                            content=f"[tool:{name}] 调用失败: {e}",
                        )
                    )

        if not final_query_and_type:
            content = getattr(last_reply, "content", None) or []
            final_query_and_type = parse_final_query_and_type(content) or {}

        final_query_and_type.update({"trajectory": history})
        return final_query_and_type

    # -------------------- Main Op execution --------------------
    async def async_execute(self):
        # parse inputs
        items_raw = self.input_dict.get("items")
        if not items_raw:
            raise RuntimeError("'items' is required")

        items = [BatchItem(**x) if isinstance(x, dict) else BatchItem(topic=str(x)) for x in items_raw]

        # New: accept exist_list directly and do not read jsonl to load history
        provided_exist_list = self.input_dict.get("exist_list")
        if provided_exist_list is None:
            existed_list: List[str] = []
        else:
            # ensure strings
            existed_list = [str(x) for x in provided_exist_list]

        mcp_transport = self.input_dict.get("mcp_transport", "sse")
        mcp_host = self.input_dict.get("mcp_host", "0.0.0.0")
        mcp_port = int(self.input_dict.get("mcp_port", 8001))
        max_steps = int(self.input_dict.get("max_steps", 30))
        exist_task_prompt_limit = int(self.input_dict.get("exist_task_prompt_limit", 500))
        per_item_timeout = self.input_dict.get("per_item_timeout", 300.0)
        include_trajectory = bool(self.input_dict.get("include_trajectory", True))

        # prepare dedup / history
        logger.info(f"existed_list length={len(existed_list)}")
        exist_tasks_for_prompt = existed_list[-exist_task_prompt_limit:]

        # Open MCP once
        async with McpClient(transport=mcp_transport, host=mcp_host, port=mcp_port) as mcp:
            for idx, item in enumerate(items, 1):
                topic = item.topic
                logger.info(f"[Op-Batch-Dedup] ({idx}/{len(items)}) topic={topic!r}")

                # stream: notify start of item
                await self.context.add_stream_chunk_and_type(
                    chunk=json.dumps({"event": "start_item", "index": idx, "total": len(items), "topic": topic}, ensure_ascii=False),
                    chunk_type=ChunkEnum.THINK,
                )

                # run merged agent under timeout
                task = asyncio.create_task(
                    self._agent_execute(
                        topic,
                        mcp=mcp,
                        max_steps=max_steps,
                        stream=False,
                        exist_tasks=exist_tasks_for_prompt,
                    )
                )

                try:
                    if per_item_timeout is not None and per_item_timeout > 0:
                        result = await asyncio.wait_for(task, timeout=per_item_timeout)
                    else:
                        result = await task

                    # dedup check
                    simplified = result.get("simplified_query")

                    record: Dict[str, Any] = {
                        "event": "end_item",
                        "input_topic": topic,
                        "final_query": result.get("final_query"),
                        "simplified_query": result.get("simplified_query"),
                        "type": result.get("type"),
                        "ts": datetime.now().isoformat(timespec="seconds"),
                    }
                    if include_trajectory:
                        record["trajectory"] = serialize_trajectory(result.get("trajectory", []))


                    if simplified is not None:
                        existed_list.append(simplified)
                        exist_tasks_for_prompt.append(simplified)
                        if len(exist_tasks_for_prompt) > exist_task_prompt_limit:
                            exist_tasks_for_prompt = exist_tasks_for_prompt[-exist_task_prompt_limit:]

                    # stream final_query as ANSWER chunk
                    await self.context.add_stream_chunk_and_type(
                        chunk=json.dumps(record, ensure_ascii=False),
                        chunk_type=ChunkEnum.ANSWER,
                    )

                except asyncio.TimeoutError:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task

                    err_msg = f"timeout after {per_item_timeout}s"
                    await self.context.add_stream_chunk_and_type(
                        chunk=json.dumps({"event": "error", "topic": topic, "error": err_msg}, ensure_ascii=False),
                        chunk_type=ChunkEnum.ERROR,
                    )

                except Exception as e:
                    await self.context.add_stream_chunk_and_type(
                        chunk=json.dumps({"event": "error", "topic": topic, "error": str(e)}, ensure_ascii=False),
                        chunk_type=ChunkEnum.ERROR,
                    )



async def main():
    from flowllm.app import FlowLLMApp
    async with FlowLLMApp(load_default_config=True):

        context = FlowContext(items=["",""], stream_queue=asyncio.Queue())
        op = TaskReactOp()
        async def async_call():
            await op.async_call(context=context)
            await context.add_stream_done()

        task = asyncio.create_task(async_call())

        while True:
            stream_chunk = await context.stream_queue.get()
            if stream_chunk.done:
                print("\nend")
                await task
                break
            else:
                print(stream_chunk.chunk, end="")

        await task


if __name__ == "__main__":
    asyncio.run(main())