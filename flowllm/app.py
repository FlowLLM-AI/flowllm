import sys

from flowllm.service.base_service import BaseService
from flowllm.utils.common_utils import load_env

load_env()

from flowllm.config.pydantic_config_parser import PydanticConfigParser
from flowllm.schema.service_config import ServiceConfig
from flowllm.context.service_context import C


def main():
    config_parser = PydanticConfigParser(ServiceConfig)
    service_config: ServiceConfig = config_parser.parse_args(sys.argv[1:])
    service_cls = C.resolve_service(service_config.backend)
    service: BaseService = service_cls(service_config)
    service()

if __name__ == "__main__":
    main()
