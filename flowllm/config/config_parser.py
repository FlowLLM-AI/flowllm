import json
from pathlib import Path

from loguru import logger
from omegaconf import OmegaConf, DictConfig

from flowllm.schema.service_config import ServiceConfig


class ConfigParser:
    """
    Configuration parser that handles loading and merging configurations from multiple sources.

    The configuration loading priority (from lowest to highest):
    1. Default configuration from ServiceConfig schema
    2. YAML configuration file
    3. Command line arguments
    4. Runtime keyword arguments
    """

    def __init__(self, args: list):
        """
        Initialize the configuration parser with command line arguments.
        
        Args:
            args: List of command line arguments in dot list format (e.g., ['key=value'])
        """

        self.app_config: DictConfig = OmegaConf.structured(ServiceConfig)

        cli_config: DictConfig = OmegaConf.from_dotlist(args)
        temp_config: ServiceConfig = OmegaConf.to_object(OmegaConf.merge(self.app_config, cli_config))

        if temp_config.config_path:
            config_path: str = temp_config.config_path
            if not config_path.endswith(".yaml"):
                config_path += ".yaml"

            real_config_path = Path(__file__).parent / config_path
            if not real_config_path.exists():
                real_config_path = Path(config_path)
            assert real_config_path.exists(), f"Config file {real_config_path} does not exist!"

            logger.info(f"load config from path={real_config_path}")
            yaml_config = OmegaConf.load(real_config_path)
            self.app_config = OmegaConf.merge(self.app_config, yaml_config)

        self.app_config = OmegaConf.merge(self.app_config, cli_config)
        app_config_dict = OmegaConf.to_container(self.app_config, resolve=True)
        logger.info(f"app_config=\n{json.dumps(app_config_dict, indent=2, ensure_ascii=False)}")

    def get_service_config(self, **kwargs) -> ServiceConfig:
        """
        Get the service configuration with optional runtime overrides.
        
        Args:
            **kwargs: Additional configuration parameters to override at runtime
            
        Returns:
            ServiceConfig: The final service configuration object
        """
        # Create a copy of the current configuration
        app_config = self.app_config.copy()

        if kwargs:
            kwargs_list = [f"{k}={v}" for k, v in kwargs.items()]
            update_config = OmegaConf.from_dotlist(kwargs_list)
            app_config = OmegaConf.merge(app_config, update_config)

        return OmegaConf.to_object(app_config)
