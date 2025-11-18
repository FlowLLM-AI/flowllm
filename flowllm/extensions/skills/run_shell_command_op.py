import re
import os
import subprocess

from loguru import logger
from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class RunShellCommandOp(BaseAsyncToolOp):

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "run_shell_command",
            "description": "run shell command (e.g., 'echo \'hello world\'') in a subprocess.",
            "input_schema": {
                "command": {
                    "type": "string",
                    "description": "shell command",
                    "required": True
                },
                "timeout": {
                    "type": "int",
                    "description": "timeout for the subprocess",
                    "required": False
                }
            }
        })
    
    async def async_execute(self):
        if self.input_dict.get("command"):
            command = self.input_dict.get("command")
        else:
            raise RuntimeError("one shell command is required")
        timeout = self.input_dict.get("timeout", 60)
    
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
            self.set_result(error.stdout.decode())
            return

        logger.info("✅ Successfully run the shell commands")
        self.set_result(output.strip())

    def _extract_script_path(self, command):
        # This regex looks for common script file extensions
        match = re.search(r'((?:/[\w.-]+)+\.(?:py|js|jsx|sh|bash))', command)
        return match.group(1) if match else None

    def _detect_language(self, script_path):
        _, ext = os.path.splitext(script_path)
        ext = ext.lower()
        
        if ext in ['.py']:
            return 'Python'
        elif ext in ['.js', '.jsx']:
            return 'JavaScript'
        elif ext in ['.sh', '.bash']:
            return 'Shell'
        return 'Unknown'

    def _detect_dependencies(self, script_path, language):
        if language == 'Python':
            return self._detect_python_dependencies(script_path)
        # Add more language-specific dependency detection methods here
        return []

    def _detect_python_dependencies(self, script_path):
        # Use pipreqs to generate requirements
        requirements_path = 'requirements.txt'
        subprocess.run(['pipreqs', os.path.dirname(script_path), '--savepath', requirements_path], check=True)
        with open(requirements_path, 'r') as file:
            dependencies = file.read().splitlines()
        os.remove(requirements_path)
        return dependencies
    
    def _install_dependencies(self, dependencies, script_path, language):
        if language == 'Python':
            for dep in dependencies:
                subprocess.run(['pip', 'install', dep], check=True, cwd=os.path.dirname(script_path))
        # Add more language-specific installation methods here
    
    