import asyncio
import json
from pathlib import Path
from typing import List, Dict, Tuple

from loguru import logger
from tqdm.asyncio import tqdm_asyncio

from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.message import Message, Role
from flowllm.schema.tool_call import ToolCall, ParamAttrs
from flowllm.utils.common_utils import extract_content


@C.register_op(register_app="FlowLLM")
class TranslateCodeOp(BaseAsyncToolOp):
    """
    TranslateCodeOp - TypeScript/TSX to Python Translation/Interpretation Operator
    
    This operator recursively finds all TypeScript (.ts) and TSX (.tsx) files in a given directory and:
    - mode=True: Translates them to Python (saved to *_python directory with .py extension)
    - mode=False: Interprets/explains them as markdown (saved to *_markdown directory with .md extension)
    
    Uses LLM with concurrent processing (pool size: 6).
    """
    file_path: str = __file__

    def __init__(self,
                 # llm="qwen3_max_instruct",
                 llm="qwen3_30b_instruct",
                 max_concurrent: int = 6,
                 max_retries: int = 3,
                 skip_existing: bool = True,
                 submit_interval: float = 2.0,
                 enable_print_output: bool = False,
                 **kwargs):
        """
        Initialize TranslateCodeOp
        
        Args:
            max_concurrent: Maximum number of concurrent LLM calls (default: 6)
            max_retries: Maximum number of retries for failed translations (default: 3)
            skip_existing: Skip if target file already exists and is not empty (default: True)
            submit_interval: Interval in seconds between submitting concurrent tasks (default: 2.0)
        """
        super().__init__(llm=llm, enable_print_output=enable_print_output, **kwargs)
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.skip_existing = skip_existing
        self.submit_interval = submit_interval
        self.semaphore = None  # Will be initialized in async_execute

    def build_tool_call(self) -> ToolCall:
        """Build tool call schema for TranslateCodeOp"""
        return ToolCall(**{
            "name": "translate_code",
            "description": "Recursively find all TypeScript (.ts) and TSX (.tsx) files in a directory and translate/interpret them",
            "input_schema": {
                "file_path": ParamAttrs(
                    type="str",
                    description="The directory path(s) to search for TypeScript/TSX files. Multiple paths can be separated by semicolons (;)",
                    required=True
                ),
                "mode": ParamAttrs(
                    type="bool",
                    description="True = translate to Python (saved to *_python/*.py), False = interpret to markdown (saved to *_markdown/*.md)",
                    required=False
                )
            }
        })

    async def async_execute(self):
        """
        Main execution method
        
        Steps:
        1. Get the input file path(s) and mode from context (supports multiple paths separated by semicolons)
        2. Recursively find all .ts and .tsx files in all paths
        3. Translate/interpret each file concurrently with pool size limit
        4. Return translation results
        """
        # Get input file path(s)
        file_path: str = self.input_dict.get("file_path", "")
        if not file_path:
            raise ValueError("file_path is required")
        
        # Get mode from input_dict (default: True for translation)
        mode = self.input_dict.get("mode", True)

        # Split paths by semicolon and strip whitespace
        file_paths = [path.strip() for path in file_path.split(';') if path.strip()]
        mode_str = "Translation" if mode else "Interpretation"
        logger.info(f"Mode: {mode_str}")
        logger.info(f"Processing {len(file_paths)} path(s): {file_paths}")

        # Initialize semaphore for concurrent control
        self.semaphore = asyncio.Semaphore(self.max_concurrent)

        # Find all TypeScript and TSX files recursively from all paths
        ts_files = []
        for path in file_paths:
            files = self._find_ts_files(path)
            ts_files.extend(files)
            logger.info(f"Found {len(files)} TypeScript/TSX files in {path}")

        # Remove duplicates while preserving order
        seen = set()
        unique_ts_files = []
        for file in ts_files:
            if file not in seen:
                seen.add(file)
                unique_ts_files.append(file)
        ts_files = unique_ts_files

        logger.info(f"Total: {len(ts_files)} unique TypeScript/TSX files")

        if not ts_files:
            result = {
                "status": "success",
                "message": f"No TypeScript/TSX files found in the specified path(s)",
                "paths": file_paths,
                "translations": []
            }
            self.set_result(json.dumps(result, ensure_ascii=False, indent=2))
            return

        # Analyze file statistics before translation
        file_stats = self._analyze_file_statistics(ts_files)
        logger.info(f"\n{'='*60}\nTypeScript Files Statistics:\n{'='*60}")
        logger.info(f"Total files: {file_stats['total_files']}")
        logger.info(f"Total characters: {file_stats['total_chars']:,}")
        logger.info(f"Average characters per file: {file_stats['avg_chars']:.2f}")
        logger.info(f"Median characters: {file_stats['median_chars']:,}")
        logger.info(f"\nTop 5 Largest Files:")
        for i, (file_path, chars) in enumerate(file_stats['top_5_largest'], 1):
            logger.info(f"  {i}. {file_path} - {chars:,} chars")
        logger.info(f"{'='*60}\n")

        # Create a mapping from ts_file to its base_path for output path generation
        file_to_base_path = {}
        for ts_file in ts_files:
            for base_path in file_paths:
                if ts_file.startswith(base_path) or ts_file.startswith(str(Path(base_path).resolve())):
                    file_to_base_path[ts_file] = base_path
                    break
        
        # Translate/interpret files concurrently with retry mechanism
        translations = await self._translate_files_with_retry(ts_files, mode, file_to_base_path)

        # Prepare result
        successful_count = len([t for t in translations if t.get("status") == "success"])
        skipped_count = len([t for t in translations if t.get("status") == "skipped"])
        failed_count = len([t for t in translations if t.get("status") == "failed"])

        result = {
            "status": "success",
            "mode": mode_str,
            "paths": file_paths,
            "total_files": len(ts_files),
            "successful_translations": successful_count,
            "skipped_translations": skipped_count,
            "failed_translations": failed_count,
            "file_statistics": file_stats,
            "translations": translations
        }

        logger.info(
            f"{mode_str} completed: {successful_count} processed, {skipped_count} skipped, {failed_count} failed (total: {len(ts_files)})")
        self.set_result(json.dumps(result, ensure_ascii=False, indent=2))

    @staticmethod
    def _find_ts_files(directory_path: str) -> List[str]:
        """
        Recursively find all TypeScript (.ts) and TSX (.tsx) files in the given directory
        
        Args:
            directory_path: Root directory to search
            
        Returns:
            List of TypeScript/TSX file paths
        """
        path = Path(directory_path)

        if not path.exists():
            logger.warning(f"Path does not exist: {directory_path}")
            return []

        if path.is_file():
            # If it's a file, check if it's a .ts or .tsx file
            if path.suffix in ['.ts', '.tsx']:
                return [str(path)]
            else:
                logger.warning(f"Path is not a TypeScript/TSX file: {directory_path}")
                return []

        # Recursively find all .ts and .tsx files
        ts_files = []
        for ts_file in path.rglob("*.ts"):
            if ts_file.is_file():
                ts_files.append(str(ts_file))
        for tsx_file in path.rglob("*.tsx"):
            if tsx_file.is_file():
                ts_files.append(str(tsx_file))

        return sorted(ts_files)

    @staticmethod
    def _analyze_file_statistics(ts_files: List[str]) -> Dict:
        """
        Analyze statistics of TypeScript files (character count, top 5 largest, average, etc.)
        
        Args:
            ts_files: List of TypeScript file paths
            
        Returns:
            Dictionary containing file statistics:
            - total_files: Total number of files
            - total_chars: Total character count
            - avg_chars: Average characters per file
            - median_chars: Median character count
            - top_5_largest: List of (file_path, char_count) tuples for top 5 largest files
        """
        if not ts_files:
            return {
                "total_files": 0,
                "total_chars": 0,
                "avg_chars": 0,
                "median_chars": 0,
                "top_5_largest": []
            }

        # Collect file sizes
        file_sizes: List[Tuple[str, int]] = []
        for ts_file in ts_files:
            try:
                content = Path(ts_file).read_text(encoding='utf-8')
                char_count = len(content)
                file_sizes.append((ts_file, char_count))
            except Exception as e:
                logger.warning(f"Error reading {ts_file} for statistics: {e}")
                file_sizes.append((ts_file, 0))

        # Sort by size (descending)
        file_sizes.sort(key=lambda x: x[1], reverse=True)

        # Calculate statistics
        char_counts = [size for _, size in file_sizes]
        total_files = len(ts_files)
        total_chars = sum(char_counts)
        avg_chars = total_chars / total_files if total_files > 0 else 0

        # Calculate median
        sorted_counts = sorted(char_counts)
        n = len(sorted_counts)
        if n % 2 == 0:
            median_chars = (sorted_counts[n//2 - 1] + sorted_counts[n//2]) / 2
        else:
            median_chars = sorted_counts[n//2]

        # Get top 5 largest files
        top_5_largest = file_sizes[:5]

        return {
            "total_files": total_files,
            "total_chars": total_chars,
            "avg_chars": avg_chars,
            "median_chars": int(median_chars),
            "top_5_largest": top_5_largest
        }

    @staticmethod
    def _get_output_file_path(ts_file_path: str, base_path: str, mode: bool) -> str:
        """
        Generate corresponding output file path from TypeScript file path
        
        Args:
            ts_file_path: Path to the TypeScript file (e.g., 'a/b/c/dir/file.ts')
            base_path: Base path that was originally searched (e.g., 'a/b/c')
            mode: True = Python translation, False = Markdown interpretation
            
        Returns:
            Corresponding output file path:
            - mode=True: 'a/b/c_python/dir/file.py'
            - mode=False: 'a/b/c_markdown/dir/file.md'
        """
        ts_path = Path(ts_file_path)
        base = Path(base_path)
        
        # Get the relative path from base to the ts file
        try:
            relative_path = ts_path.relative_to(base)
        except ValueError:
            # If ts_file_path is not relative to base_path, just use the filename
            relative_path = ts_path.name
        
        # Determine output directory and extension based on mode
        if mode:
            # Translation mode: a/b/c -> a/b/c_python
            output_base = Path(str(base) + "_python")
            extension = '.py'
        else:
            # Interpretation mode: a/b/c -> a/b/c_markdown
            output_base = Path(str(base) + "_markdown")
            extension = '.md'
        
        # Construct output path with new extension
        output_path = output_base / relative_path.with_suffix(extension)
        
        return str(output_path)

    async def _translate_files_with_retry(self, ts_files: List[str], mode: bool, file_to_base_path: Dict[str, str]) -> List[Dict]:
        """
        Translate/interpret TypeScript files with retry mechanism for failed cases
        
        Args:
            ts_files: List of TypeScript file paths
            mode: True = translate to Python, False = interpret to markdown
            file_to_base_path: Mapping from ts_file to its base_path
            
        Returns:
            List of translation results
        """
        all_results = {}  # file_path -> result dict
        files_to_translate = ts_files.copy()
        retry_count = 0

        while files_to_translate and retry_count <= self.max_retries:
            if retry_count > 0:
                logger.info(
                    f"Retry attempt {retry_count}/{self.max_retries} for {len(files_to_translate)} failed files...")

            # Translate current batch with progress bar
            translations = await self._translate_files_concurrently(files_to_translate, mode, file_to_base_path, retry_round=retry_count)

            # Collect results and identify failed files
            failed_files = []
            for translation in translations:
                file_path = translation["file_path"]
                all_results[file_path] = translation

                # Add retry info if this is a retry attempt
                if retry_count > 0:
                    if "retry_attempts" not in translation:
                        translation["retry_attempts"] = []
                    translation["retry_attempts"].append(retry_count)

                # Collect failed files for retry
                if translation.get("status") == "failed" and retry_count < self.max_retries:
                    failed_files.append(file_path)

            # Update files to translate for next retry
            files_to_translate = failed_files
            retry_count += 1

        # Convert results dict back to list, preserving original order
        final_results = [all_results[f] for f in ts_files]

        # Add final retry statistics
        retry_stats = {
            "total_retries": retry_count - 1,
            "files_retried": len([r for r in final_results if "retry_attempts" in r])
        }
        logger.info(f"Retry statistics: {retry_stats}")

        return final_results

    async def _translate_single_file_safe(self, ts_file: str, mode: bool, base_path: str):
        """Wrapper to safely execute translation/interpretation and catch exceptions"""
        try:
            return await self._translate_single_file(ts_file, mode, base_path)
        except Exception as e:
            logger.error(f"{'Translation' if mode else 'Interpretation'} failed for {ts_file}: {str(e)}")
            return {
                "file_path": ts_file,
                "status": "failed",
                "error": str(e)
            }

    async def _translate_files_concurrently(self, ts_files: List[str], mode: bool, file_to_base_path: Dict[str, str], retry_round: int = 0) -> List[Dict]:
        """
        Translate/interpret TypeScript files concurrently with semaphore control and submit interval
        
        Args:
            ts_files: List of TypeScript file paths
            mode: True = translate to Python, False = interpret to markdown
            file_to_base_path: Mapping from ts_file to its base_path
            retry_round: Current retry round number (0 for initial attempt)
            
        Returns:
            List of translation results
        """
        # Progress bar description
        if retry_round > 0:
            desc = f"Retry {retry_round}/{self.max_retries}"
        else:
            desc = "Translating" if mode else "Interpreting"

        # Create a wrapper task that includes delay
        async def delayed_task(index: int, ts_file: str):
            # Add delay before each task execution (except the first one)
            if index > 0:
                await asyncio.sleep(self.submit_interval)
                logger.debug(f"Starting task {index} after {self.submit_interval}s delay")
            return await self._translate_single_file_safe(ts_file, mode, file_to_base_path.get(ts_file, ts_file))

        # Create all delayed tasks
        tasks = [delayed_task(i, ts_file) for i, ts_file in enumerate(ts_files)]

        # Execute all tasks concurrently with progress bar
        results = await tqdm_asyncio.gather(
            *tasks,
            desc=desc,
            total=len(tasks),
            unit="file"
        )

        return results

    async def _translate_single_file(self, ts_file_path: str, mode: bool, base_path: str) -> Dict:
        """
        Translate/interpret a single TypeScript file using LLM with semaphore control
        
        Args:
            ts_file_path: Path to the TypeScript file
            mode: True = translate to Python, False = interpret to markdown
            base_path: Base path for generating output path
            
        Returns:
            Translation/interpretation result dictionary
        """
        async with self.semaphore:
            try:
                # Read TypeScript file content
                ts_content = Path(ts_file_path).read_text(encoding='utf-8')

                # Get output file path based on mode
                output_file_path = self._get_output_file_path(ts_file_path, base_path, mode)
                
                # Check if target file already exists and is not empty
                if self.skip_existing and Path(output_file_path).exists():
                    try:
                        existing_content = Path(output_file_path).read_text(encoding='utf-8').strip()
                        if existing_content:
                            logger.info(
                                f"Skipping {ts_file_path} - target file {output_file_path} already exists with content")
                            return {
                                "file_path": ts_file_path,
                                "status": "skipped",
                                "message": f"Target file {output_file_path} already exists",
                                "ts_content": ts_content,
                                "output_code": existing_content,
                                "output_file_path": output_file_path
                            }
                    except Exception as e:
                        logger.warning(f"Error reading existing file {output_file_path}: {e}")

                # Create prompt based on mode
                if mode:
                    # Translation mode: translate to Python
                    prompt = self.prompt_format(
                        prompt_name="translate_ts_to_python_prompt",
                        ts_content=ts_content
                    )
                    task_name = "Translating"
                    language_tag = "python"
                else:
                    # Interpretation mode: explain in markdown
                    prompt = self.prompt_format(
                        prompt_name="interpret_ts_to_markdown_prompt",
                        ts_content=ts_content
                    )
                    task_name = "Interpreting"
                    language_tag = "markdown"

                # Call LLM with callback to extract code
                logger.info(f"{task_name} {ts_file_path}...")
                
                # Callback function to extract code (only for translation mode)
                if mode:
                    # Translation mode: extract Python code block
                    def extract_code(msg):
                        content = msg.content
                        
                        # Extract code block
                        extracted = extract_content(content, language_tag=language_tag)
                        return extracted if extracted else content
                    
                    output_code = await self.llm.achat(
                        messages=[Message(role=Role.USER, content=prompt)],
                        callback_fn=extract_code,
                        enable_stream_print=False
                    )
                else:
                    # Interpretation mode: keep all content as is (no code extraction)
                    output_message = await self.llm.achat(
                        messages=[Message(role=Role.USER, content=prompt)],
                        enable_stream_print=False
                    )
                    output_code = output_message.content

                # Save output code to disk
                output_path = Path(output_file_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)  # Create parent directories if needed
                output_path.write_text(output_code, encoding='utf-8')
                logger.info(f"Saved {task_name.lower()} output to {output_file_path}")

                result = {
                    "file_path": ts_file_path,
                    "status": "success",
                    "ts_content": ts_content,
                    "output_code": output_code,
                    "output_file_path": output_file_path
                }

                return result

            except Exception as e:
                logger.exception(f"Error processing {ts_file_path}: {e}")
                return {
                    "file_path": ts_file_path,
                    "status": "failed",
                    "error": str(e)
                }


async def main():
    """
    Test function demonstrating both translation and interpretation modes
    
    Example usage:
    - Translation mode (mode=True): Translates TypeScript to Python, saves to *_python/*.py
    - Interpretation mode (mode=False): Explains TypeScript in Markdown, saves to *_markdown/*.md
    """
    from flowllm.app import FlowLLMApp
    from flowllm.context.flow_context import FlowContext

    async with FlowLLMApp(load_default_config=True):
        # Example: Translation mode (default)
        print("="*80)
        print("Example 1: Translation Mode (TypeScript -> Python)")
        print("="*80)
        op_translate = TranslateCodeOp(max_concurrent=2)
        context1 = FlowContext()
        await op_translate.async_call(
            context1, 
            file_path="/Users/yuli/workspace/qwen-code",
            mode=True
        )
        print(f"Translation Result Summary:\n{op_translate.output}\n")
        
        # Example: Interpretation mode
        print("="*80)
        print("Example 2: Interpretation Mode (TypeScript -> Markdown)")
        print("="*80)
        op_interpret = TranslateCodeOp(max_concurrent=2)
        context2 = FlowContext()
        await op_interpret.async_call(
            context2, 
            file_path="/Users/yuli/workspace/qwen-code",
            mode=False
        )
        print(f"Interpretation Result Summary:\n{op_interpret.output}\n")


if __name__ == "__main__":
    asyncio.run(main())
