"""Base context class for managing dynamic attributes.

This module provides a base class for context management with dictionary-like
behavior, allowing dynamic attribute access and storage.
"""


class BaseContext:
    """Base context class that provides dictionary-like attribute access.

    This class allows dynamic attribute storage and retrieval, making it
    suitable for context objects where attributes may not be known at
    class definition time.

    Attributes:
        _data: Internal dictionary storing all context data.
    """

    def __init__(self, **kwargs):
        """Initialize BaseContext with optional keyword arguments.

        Args:
            **kwargs: Initial data to store in the context.
        """
        self._data: dict = {**kwargs}

    def __getattr__(self, name: str):
        """Get attribute by name.

        Args:
            name: Attribute name to retrieve.

        Returns:
            The value associated with the attribute name.

        Raises:
            AttributeError: If the attribute is not found.
        """
        data = object.__getattribute__(self, "_data")
        if name in data:
            return data[name]
        else:
            raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")

    def __setattr__(self, name: str, value):
        """Set attribute by name.

        Args:
            name: Attribute name to set.
            value: Value to assign to the attribute.
        """
        if name == "_data":
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def __getitem__(self, name: str):
        """Get item using dictionary-style access.

        Args:
            name: Key name to retrieve.

        Returns:
            The value associated with the key.

        Raises:
            AttributeError: If the key is not found.
        """
        if name in self._data:
            return self._data[name]
        else:
            raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")

    def __setitem__(self, name: str, value):
        """Set item using dictionary-style access.

        Args:
            name: Key name to set.
            value: Value to assign to the key.
        """
        self._data[name] = value

    def __contains__(self, name: str):
        """Check if a key exists in the context.

        Args:
            name: Key name to check.

        Returns:
            True if the key exists, False otherwise.
        """
        return name in self._data

    def __repr__(self):
        """Return string representation of the context.

        Returns:
            String representation showing class name and data.
        """
        return f"{self.__class__.__name__}({self._data!r})"

    def dump(self) -> dict:
        """Dump all context data as a dictionary.

        Returns:
            A copy of all stored data as a dictionary.
        """
        return {**self._data}

    def get(self, key: str, default=None):
        """Get a value by key with optional default.

        Args:
            key: Key name to retrieve.
            default: Default value to return if key is not found.

        Returns:
            The value associated with the key, or default if not found.
        """
        return self._data.get(key, default)

    def keys(self):
        """Get all keys in the context.

        Returns:
            A view object of all keys in the context.
        """
        return self._data.keys()

    def values(self):
        """Get all values in the context.

        Returns:
            A view object of all values in the context.
        """
        return self._data.values()

    def update(self, kwargs: dict):
        """Update context with new key-value pairs.

        Args:
            kwargs: Dictionary of key-value pairs to update.
        """
        self._data.update(kwargs)

    def items(self):
        """Get all key-value pairs in the context.

        Returns:
            A view object of all key-value pairs in the context.
        """
        return self._data.items()

    def clear(self):
        """Clear all context data."""
        self._data.clear()

    def __getstate__(self):
        """Get state for pickling.

        Returns:
            The internal data dictionary.
        """
        return self._data

    def __setstate__(self, state):
        """Set state from pickling.

        Args:
            state: The data dictionary to restore.
        """
        self._data = state
