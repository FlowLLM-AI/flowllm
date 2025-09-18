import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any

import pandas as pd


class CacheDataHandler(ABC):
    """Abstract base class for data type handlers"""

    @abstractmethod
    def save(self, data: Any, file_path: Path, **kwargs) -> Dict[str, Any]:
        """
        Save data to file and return metadata
        
        Args:
            data: Data to save
            file_path: File path to save to
            **kwargs: Additional parameters
            
        Returns:
            Dict containing metadata about the saved data
        """
        pass

    @abstractmethod
    def load(self, file_path: Path, **kwargs) -> Any:
        """
        Load data from file
        
        Args:
            file_path: File path to load from
            **kwargs: Additional parameters
            
        Returns:
            Loaded data
        """
        pass

    @abstractmethod
    def get_file_extension(self) -> str:
        """Get the file extension for this data type"""
        pass


class DataFrameHandler(CacheDataHandler):
    """Handler for pandas DataFrame data type"""

    def save(self, data: pd.DataFrame, file_path: Path, **kwargs) -> Dict[str, Any]:
        """Save DataFrame as CSV"""
        csv_params = {
            "index": False,
            "encoding": "utf-8"
        }
        csv_params.update(kwargs)

        data.to_csv(file_path, **csv_params)

        return {
            'row_count': len(data),
            'column_count': len(data.columns),
            'file_size': file_path.stat().st_size
        }

    def load(self, file_path: Path, **kwargs) -> pd.DataFrame:
        """Load DataFrame from CSV"""
        csv_params = {
            'encoding': 'utf-8'
        }
        csv_params.update(kwargs)

        return pd.read_csv(file_path, **csv_params)

    def get_file_extension(self) -> str:
        return ".csv"


class DictHandler(CacheDataHandler):
    """Handler for dict data type"""

    def save(self, data: dict, file_path: Path, **kwargs) -> Dict[str, Any]:
        """Save dict as JSON"""
        json_params = {
            "ensure_ascii": False,
            "indent": 2
        }
        json_params.update(kwargs)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, **json_params)

        return {
            'key_count': len(data),
            'file_size': file_path.stat().st_size
        }

    def load(self, file_path: Path, **kwargs) -> dict:
        """Load dict from JSON"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_file_extension(self) -> str:
        return ".json"
