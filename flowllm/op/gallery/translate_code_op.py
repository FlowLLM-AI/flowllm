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
    TranslateCodeOp - TypeScript to Python Translation Operator
    
    This operator recursively finds all TypeScript files in a given directory and
    translates them to Python using LLM with concurrent processing (pool size: 4).
    """
    file_path: str = __file__

    def __init__(self, max_concurrent: int = 4, max_retries: int = 3, skip_existing: bool = True, **kwargs):
        """
        Initialize TranslateCodeOp
        
        Args:
            max_concurrent: Maximum number of concurrent LLM calls (default: 4)
            max_retries: Maximum number of retries for failed translations (default: 3)
            skip_existing: Skip translation if target .py file already exists and is not empty (default: True)
        """
        super().__init__(**kwargs)
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.skip_existing = skip_existing
        self.semaphore = None  # Will be initialized in async_execute

    def build_tool_call(self) -> ToolCall:
        """Build tool call schema for TranslateCodeOp"""
        return ToolCall(**{
            "name": "translate_code",
            "description": "Recursively find all TypeScript files in a directory and translate them to Python with detailed comments",
            "input_schema": {
                "file_path": ParamAttrs(
                    type="str",
                    description="The directory path(s) to search for TypeScript files. Multiple paths can be separated by semicolons (;)",
                    required=True
                )
            }
        })

    async def async_execute(self):
        """
        Main execution method
        
        Steps:
        1. Get the input file path(s) from context (supports multiple paths separated by semicolons)
        2. Recursively find all .ts files in all paths
        3. Translate each file concurrently with pool size limit
        4. Return translation results
        """
        # Get input file path(s)
        file_path: str = self.input_dict.get("file_path", "")
        if not file_path:
            raise ValueError("file_path is required")

        # Split paths by semicolon and strip whitespace
        file_paths = [path.strip() for path in file_path.split(';') if path.strip()]
        logger.info(f"Processing {len(file_paths)} path(s): {file_paths}")

        # Initialize semaphore for concurrent control
        self.semaphore = asyncio.Semaphore(self.max_concurrent)

        # Find all TypeScript files recursively from all paths
        ts_files = []
        for path in file_paths:
            files = self._find_ts_files(path)
            ts_files.extend(files)
            logger.info(f"Found {len(files)} TypeScript files in {path}")

        # Remove duplicates while preserving order
        seen = set()
        unique_ts_files = []
        for file in ts_files:
            if file not in seen:
                seen.add(file)
                unique_ts_files.append(file)
        ts_files = unique_ts_files

        logger.info(f"Total: {len(ts_files)} unique TypeScript files")

        if not ts_files:
            result = {
                "status": "success",
                "message": f"No TypeScript files found in the specified path(s)",
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

        # Translate files concurrently with retry mechanism
        translations = await self._translate_files_with_retry(ts_files)

        # Prepare result
        successful_count = len([t for t in translations if t.get("status") == "success"])
        skipped_count = len([t for t in translations if t.get("status") == "skipped"])
        failed_count = len([t for t in translations if t.get("status") == "failed"])

        result = {
            "status": "success",
            "paths": file_paths,
            "total_files": len(ts_files),
            "successful_translations": successful_count,
            "skipped_translations": skipped_count,
            "failed_translations": failed_count,
            "file_statistics": file_stats,
            "translations": translations
        }

        logger.info(
            f"Translation completed: {successful_count} translated, {skipped_count} skipped, {failed_count} failed (total: {len(ts_files)})")
        self.set_result(json.dumps(result, ensure_ascii=False, indent=2))

    @staticmethod
    def _find_ts_files(directory_path: str) -> List[str]:
        """
        Recursively find all TypeScript (.ts) files in the given directory
        
        Args:
            directory_path: Root directory to search
            
        Returns:
            List of TypeScript file paths
        """
        path = Path(directory_path)

        if not path.exists():
            logger.warning(f"Path does not exist: {directory_path}")
            return []

        if path.is_file():
            # If it's a file, check if it's a .ts file
            if path.suffix == '.ts':
                return [str(path)]
            else:
                logger.warning(f"Path is not a TypeScript file: {directory_path}")
                return []

        # Recursively find all .ts files
        ts_files = []
        for ts_file in path.rglob("*.ts"):
            if ts_file.is_file():
                ts_files.append(str(ts_file))

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
    def _get_python_file_path(ts_file_path: str) -> str:
        """
        Generate corresponding Python file path from TypeScript file path
        
        Args:
            ts_file_path: Path to the TypeScript file (e.g., 'path/to/file.ts')
            
        Returns:
            Corresponding Python file path (e.g., 'path/to/file.py')
        """
        return str(Path(ts_file_path).with_suffix('.py'))

    async def _translate_files_with_retry(self, ts_files: List[str]) -> List[Dict]:
        """
        Translate TypeScript files to Python with retry mechanism for failed cases
        
        Args:
            ts_files: List of TypeScript file paths
            
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
            translations = await self._translate_files_concurrently(files_to_translate, retry_round=retry_count)

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

    async def _translate_single_file_safe(self, ts_file: str):
        """Wrapper to safely execute translation and catch exceptions"""
        try:
            return await self._translate_single_file(ts_file)
        except Exception as e:
            logger.error(f"Translation failed for {ts_file}: {str(e)}")
            return {
                "file_path": ts_file,
                "status": "failed",
                "error": str(e)
            }

    async def _translate_files_concurrently(self, ts_files: List[str], retry_round: int = 0) -> List[Dict]:
        """
        Translate TypeScript files to Python concurrently with semaphore control
        
        Args:
            ts_files: List of TypeScript file paths
            retry_round: Current retry round number (0 for initial attempt)
            
        Returns:
            List of translation results
        """
        # Create safe tasks for all files
        tasks = []
        for ts_file in ts_files:
            task = self._translate_single_file_safe(ts_file)
            tasks.append(task)

        # Progress bar description
        if retry_round > 0:
            desc = f"Retry {retry_round}/{self.max_retries}"
        else:
            desc = "Translating"

        # Execute all tasks concurrently with progress bar
        results = await tqdm_asyncio.gather(
            *tasks,
            desc=desc,
            total=len(tasks),
            unit="file"
        )

        return results

    async def _translate_single_file(self, ts_file_path: str) -> Dict:
        """
        Translate a single TypeScript file to Python using LLM with semaphore control
        
        Args:
            ts_file_path: Path to the TypeScript file
            
        Returns:
            Translation result dictionary
        """
        async with self.semaphore:
            try:
                # Read TypeScript file content
                ts_content = Path(ts_file_path).read_text(encoding='utf-8')

                # Check if target Python file already exists and is not empty
                python_file_path = self._get_python_file_path(ts_file_path)
                if self.skip_existing and Path(python_file_path).exists():
                    try:
                        existing_content = Path(python_file_path).read_text(encoding='utf-8').strip()
                        if existing_content:
                            logger.info(
                                f"Skipping {ts_file_path} - target file {python_file_path} already exists with content")
                            return {
                                "file_path": ts_file_path,
                                "status": "skipped",
                                "message": f"Target file {python_file_path} already exists",
                                "ts_content": ts_content,
                                "python_code": existing_content,
                                "python_file_path": python_file_path
                            }
                    except Exception as e:
                        logger.warning(f"Error reading existing file {python_file_path}: {e}")

                # Create translation prompt
                prompt = self.prompt_format(
                    prompt_name="translate_ts_to_python_prompt",
                    ts_content=ts_content
                )

                # Call LLM to translate with callback to extract Python code
                logger.info(f"Translating {ts_file_path}...")
                
                # Callback function to extract Python code and print full response
                def extract_python_code(msg):
                    content = msg.content
                    
                    # Print the full LLM response for debugging
                    # logger.info(f"[LLM Response for {ts_file_path}]:\n{content}")
                    
                    # Extract Python code
                    python_code = extract_content(content, language_tag="python")
                    return python_code if python_code else content
                
                python_code = await self.llm.achat(
                    messages=[Message(role=Role.USER, content=prompt)],
                    callback_fn=extract_python_code,
                    enable_stream_print=False
                )

                # Save Python code to disk
                python_path = Path(python_file_path)
                python_path.parent.mkdir(parents=True, exist_ok=True)  # Create parent directories if needed
                python_path.write_text(python_code, encoding='utf-8')
                logger.info(f"Saved translated Python code to {python_file_path}")

                result = {
                    "file_path": ts_file_path,
                    "status": "success",
                    "ts_content": ts_content,
                    "python_code": python_code,
                    "python_file_path": python_file_path
                }

                return result

            except Exception as e:
                logger.exception(f"Error translating {ts_file_path}: {e}")
                return {
                    "file_path": ts_file_path,
                    "status": "failed",
                    "error": str(e)
                }


async def main():
    from flowllm.app import FlowLLMApp
    from flowllm.context.flow_context import FlowContext

    async with FlowLLMApp(load_default_config=True):
        """Test function for TranslateCodeOp"""
        op = TranslateCodeOp()
        context = FlowContext()
        await op.async_call(context, file_path="/Users/yuli/workspace/qwen-code")
        print(f"Result: {op.output}")


if __name__ == "__main__":

    asyncio.run(main())
