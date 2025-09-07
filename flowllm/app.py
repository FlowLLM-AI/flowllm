import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="uvicorn")

from flowllm.service.base_service import BaseService


def main():
    with BaseService.get_service(*sys.argv[1:]) as service:
        service(logo="FlowLLM")


if __name__ == "__main__":
    main()

# python -m build
# twine upload dist/*
# python -m build && twine upload dist/*
