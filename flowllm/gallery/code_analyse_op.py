"""Code analysis operation for traversing and analyzing code files.

This module provides the CodeAnalyseOp class which can traverse code files,
judge their relevance to a query, and produce explanations.

Example usage:
    flowllm backend=cmd \\
        cmd.flow="CodeAnalyseOp()" \\
        cmd.params.query="对话上下文(list of messages)超过一定长度后如何管理，保留关键代码" \\
        cmd.params.code_dir="/Users/yuli/workspace/gemini-cli/packages/core" \\
        cmd.params.file_suffix="ts,tsx" \\
        cmd.params.exclude_suffix="test.ts" \\
        cmd.params.output_dir="tmp"
"""

import json
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from ..core.context import C
from ..core.enumeration import Role
from ..core.op import BaseAsyncToolOp
from ..core.schema import Message, ToolCall
from ..core.utils.llm_utils import parse_message_by_keys


@C.register_op()
class CodeAnalyseOp(BaseAsyncToolOp):
    """Operation for analyzing code files with relevance judgment and explanations.

    This operation traverses code files in a directory, judges their relevance
    to a user query (if provided), and generates explanations. It supports
    filtering by file suffixes and excluding specific patterns.
    """

    file_path: str = __file__

    def __init__(
        self,
        llm: str = "qwen3_30b_instruct",
        max_chars_per_file: int = 30000,
        max_parallel_cnt: int = 4,
        **kwargs,
    ):
        super().__init__(llm=llm, **kwargs)
        self.max_chars_per_file = max_chars_per_file
        self.max_parallel_cnt = max_parallel_cnt

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "Traverse code files, judge relevance to a query, and produce explanations.",
                "input_schema": {
                    "query": {
                        "type": "string",
                        "description": "User question or task the code should address. "
                        "If empty, the code will be directly analyzed without relevance judgment.",
                        "required": False,
                    },
                    "code_dir": {
                        "type": "string",
                        "description": "Absolute path to the root directory of the code to inspect.",
                        "required": True,
                    },
                    "file_suffix": {
                        "type": "string",
                        "description": "File suffix to include when scanning, e.g. 'py'.",
                        "required": True,
                    },
                    "exclude_suffix": {
                        "type": "string",
                        "description": "File suffix to exclude when scanning, e.g. 'test.py'. "
                        "Multiple suffixes can be separated by commas.",
                        "required": False,
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Absolute path to the directory where analysis files will be written.",
                        "required": True,
                    },
                },
            },
        )

    async def async_execute(self):
        query: str = self.input_dict.get("query", "").strip()
        code_dir = Path(self.input_dict["code_dir"]).expanduser().resolve()
        output_dir = Path(self.input_dict["output_dir"]).expanduser().resolve()
        suffix_input = self.input_dict["file_suffix"].strip()
        suffix_tokens = [token.strip() for token in suffix_input.split(",") if token.strip()]
        normalized_suffixes = {token if token.startswith(".") else f".{token}" for token in suffix_tokens}

        if not normalized_suffixes:
            error_msg = f"file_suffix is empty or invalid: {suffix_input}"
            logger.error(error_msg)
            self.set_output(error_msg)
            return

        # 处理排除的后缀
        exclude_suffix_input = self.input_dict.get("exclude_suffix", "").strip()
        exclude_suffix_tokens = [token.strip() for token in exclude_suffix_input.split(",") if token.strip()]
        normalized_exclude_suffixes = {
            token if token.startswith(".") else f".{token}" for token in exclude_suffix_tokens
        }

        if not code_dir.exists() or not code_dir.is_dir():
            error_msg = f"code_dir does not exist or is not a directory: {code_dir}"
            logger.error(error_msg)
            self.set_output(error_msg)
            return

        output_dir.mkdir(parents=True, exist_ok=True)

        matching_files = [
            path
            for path in sorted(code_dir.rglob("*"))
            if path.is_file()
            and path.suffix in normalized_suffixes
            and not any(path.name.endswith(exclude_suffix) for exclude_suffix in normalized_exclude_suffixes)
        ]

        exclude_info = f" (excluding {sorted(normalized_exclude_suffixes)})" if normalized_exclude_suffixes else ""
        logger.info(
            f"{self.name}: Found {len(matching_files)} file(s) "
            f"with suffixes {sorted(normalized_suffixes)}{exclude_info}",
        )

        # 根据 query 是否为空选择不同的 prompt
        is_query_mode = bool(query)
        if is_query_mode:
            system_prompt = self.get_prompt("code_judge_system_prompt")
        else:
            system_prompt = self.get_prompt("code_analyse_system_prompt")

        max_parallel_cnt = max(1, self.max_parallel_cnt)
        for file_path in tqdm(matching_files):
            while len(self.task_list) >= max_parallel_cnt:
                await self.join_async_task()

            self.submit_async_task(
                self._process_single_file,
                file_path,
                code_dir,
                output_dir,
                query,
                system_prompt,
                is_query_mode,
            )

        await self.join_async_task()

    async def _process_single_file(
        self,
        file_path: Path,
        code_dir: Path,
        output_dir: Path,
        query: str,
        system_prompt: str,
        is_query_mode: bool,
    ):
        raw_content = file_path.read_text(encoding="utf-8", errors="ignore")

        truncated = len(raw_content) > self.max_chars_per_file
        snippet = raw_content[: self.max_chars_per_file]

        relative_path = str(file_path.relative_to(code_dir))

        # 根据模式选择不同的 user prompt
        if is_query_mode:
            user_prompt = self.prompt_format(
                "code_judge_user_prompt",
                query=query,
                file_path=str(file_path),
                relative_path=relative_path,
                truncated_flag="是" if truncated else "否",
                code_language=file_path.suffix.lstrip(".") or "text",
                code_content=snippet,
            )
        else:
            user_prompt = self.prompt_format(
                "code_analyse_user_prompt",
                file_path=str(file_path),
                relative_path=relative_path,
                truncated_flag="是" if truncated else "否",
                code_language=file_path.suffix.lstrip(".") or "text",
                code_content=snippet,
            )

        messages = [
            Message(role=Role.SYSTEM, content=system_prompt),
            Message(role=Role.USER, content=user_prompt),
        ]

        def parse_result(message: Message):
            content = message.content.strip()

            if is_query_mode:
                # 查询模式：需要判断相关性
                parsed = parse_message_by_keys(content, ["### think", "### result", "### explanation"])
                think_content = parsed.get("### think", "").strip()
                result_content = parsed.get("### result", "").strip()
                is_relevant: bool = "true" in result_content.lower()
                if is_relevant:
                    explanation_content = parsed.get("### explanation", "").strip()
                else:
                    explanation_content = ""
                return {
                    "is_relevant": is_relevant,
                    "think_content": think_content,
                    "explanation_content": explanation_content,
                }
            else:
                # 直接解读模式：不需要判断相关性，直接生成解释
                parsed = parse_message_by_keys(content, ["### think", "### explanation"])
                think_content = parsed.get("### think", "").strip()
                explanation_content = parsed.get("### explanation", "").strip()
                return {
                    "is_relevant": True,
                    "think_content": think_content,
                    "explanation_content": explanation_content,
                }

        parsed_result = await self.llm.achat(messages=messages, callback_fn=parse_result)
        logger.info(
            f"file_path={file_path} parsed_result={json.dumps(parsed_result, ensure_ascii=False, indent=2)}",
        )
        if not parsed_result["is_relevant"]:
            logger.info(f"{self.name}: File {relative_path} deemed not relevant.")
            return

        analysis_path = (output_dir / relative_path).with_suffix(".md")
        analysis_path.parent.mkdir(parents=True, exist_ok=True)

        # think = parsed_result["think_content"]
        explanation = parsed_result["explanation_content"]
        analysis_text = "\n\n".join(
            [
                str(file_path.absolute()),
                explanation,
            ],
        )
        analysis_path.write_text(analysis_text, encoding="utf-8")
