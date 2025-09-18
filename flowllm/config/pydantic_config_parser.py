import copy
import json
from pathlib import Path
from typing import Any, Generic, List, Type, TypeVar

import yaml
from loguru import logger
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


class PydanticConfigParser(Generic[T]):
    current_file: str = __file__
    default_config_name: str = "default"

    """
    Pydantic Configuration Parser
    
    Supported configuration sources (priority from low to high):
    1. Default configuration (Pydantic model default values)
    2. YAML configuration file (supports import_config for importing multiple files)
    3. Command line arguments (dot notation format)
    4. Runtime parameters
    
    The import_config field supports importing multiple configuration files
    by separating them with commas. Example:
    import_config: "base.yaml, auth.yaml, database.yaml"
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

    def _load_import_configs_recursive(self, config_dict: dict, visited_configs: set) -> List[dict]:
        """
        Recursively load import_config configurations with cycle detection
        
        Supports importing multiple config files by separating them with commas.
        Example: import_config: "base.yaml, auth.yaml, database.yaml"
        
        Args:
            config_dict: Current configuration dictionary
            visited_configs: Set of already visited config file paths to detect cycles
            
        Returns:
            List of imported configurations in correct merge order (base configs first)
        """
        import_config = config_dict.get("import_config", "")
        if not import_config:
            return []
        
        # Support comma-separated config files
        import_config_list = [config.strip() for config in import_config.split(",") if config.strip()]
        if not import_config_list:
            return []
            
        all_imported_configs = []
        
        for single_import_config in import_config_list:
            # Normalize config path
            if not single_import_config.endswith(".yaml"):
                single_import_config += ".yaml"
                
            # Resolve config file path
            import_config_path = Path(self.current_file).parent / single_import_config
            if not import_config_path.exists():
                import_config_path = Path(single_import_config)
                
            # Convert to absolute path for cycle detection
            abs_config_path = import_config_path.resolve()
            
            # Check for circular dependency
            if str(abs_config_path) in visited_configs:
                # logger.warning(f"Circular import detected for config: {abs_config_path}")
                continue
                
            logger.info(f"flowllm using import_config_path={import_config_path}")
            
            # Add current config to visited set
            visited_configs.add(str(abs_config_path))

            # Load the import config
            import_yaml_config = self.load_from_yaml(import_config_path)

            # Recursively load imports from the imported config
            nested_imports = self._load_import_configs_recursive(import_yaml_config, visited_configs.copy())

            # Add configs in correct order: deeper imports first, then current import
            # This ensures that configs closer to the root have higher priority
            all_imported_configs.extend(nested_imports)
            all_imported_configs.append(import_yaml_config)
        
        return all_imported_configs

    def parse_args(self, *args) -> T:
        """
        Parse command line arguments and return configuration object
        
        Args:
            args: Command line arguments.
            
        Returns:
            Parsed configuration object
        """
        configs_to_merge = []

        # 1. Default configuration (from Pydantic model)
        default_config = self.config_class().model_dump()
        configs_to_merge.append(default_config)

        # 2. YAML configuration file
        config = ""
        filter_args = []
        for arg in args:
            if "=" not in arg:
                continue

            arg = arg.lstrip("--").lstrip("-")

            if "c=" in arg or "config=" in arg:
                config = arg.split("=")[-1]
            else:
                filter_args.append(arg)

        if not config:
            if self.default_config_name:
                config = self.default_config_name
            assert config, "add `config=<config_file>` in cmd!"

        if not config.endswith(".yaml"):
            config += ".yaml"

        # load pre-built configs
        config_path = Path(self.current_file).parent / config
        if not config_path.exists():
            config_path = Path(config)
        logger.info(f"load config={config_path}")

        yaml_config = self.load_from_yaml(config_path)

        # load import configs recursively
        imported_configs = self._load_import_configs_recursive(yaml_config, set())
        configs_to_merge.extend(imported_configs)

        configs_to_merge.append(yaml_config)

        # 3. Command line override configuration
        if args:
            cli_config = self.parse_dot_notation(filter_args)
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
