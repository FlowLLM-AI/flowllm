import sys

from flowllm.utils.common_utils import load_env

load_env()


def main():
    from flowllm.service.base_service import BaseService

    BaseService.get_service(*sys.argv[1:])()


if __name__ == "__main__":
    main()

# python -m build
# twine upload dist/*
