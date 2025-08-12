from flowllm.context.registry_context import RegistryContext

OP_REGISTRY = RegistryContext()


def register_op(name: str = ""):
    return OP_REGISTRY.register(name)
