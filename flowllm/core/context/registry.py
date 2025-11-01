"""Registry for class registration and lookup.

This module provides a registry class for managing class registrations
with dynamic lookup capabilities.
"""

from .base_context import BaseContext
from ..utils import camel_to_snake


class Registry(BaseContext):
    """Registry for storing and retrieving registered classes.

    This class provides a decorator-based registration system for classes,
    allowing dynamic class lookup by name.
    """

    def register(self, name: str = "", add_cls: bool = True):
        """Register a class in the registry.

        Args:
            name: Name to register the class under. If empty, the class
                name will be converted to snake_case.
            add_cls: Whether to actually add the class to the registry.
                Defaults to True.

        Returns:
            Decorator function that registers the class when applied.
        """

        def decorator(cls):
            """Decorator function that registers the class.

            Args:
                cls: The class to register.

            Returns:
                The class unchanged (for use as decorator).
            """
            if add_cls:
                class_name = name if name else camel_to_snake(cls.__name__)
                self._data[class_name] = cls
            return cls

        return decorator
