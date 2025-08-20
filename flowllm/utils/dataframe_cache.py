"""
DataFrame cache utility that supports local CSV file storage and reading with data expiration functionality
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd


class DataFrameCache:
    """
    DataFrame cache utility class
    
    Features:
    - Support for pandas DataFrame local CSV storage and reading
    - Support for data expiration time settings
    - Automatic cleanup of expired data
    - Recording and managing update timestamps
    """

    def __init__(self, cache_dir: str = "cache_df"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = {}
        self._load_metadata()

    def _load_metadata(self):
        """Load metadata"""
        if self.metadata_file.exists():
            with open(self.metadata_file) as f:
                self.metadata = json.load(f)

    def _save_metadata(self):
        """Save metadata"""
        with open(self.metadata_file, "w") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    def _get_file_path(self, key: str) -> Path:
        """Get data file path"""
        return self.cache_dir / f"{key}.csv"

    def _is_expired(self, key: str) -> bool:
        """Check if data is expired"""
        if key not in self.metadata:
            return True

        expire_time_str = self.metadata[key].get('expire_time')
        if not expire_time_str:
            return False  # No expiration time set, never expires

        expire_time = datetime.fromisoformat(expire_time_str)
        return datetime.now() > expire_time

    def save(self, key: str, df: pd.DataFrame, expire_hours: Optional[float] = None,
             **csv_kwargs) -> bool:
        """
        Save DataFrame to cache
        
        Args:
            key: Cache key name
            df: DataFrame to save
            expire_hours: Expiration time in hours, None means never expires
            **csv_kwargs: Additional parameters passed to pandas to_csv
            
        Returns:
            bool: Whether save was successful
        """
        try:
            file_path = self._get_file_path(key)

            # Set default CSV parameters
            csv_params = {
                "index": False,
                "encoding": "utf-8"
            }
            csv_params.update(csv_kwargs)

            # Save CSV file
            df.to_csv(file_path, **csv_params)

            # Update metadata
            current_time = datetime.now()
            self.metadata[key] = {
                'created_time': current_time.isoformat(),
                'updated_time': current_time.isoformat(),
                'expire_time': (current_time + timedelta(hours=expire_hours)).isoformat() if expire_hours else None,
                'file_size': file_path.stat().st_size,
                'row_count': len(df),
                'column_count': len(df.columns)
            }

            self._save_metadata()
            return True

        except Exception as e:
            print(f"Failed to save DataFrame: {e}")
            return False

    def load(self, key: str, auto_clean_expired: bool = True, **csv_kwargs) -> Optional[pd.DataFrame]:
        """
        Load DataFrame from cache
        
        Args:
            key: Cache key name
            auto_clean_expired: Whether to automatically clean expired data
            **csv_kwargs: Additional parameters passed to pandas read_csv
            
        Returns:
            Optional[pd.DataFrame]: Loaded DataFrame, returns None if not exists or expired
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

            # Set default CSV parameters
            csv_params = {
                'encoding': 'utf-8'
            }
            csv_params.update(csv_kwargs)

            # Read CSV file
            df = pd.read_csv(file_path, **csv_params)

            # Update last access time
            if key in self.metadata:
                self.metadata[key]['last_accessed'] = datetime.now().isoformat()
                self._save_metadata()

            return df

        except Exception as e:
            print(f"Failed to load DataFrame: {e}")
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

            # Delete CSV file
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
            # Delete all CSV files
            for csv_file in self.cache_dir.glob("*.csv"):
                csv_file.unlink()

            # Clear metadata
            self.metadata = {}
            self._save_metadata()

            return True

        except Exception as e:
            print(f"Failed to clear cache: {e}")
            return False


# Create default instance
default_cache = DataFrameCache()


# Convenience functions
def save_dataframe(key: str, df: pd.DataFrame, expire_hours: Optional[float] = None,
                   **csv_kwargs) -> bool:
    """Convenience function: Save DataFrame"""
    return default_cache.save(key, df, expire_hours, **csv_kwargs)


def load_dataframe(key: str, **csv_kwargs) -> Optional[pd.DataFrame]:
    """Convenience function: Load DataFrame"""
    return default_cache.load(key, **csv_kwargs)


def dataframe_exists(key: str) -> bool:
    """Convenience function: Check if DataFrame exists"""
    return default_cache.exists(key)


def delete_dataframe(key: str) -> bool:
    """Convenience function: Delete DataFrame cache"""
    return default_cache.delete(key)


def clean_expired_dataframes() -> int:
    """Convenience function: Clean expired DataFrame caches"""
    return default_cache.clean_expired()
