"""
DataCache utility that supports multiple data types with local storage and data expiration functionality
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Union, Type

import pandas as pd

from flowllm.storage.cache.cache_data_handler import CacheDataHandler, DataFrameHandler, DictHandler


class DataCache:
    """
    Generic data cache utility class

    Features:
    - Support for multiple data types (DataFrame, dict, and extensible for others)
    - Support for data expiration time settings
    - Automatic cleanup of expired data
    - Recording and managing update timestamps
    - Type-specific storage formats (CSV for DataFrame, JSON for dict)
    """

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = {}

        # Register default handlers
        self.handlers: Dict[Type, CacheDataHandler] = {
            pd.DataFrame: DataFrameHandler(),
            dict: DictHandler()
        }

        self._load_metadata()

    def register_handler(self, data_type: Type, handler: CacheDataHandler):
        """
        Register a custom data handler for a specific data type

        Args:
            data_type: The data type to handle
            handler: The handler instance
        """
        self.handlers[data_type] = handler

    def _get_handler(self, data_type: Type) -> CacheDataHandler:
        """Get the appropriate handler for a data type"""
        if data_type in self.handlers:
            return self.handlers[data_type]

        # Try to find a handler for parent classes
        for registered_type, handler in self.handlers.items():
            if issubclass(data_type, registered_type):
                return handler

        raise ValueError(f"No handler registered for data type: {data_type}")

    def _load_metadata(self):
        """Load metadata"""
        if self.metadata_file.exists():
            with open(self.metadata_file) as f:
                self.metadata = json.load(f)

    def _save_metadata(self):
        """Save metadata"""
        with open(self.metadata_file, "w") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    def _get_file_path(self, key: str, data_type: Type = None) -> Path:
        """Get data file path with appropriate extension"""
        if data_type is None:
            # Try to get extension from metadata
            if key in self.metadata and 'data_type' in self.metadata[key]:
                stored_type_name = self.metadata[key]['data_type']
                if stored_type_name == 'DataFrame':
                    extension = '.csv'
                elif stored_type_name == 'dict':
                    extension = '.json'
                elif stored_type_name == 'str':
                    extension = '.txt'
                else:
                    # Try to find extension from registered handlers
                    extension = '.dat'  # Default extension
                    for registered_type, handler in self.handlers.items():
                        if registered_type.__name__ == stored_type_name:
                            extension = handler.get_file_extension()
                            break
            else:
                extension = '.dat'  # Default extension
        else:
            try:
                handler = self._get_handler(data_type)
                extension = handler.get_file_extension()
            except ValueError:
                extension = '.dat'  # Default extension

        return self.cache_dir / f"{key}{extension}"

    def _is_expired(self, key: str) -> bool:
        """Check if data is expired"""
        if key not in self.metadata:
            return True

        expire_time_str = self.metadata[key].get('expire_time')
        if not expire_time_str:
            return False  # No expiration time set, never expires

        expire_time = datetime.fromisoformat(expire_time_str)
        return datetime.now() > expire_time

    def save(self, key: str, data: Union[pd.DataFrame, dict, Any], expire_hours: Optional[float] = None,
             **handler_kwargs) -> bool:
        """
        Save data to cache

        Args:
            key: Cache key name
            data: Data to save (DataFrame, dict, or other supported types)
            expire_hours: Expiration time in hours, None means never expires
            **handler_kwargs: Additional parameters passed to the data handler

        Returns:
            bool: Whether save was successful
        """
        try:
            data_type = type(data)
            handler = self._get_handler(data_type)
            file_path = self._get_file_path(key, data_type)

            # Save data using appropriate handler
            handler_metadata = handler.save(data, file_path, **handler_kwargs)

            # Update metadata
            current_time = datetime.now()
            self.metadata[key] = {
                'created_time': current_time.isoformat(),
                'updated_time': current_time.isoformat(),
                'expire_time': (current_time + timedelta(hours=expire_hours)).isoformat() if expire_hours else None,
                'data_type': data_type.__name__,
                **handler_metadata
            }

            self._save_metadata()
            return True

        except Exception as e:
            print(f"Failed to save data: {e}")
            return False

    def load(self, key: str, auto_clean_expired: bool = True, **handler_kwargs) -> Optional[Any]:
        """
        Load data from cache

        Args:
            key: Cache key name
            auto_clean_expired: Whether to automatically clean expired data
            **handler_kwargs: Additional parameters passed to the data handler

        Returns:
            Optional[Any]: Loaded data, returns None if not exists or expired
        """
        try:
            # Check if expired
            if self._is_expired(key):
                if auto_clean_expired:
                    self.delete(key)
                    print(f"Cache '{key}' has expired and was automatically cleaned")
                return None

            file_path = self._get_file_path(key)
            if not file_path.exists():
                return None

            # Get data type from metadata
            if key not in self.metadata or 'data_type' not in self.metadata[key]:
                print(f"No data type information found for key '{key}'")
                return None

            data_type_name = self.metadata[key]['data_type']

            # Map type name back to actual type
            if data_type_name == 'DataFrame':
                data_type = pd.DataFrame
            elif data_type_name == 'dict':
                data_type = dict
            elif data_type_name == 'str':
                data_type = str
            else:
                # For other custom types, try to find a handler by checking registered types
                data_type = None
                for registered_type in self.handlers.keys():
                    if registered_type.__name__ == data_type_name:
                        data_type = registered_type
                        break

                if data_type is None:
                    print(f"Unknown data type: {data_type_name}")
                    return None

            handler = self._get_handler(data_type)

            # Load data using appropriate handler
            data = handler.load(file_path, **handler_kwargs)

            # Update last access time
            if key in self.metadata:
                self.metadata[key]['last_accessed'] = datetime.now().isoformat()
                self._save_metadata()

            return data

        except Exception as e:
            print(f"Failed to load data: {e}")
            return None

    def exists(self, key: str, check_expired: bool = True) -> bool:
        """
        Check if cache exists

        Args:
            key: Cache key name
            check_expired: Whether to check expiration status

        Returns:
            bool: Whether cache exists and is not expired
        """
        if check_expired and self._is_expired(key):
            return False

        file_path = self._get_file_path(key)
        return file_path.exists() and key in self.metadata

    def delete(self, key: str) -> bool:
        """
        Delete cache

        Args:
            key: Cache key name

        Returns:
            bool: Whether deletion was successful
        """
        try:
            file_path = self._get_file_path(key)

            # Delete data file
            if file_path.exists():
                file_path.unlink()

            # Delete metadata
            if key in self.metadata:
                del self.metadata[key]
                self._save_metadata()

            return True

        except Exception as e:
            print(f"Failed to delete cache: {e}")
            return False

    def clean_expired(self) -> int:
        """
        Clean all expired caches

        Returns:
            int: Number of cleaned caches
        """
        expired_keys = []

        for key in list(self.metadata.keys()):
            if self._is_expired(key):
                expired_keys.append(key)

        cleaned_count = 0
        for key in expired_keys:
            if self.delete(key):
                cleaned_count += 1

        return cleaned_count

    def get_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cache information

        Args:
            key: Cache key name

        Returns:
            Optional[Dict]: Cache information including creation time, update time, expiration time, etc.
        """
        if key not in self.metadata:
            return None

        info = self.metadata[key].copy()
        info['key'] = key
        info['is_expired'] = self._is_expired(key)
        info['file_path'] = str(self._get_file_path(key))

        return info

    def list_all(self, include_expired: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        List all caches

        Args:
            include_expired: Whether to include expired caches

        Returns:
            Dict: Information of all caches
        """
        result = {}

        for key in self.metadata:
            if not include_expired and self._is_expired(key):
                continue

            info = self.get_info(key)
            if info:
                result[key] = info

        return result

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dict: Cache statistics information
        """
        total_count = len(self.metadata)
        expired_count = sum(1 for key in self.metadata if self._is_expired(key))
        active_count = total_count - expired_count

        total_size = 0
        for key in self.metadata:
            file_path = self._get_file_path(key)
            if file_path.exists():
                total_size += file_path.stat().st_size

        return {
            'total_count': total_count,
            'active_count': active_count,
            'expired_count': expired_count,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': str(self.cache_dir)
        }

    def clear_all(self) -> bool:
        """
        Clear all caches

        Returns:
            bool: Whether clearing was successful
        """
        try:
            # Delete all data files (CSV, JSON, and other supported formats)
            for data_file in self.cache_dir.glob("*"):
                if data_file.is_file() and data_file.name != "metadata.json":
                    data_file.unlink()

            # Clear metadata
            self.metadata = {}
            self._save_metadata()

            return True

        except Exception as e:
            print(f"Failed to clear cache: {e}")
            return False
