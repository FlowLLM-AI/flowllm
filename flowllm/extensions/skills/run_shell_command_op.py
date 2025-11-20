"""Operation for running shell commands.

This module provides the RunShellCommandOp class which executes shell
commands in a subprocess, with automatic dependency detection and
installation for script files.
"""

import os
import re
import subprocess

from loguru import logger

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class RunShellCommandOp(BaseAsyncToolOp):
    """Operation for running shell commands in a subprocess.

    This tool executes shell commands and can automatically detect and
    install dependencies for script files (Python, JavaScript, Shell).
    It supports timeout configuration and error handling.
    """

    def build_tool_call(self) -> ToolCall:
        """Build the tool call definition for run_shell_command.

        Returns:
            A ToolCall object defining the run_shell_command tool.
        """
        return ToolCall(
            **{
                "name": "run_shell_command",
                "description": "run shell command (e.g., 'echo 'hello world'') in a subprocess.",
                "input_schema": {
                    "command": {
                        "type": "string",
                        "description": "shell command",
                        "required": True,
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "timeout for the subprocess",
                        "required": False,
                    },
                },
            },
        )

    async def async_execute(self):
        """Execute the shell command operation.

        Runs a shell command in a subprocess. If the command contains
        a script file path, automatically detects the language and
        installs any required dependencies before execution.

        Args:
            command: The shell command to execute.
            timeout: Optional timeout in seconds for the subprocess.

        The output (stdout) is captured and set as the operation output.
        If an error occurs, the error output is captured and returned.
        """
        command: str = self.input_dict["command"]
        timeout: int | None = self.input_dict.get("timeout", None)

        # Extract script path from command
        script_path = self._extract_script_path(command)
        if script_path:
            # Detect language
            language = self._detect_language(script_path)
            logger.info(f"Detected language: {language} in the script: {script_path}")

            # Detect and install dependencies
            dependencies = self._detect_dependencies(script_path, language)
            self._install_dependencies(dependencies, script_path, language)
        else:
            logger.info("No script detected in the command. Skipping language detection and dependency installation.")

        logger.info(f"Executing command:\n {command}")

        try:
            output = subprocess.run(
                command,
                shell=True,
                check=True,
                timeout=timeout,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ).stdout.decode()

        except subprocess.CalledProcessError as error:
            logger.exception(f"❌ Error during command execution: {error}")
            self.set_output(error.stdout.decode())
            return

        logger.info(f"✅ Successfully run the shell commands \n{output}")
        self.set_output(output)

    @staticmethod
    def _extract_script_path(command: str):
        """Extract script file path from a shell command.

        Uses regex to find file paths with common script extensions
        (.py, .js, .jsx, .sh, .bash) in the command string.

        Args:
            command: The shell command string.

        Returns:
            The extracted script path if found, None otherwise.
        """
        # This regex looks for common script file extensions
        match = re.search(r"((?:/[\w.-]+)+\.(?:py|js|jsx|sh|bash))", command)
        return match.group(1) if match else None

    @staticmethod
    def _detect_language(script_path):
        """Detect the programming language from a script file extension.

        Args:
            script_path: Path to the script file.

        Returns:
            The detected language name ("Python", "JavaScript", "Shell", or "Unknown").
        """
        _, ext = os.path.splitext(script_path)
        ext = ext.lower()

        if ext in [".py"]:
            return "Python"
        elif ext in [".js", ".jsx"]:
            return "JavaScript"
        elif ext in [".sh", ".bash"]:
            return "Shell"
        return "Unknown"

    def _detect_dependencies(self, script_path, language):
        """Detect dependencies required by a script.

        Args:
            script_path: Path to the script file.
            language: The programming language of the script.

        Returns:
            A list of dependency strings, empty if none found or language not supported.
        """
        if language == "Python":
            return self._detect_python_dependencies(script_path)
        # Add more language-specific dependency detection methods here
        return []

    @staticmethod
    def _detect_python_dependencies(script_path):
        """Detect Python dependencies using pipreqs.

        Uses pipreqs to analyze the script directory and generate
        a requirements.txt file, then reads and returns the dependencies.

        Args:
            script_path: Path to the Python script file.

        Returns:
            A list of dependency strings from the generated requirements.txt.
        """
        # Use pipreqs to generate requirements
        requirements_path = "requirements.txt"
        subprocess.run(["pipreqs", os.path.dirname(script_path), "--savepath", requirements_path], check=True)
        with open(requirements_path, "r", encoding="utf-8") as file:
            dependencies = file.read().splitlines()
        os.remove(requirements_path)
        return dependencies

    @staticmethod
    def _install_dependencies(dependencies, script_path, language):
        """Install dependencies for a script.

        Installs the detected dependencies using the appropriate package
        manager for the given language.

        Args:
            dependencies: List of dependency strings to install.
            script_path: Path to the script file (used for working directory).
            language: The programming language of the script.
        """
        if language == "Python":
            for dep in dependencies:
                subprocess.run(["pip", "install", dep], check=True, cwd=os.path.dirname(script_path))
        # Add more language-specific installation methods here
