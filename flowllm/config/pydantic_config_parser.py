import argparse
import copy
import json
from pathlib import Path
from typing import Any, Generic, List, Type, TypeVar

import yaml
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


class PydanticConfigParser(Generic[T]):
    """
    Pydantic Configuration Parser
    
    Supported configuration sources (priority from low to high):
    1. Default configuration (Pydantic model default values)
    2. YAML configuration file
    3. Command line arguments (dot notation format)
    4. Runtime parameters
    """

    def __init__(self, config_class: Type[T]):
        """
        Initialize configuration parser
        
        Args:
            config_class: Pydantic configuration model class
        """
        self.config_class = config_class
        self.config_dict: dict = {}

    def parse_dot_notation(self, dot_list: List[str]) -> dict:
        """
        Parse dot notation format configuration list
        
        Args:
            dot_list: Configuration list in format ['a.b.c=value', 'x.y=123']
            
        Returns:
            Parsed nested dictionary
        """
        config_dict = {}

        for item in dot_list:
            if '=' not in item:
                continue

            key_path, value_str = item.split('=', 1)
            keys = key_path.split('.')

            # Automatic type conversion
            value = self._convert_value(value_str)

            # Build nested dictionary
            current_dict = config_dict
            for key in keys[:-1]:
                if key not in current_dict:
                    current_dict[key] = {}
                current_dict = current_dict[key]

            current_dict[keys[-1]] = value

        return config_dict

    @staticmethod
    def _convert_value(value_str: str) -> Any:
        """
        Automatically convert string values to appropriate Python types
        
        Args:
            value_str: String value
            
        Returns:
            Converted value
        """
        value_str = value_str.strip()

        if value_str.lower() in ("true", "false"):
            return value_str.lower() == "true"

        if value_str.lower() in ("none", "null"):
            return None

        try:
            if "." not in value_str and "e" not in value_str.lower():
                return int(value_str)

            return float(value_str)

        except ValueError:
            pass

        try:
            return json.loads(value_str)
        except (json.JSONDecodeError, ValueError):
            pass

        return value_str

    @staticmethod
    def load_from_yaml(yaml_path: str | Path) -> dict:
        """
        Load configuration from YAML file
        
        Args:
            yaml_path: YAML file path
            
        Returns:
            Configuration dictionary
        """
        if isinstance(yaml_path, str):
            yaml_path = Path(yaml_path)

        if not yaml_path.exists():
            raise FileNotFoundError(f"Configuration file does not exist: {yaml_path}")

        with yaml_path.open() as f:
            return yaml.safe_load(f)

    def merge_configs(self, *config_dicts: dict) -> dict:
        """
        Deep merge multiple configuration dictionaries
        
        Args:
            *config_dicts: Multiple configuration dictionaries
            
        Returns:
            Merged configuration dictionary
        """
        result = {}

        for config_dict in config_dicts:
            result = self._deep_merge(result, config_dict)

        return result

    def _deep_merge(self, base_dict: dict, update_dict: dict) -> dict:
        """
        Deep merge two dictionaries
        
        Args:
            base_dict: Base dictionary
            update_dict: Update dictionary
            
        Returns:
            Merged dictionary
        """
        result = base_dict.copy()

        for key, value in update_dict.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def parse_args(self, *args) -> T:
        """
        Parse command line arguments and return configuration object
        
        Args:
            args: Command line arguments, if None then get from sys.argv
            
        Returns:
            Parsed configuration object
        """

        parser = argparse.ArgumentParser(
            description="FlowLLM Configuration Parser - Supports dot notation format configuration",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="Usage examples: python script.py --config xxx.yaml a.b=xxx c.d=xxx")

        parser.add_argument("--config", "-c", type=str, help="YAML configuration file path")
        parser.add_argument("overrides", nargs="*", help="shell config, format: key.subkey=value")
        parsed_args = parser.parse_args(args=args)

        configs_to_merge = []

        # 1. Default configuration (from Pydantic model)
        default_config = self.config_class().model_dump()
        configs_to_merge.append(default_config)

        # 2. YAML configuration file
        if parsed_args.config:
            if not parsed_args.config.endswith(".yaml"):
                parsed_args.config += ".yaml"

            # load pre-built configs
            config_path = Path(__file__).parent / parsed_args.config
            if not config_path.exists():
                config_path = Path(parsed_args.config)

            yaml_config = self.load_from_yaml(config_path)
            configs_to_merge.append(yaml_config)

        # 3. Command line override configuration
        if parsed_args.overrides:
            cli_config = self.parse_dot_notation(parsed_args.overrides)
            configs_to_merge.append(cli_config)

        # Merge all configurations
        self.config_dict = self.merge_configs(*configs_to_merge)

        # Create and validate final configuration object
        return self.config_class.model_validate(self.config_dict)

    def update_config(self, **kwargs) -> T:
        """
        Update configuration object using keyword arguments
        
        Args:
            **kwargs: Configuration items to update, supports dot notation, e.g. server__host='localhost'
            
        Returns:
            Updated configuration object
        """
        # Convert kwargs to dot notation format
        dot_list = []
        for key, value in kwargs.items():
            # support double underscore as dot replacement (server__host -> server.host)
            dot_key = key.replace("__", ".")
            dot_list.append(f"{dot_key}={value}")

        # Parse and merge configuration
        override_config = self.parse_dot_notation(dot_list)
        final_config = self.merge_configs(copy.deepcopy(self.config_dict), override_config)

        return self.config_class.model_validate(final_config)
