"""Operation for running shell commands.

This module provides the RunShellCommandOp class which executes shell
commands in a subprocess, with automatic dependency detection and
installation for script files. The command is executed in the skill's
directory context, allowing scripts to access skill-specific files and
resources.
"""

import asyncio
import os
import shutil
from pathlib import Path

from loguru import logger

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class RunShellCommandOp(BaseAsyncToolOp):
    """Operation for running shell commands in a subprocess.

    This tool executes shell commands and can automatically detect and
    install dependencies for script files (Python, JavaScript, Shell).
    The command is executed in the skill's directory context, allowing
    scripts to access skill-specific files and resources.

    The operation will:
    1. Extract skill_name and command from input
    2. Look up the skill directory from skill_metadata_dict
    3. Change to the skill directory before executing the command
    4. For Python commands, automatically detect and install dependencies
       using pipreqs (if available and auto_install_deps parameter is enabled)
    5. Execute the command in a subprocess and capture stdout/stderr
    6. Return the combined output

    Returns:
        str: The combined stdout and stderr output from the command execution.
            The output is decoded as UTF-8 and stripped of leading/trailing
            whitespace, with stdout and stderr concatenated with a newline.

    Note:
        - The skill_name must exist in `self.context.skill_metadata_dict`
        - The command is executed in the skill's directory using `cd {skill_dir} && {command}`
        - For Python commands (containing "py"), the tool attempts to auto-install
          dependencies using pipreqs if it's available in the system PATH and
          the auto_install_deps parameter is enabled
        - If pipreqs is not available or dependency installation fails, a warning
          is logged but the command execution continues
        - The subprocess uses the current environment variables (os.environ.copy())
    """

    def __init__(self, auto_install_deps: bool = False, **kwargs):
        """Initialize RunShellCommandOp.

        Args:
            auto_install_deps: If True, enables automatic dependency installation for Python
                commands. Defaults to False.
            **kwargs: Additional keyword arguments passed to parent class.
        """
        super().__init__(**kwargs)
        self.auto_install_deps: bool = auto_install_deps

    def build_tool_call(self) -> ToolCall:
        """Build the tool call definition for run_shell_command.

        Creates and returns a ToolCall object that defines the run_shell_command
        tool. This tool requires both skill_name and command parameters to
        identify which skill directory to use and what command to execute.

        Returns:
            ToolCall: A ToolCall object defining the run_shell_command tool with
                the following properties:
                - name: "run_shell_command"
                - description: Description of what the tool does
                - input_schema: A schema requiring:
                    - "skill_name" (string, required): The name of the skill
                    - "command" (string, required): The shell command to execute
        """
        return ToolCall(
            **{
                "name": "run_shell_command",
                "description": self.get_prompt("tool_desc"),
                "input_schema": {
                    "skill_name": {
                        "type": "string",
                        "description": "skill name",
                        "required": True,
                    },
                    "command": {
                        "type": "string",
                        "description": "shell command",
                        "required": True,
                    },
                },
            },
        )

    async def async_execute(self):
        """Execute the shell command operation.

        Executes a shell command in the specified skill's directory. For Python
        commands, the method attempts to automatically detect and install
        dependencies using pipreqs before executing the command.

        The method:
        1. Extracts skill_name and command from input_dict
        2. Looks up the skill directory from skill_metadata_dict
        3. For Python commands (containing "py"), checks if pipreqs is available
        4. If pipreqs is available, generates requirements.txt and installs dependencies
        5. Constructs the full command as `cd {skill_dir} && {command}`
        6. Executes the command in a subprocess with the current environment
        7. Captures stdout and stderr output
        8. Returns the combined output (stdout + stderr)

        Returns:
            None: The result is set via `self.set_output()` with the combined
                stdout and stderr output from the command execution. The output
                is decoded as UTF-8 and formatted as: "{stdout}\n{stderr}"

        Raises:
            KeyError: If skill_name is not found in skill_metadata_dict.
                This should be handled by ensuring LoadSkillMetadataOp is
                called before RunShellCommandOp.

        Note:
            - Dependency auto-installation only occurs for commands containing "py"
              and when the auto_install_deps parameter is enabled
            - If pipreqs is not available, a warning is logged but execution continues
            - If dependency installation fails, a warning is logged but the command
              is still executed
            - The command runs in the skill's directory, allowing access to
              skill-specific files and resources
            - Environment variables from the current process are passed to the subprocess
        """
        # Extract skill name and command from input parameters
        skill_name = self.input_dict["skill_name"]
        command: str = self.input_dict["command"]
        # Look up the skill directory from the metadata dictionary
        # This dictionary should be populated by LoadSkillMetadataOp
        skill_dir = Path(self.context.skill_metadata_dict[skill_name]["skill_dir"])
        logger.info(f"🔧 run shell command: skill_name={skill_name} skill_dir={skill_dir} command={command}")

        # Auto-install dependencies for Python scripts if pipreqs is available
        # This helps ensure that Python scripts have their required dependencies
        # Only install if auto_install_deps parameter is enabled
        if self.auto_install_deps:
            if "py" in command:
                pipreqs_available = shutil.which("pipreqs") is not None
                if pipreqs_available:
                    install_cmd = f"cd {skill_dir} && pipreqs . --force && pip install -r requirements.txt"
                    proc = await asyncio.create_subprocess_shell(
                        install_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await proc.communicate()
                    if proc.returncode != 0:
                        logger.warning(f"⚠️ Failed to install dependencies:\n{stdout.decode()}\n{stderr.decode()}")
                    else:
                        logger.info(f"✅ Dependencies installed successfully.\n{stdout.decode()}\n{stderr.decode()}")
                else:
                    logger.info("ℹ️ pipreqs not found, skipping dependency auto-install.")

        # Construct the full command to execute in the skill directory
        # This ensures the command runs in the correct context
        full_command = f"cd {skill_dir} && {command}"
        proc = await asyncio.create_subprocess_shell(
            full_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy(),
        )

        # Wait for the command to complete and capture output
        stdout, stderr = await proc.communicate()
        # Combine stdout and stderr output, decoded as UTF-8
        output = stdout.decode().strip() + "\n" + stderr.decode().strip()
        logger.info(f"✅ Command executed: skill_name={skill_name} output={output}")
        self.set_output(output)
