"""
Comprehensive tests for DataCache and CacheDataHandler classes
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any

import pandas as pd
import pytest

# Add project root directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from flowllm.storage.cache.data_cache import DataCache
from flowllm.storage.cache.cache_data_handler import CacheDataHandler, DataFrameHandler, DictHandler


class CustomHandler(CacheDataHandler):
    """Custom handler for testing custom data types"""
    
    def save(self, data: str, file_path: Path, **kwargs) -> Dict[str, Any]:
        """Save string data to text file"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(data)
        
        return {
            'length': len(data),
            'file_size': file_path.stat().st_size
        }
    
    def load(self, file_path: Path, **kwargs) -> str:
        """Load string data from text file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def get_file_extension(self) -> str:
        return ".txt"


class TestCacheDataHandlers:
    """Test individual cache data handlers"""
    
    def test_dataframe_handler(self):
        """Test DataFrameHandler"""
        handler = DataFrameHandler()
        
        # Create test DataFrame
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['Alice', 'Bob', 'Charlie'],
            'age': [25, 30, 35]
        })
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.csv"
            
            # Test save
            metadata = handler.save(df, file_path)
            assert file_path.exists()
            assert metadata['row_count'] == 3
            assert metadata['column_count'] == 3
            assert 'file_size' in metadata
            
            # Test load
            loaded_df = handler.load(file_path)
            pd.testing.assert_frame_equal(df, loaded_df)
            
            # Test extension
            assert handler.get_file_extension() == ".csv"
    
    def test_dict_handler(self):
        """Test DictHandler"""
        handler = DictHandler()
        
        # Create test dict
        data = {
            'name': 'Test',
            'value': 42,
            'items': ['a', 'b', 'c']
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.json"
            
            # Test save
            metadata = handler.save(data, file_path)
            assert file_path.exists()
            assert metadata['key_count'] == 3
            assert 'file_size' in metadata
            
            # Test load
            loaded_data = handler.load(file_path)
            assert loaded_data == data
            
            # Test extension
            assert handler.get_file_extension() == ".json"
    
    def test_custom_handler(self):
        """Test custom handler"""
        handler = CustomHandler()
        
        # Create test string data
        data = "This is a test string with some content."
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.txt"
            
            # Test save
            metadata = handler.save(data, file_path)
            assert file_path.exists()
            assert metadata['length'] == len(data)
            assert 'file_size' in metadata
            
            # Test load
            loaded_data = handler.load(file_path)
            assert loaded_data == data
            
            # Test extension
            assert handler.get_file_extension() == ".txt"


class TestDataCache:
    """Test DataCache class"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = DataCache(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup after each test method"""
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_basic_operations_dataframe(self):
        """Test basic operations with DataFrame"""
        # Create test DataFrame
        df = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'value': [10, 20, 30, 40, 50]
        })
        
        # Test save
        success = self.cache.save("test_df", df, expire_hours=1)
        assert success is True
        
        # Test exists
        assert self.cache.exists("test_df") is True
        assert self.cache.exists("nonexistent") is False
        
        # Test load
        loaded_df = self.cache.load("test_df")
        assert loaded_df is not None
        pd.testing.assert_frame_equal(df, loaded_df)
        
        # Test info
        info = self.cache.get_info("test_df")
        assert info is not None
        assert info['data_type'] == 'DataFrame'
        assert info['row_count'] == 5
        assert info['column_count'] == 2
        assert 'created_time' in info
        assert 'file_path' in info
        
        # Test delete
        success = self.cache.delete("test_df")
        assert success is True
        assert self.cache.exists("test_df") is False
    
    def test_basic_operations_dict(self):
        """Test basic operations with dict"""
        # Create test dict
        data = {
            'users': ['Alice', 'Bob', 'Charlie'],
            'count': 3,
            'active': True
        }
        
        # Test save
        success = self.cache.save("test_dict", data, expire_hours=2)
        assert success is True
        
        # Test exists
        assert self.cache.exists("test_dict") is True
        
        # Test load
        loaded_data = self.cache.load("test_dict")
        assert loaded_data is not None
        assert loaded_data == data
        
        # Test info
        info = self.cache.get_info("test_dict")
        assert info is not None
        assert info['data_type'] == 'dict'
        assert info['key_count'] == 3
        
        # Test delete
        success = self.cache.delete("test_dict")
        assert success is True
        assert self.cache.exists("test_dict") is False
    
    def test_expiration_functionality(self):
        """Test cache expiration"""
        data = {'test': 'value'}
        
        # Save data that expires quickly (0.001 hours ≈ 3.6 seconds)
        success = self.cache.save("temp_data", data, expire_hours=0.001)
        assert success is True
        
        # Should exist immediately
        assert self.cache.exists("temp_data") is True
        
        # Should be loadable immediately
        loaded_data = self.cache.load("temp_data", auto_clean_expired=False)
        assert loaded_data == data
        
        # Wait for expiration
        time.sleep(4)
        
        # Should be expired now
        assert self.cache.exists("temp_data") is False
        
        # Loading should return None and auto-clean
        loaded_data = self.cache.load("temp_data", auto_clean_expired=True)
        assert loaded_data is None
    
    def test_no_expiration(self):
        """Test cache without expiration"""
        data = {'persistent': 'data'}
        
        # Save without expiration
        success = self.cache.save("persistent_data", data)
        assert success is True
        
        # Should exist
        assert self.cache.exists("persistent_data") is True
        
        # Info should show no expiration
        info = self.cache.get_info("persistent_data")
        assert info['expire_time'] is None
        assert info['is_expired'] is False
    
    def test_custom_handler_registration(self):
        """Test registering and using custom handlers"""
        # Register custom handler for str type
        custom_handler = CustomHandler()
        self.cache.register_handler(str, custom_handler)
        
        # Test save/load with custom handler
        test_string = "This is a test string for custom handler"
        
        success = self.cache.save("custom_data", test_string, expire_hours=1)
        assert success is True
        
        loaded_string = self.cache.load("custom_data")
        assert loaded_string == test_string
        
        # Check file extension is correct
        info = self.cache.get_info("custom_data")
        assert info['file_path'].endswith('.txt')
    
    def test_cache_management(self):
        """Test cache management operations"""
        # Create multiple caches
        df1 = pd.DataFrame({'a': [1, 2, 3]})
        df2 = pd.DataFrame({'b': [4, 5, 6]})
        dict1 = {'key1': 'value1'}
        dict2 = {'key2': 'value2'}
        
        # Save some data
        self.cache.save("df1", df1, expire_hours=24)
        self.cache.save("df2", df2, expire_hours=24)
        self.cache.save("dict1", dict1, expire_hours=24)
        self.cache.save("dict2", dict2, expire_hours=0.001)  # This will expire
        
        # Wait for one to expire
        time.sleep(4)
        
        # Test list_all
        all_caches = self.cache.list_all(include_expired=True)
        assert len(all_caches) == 4
        
        active_caches = self.cache.list_all(include_expired=False)
        assert len(active_caches) == 3  # One should be expired
        
        # Test cache stats
        stats = self.cache.get_cache_stats()
        assert stats['total_count'] == 4
        assert stats['active_count'] == 3
        assert stats['expired_count'] == 1
        assert stats['total_size_bytes'] > 0
        assert 'cache_dir' in stats
        
        # Test clean expired
        cleaned_count = self.cache.clean_expired()
        assert cleaned_count == 1
        
        # After cleaning, should have 3 total
        stats_after = self.cache.get_cache_stats()
        assert stats_after['total_count'] == 3
        assert stats_after['expired_count'] == 0
    
    def test_clear_all(self):
        """Test clearing all caches"""
        # Create some data
        df = pd.DataFrame({'x': [1, 2, 3]})
        data = {'test': 'value'}
        
        self.cache.save("df_data", df)
        self.cache.save("dict_data", data)
        
        # Verify they exist
        assert self.cache.exists("df_data") is True
        assert self.cache.exists("dict_data") is True
        
        # Clear all
        success = self.cache.clear_all()
        assert success is True
        
        # Verify they're gone
        assert self.cache.exists("df_data") is False
        assert self.cache.exists("dict_data") is False
        
        # Stats should show empty cache
        stats = self.cache.get_cache_stats()
        assert stats['total_count'] == 0
    
    def test_handler_kwargs(self):
        """Test passing kwargs to handlers"""
        df = pd.DataFrame({
            'name': ['Alice', 'Bob'],
            'age': [25, 30]
        })
        
        # Save with custom CSV parameters
        success = self.cache.save(
            "custom_csv", 
            df, 
            expire_hours=1,
            index=True,  # Save index
            sep=';'      # Use semicolon separator
        )
        assert success is True
        
        # Load with corresponding parameters
        loaded_df = self.cache.load(
            "custom_csv",
            sep=';',           # Use semicolon separator
            index_col=0        # First column as index
        )
        
        assert loaded_df is not None
        # The loaded DataFrame will have the index from the CSV
        assert len(loaded_df) == 2
        assert list(loaded_df.columns) == ['name', 'age']
    
    def test_error_handling(self):
        """Test error handling scenarios"""
        # Test loading non-existent cache
        result = self.cache.load("nonexistent")
        assert result is None
        
        # Test getting info for non-existent cache
        info = self.cache.get_info("nonexistent")
        assert info is None
        
        # Test deleting non-existent cache (should not raise error)
        success = self.cache.delete("nonexistent")
        assert success is True  # Should return True even if nothing to delete
        
        # Test unsupported data type
        class UnsupportedType:
            pass
        
        unsupported_data = UnsupportedType()
        success = self.cache.save("unsupported", unsupported_data)
        assert success is False  # Should fail gracefully


def create_sample_dataframe(rows: int = 10) -> pd.DataFrame:
    """Create a sample DataFrame for testing"""
    import numpy as np
    np.random.seed(42)
    
    data = {
        'id': range(1, rows + 1),
        'name': [f'User_{i}' for i in range(1, rows + 1)],
        'value': np.random.randint(1, 100, rows),
        'category': np.random.choice(['A', 'B', 'C'], rows)
    }
    return pd.DataFrame(data)


def test_integration_example():
    """Integration test showing typical usage"""
    print("=== Integration Test Example ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = DataCache(temp_dir)
        
        # Test with DataFrame
        df = create_sample_dataframe(20)
        print(f"Created DataFrame with {len(df)} rows")
        
        # Save DataFrame
        success = cache.save("sample_data", df, expire_hours=1)
        print(f"Save DataFrame: {'Success' if success else 'Failed'}")
        
        # Test with dict
        config_data = {
            'database_url': 'postgresql://localhost:5432/mydb',
            'cache_timeout': 3600,
            'features': ['feature1', 'feature2', 'feature3'],
            'settings': {
                'debug': True,
                'log_level': 'INFO'
            }
        }
        
        # Save dict
        success = cache.save("config", config_data, expire_hours=2)
        print(f"Save dict: {'Success' if success else 'Failed'}")
        
        # Load and verify
        loaded_df = cache.load("sample_data")
        loaded_config = cache.load("config")
        
        print(f"Load DataFrame: {'Success' if loaded_df is not None else 'Failed'}")
        print(f"Load dict: {'Success' if loaded_config is not None else 'Failed'}")
        
        # Show cache stats
        stats = cache.get_cache_stats()
        print(f"\nCache Statistics:")
        print(f"  Total items: {stats['total_count']}")
        print(f"  Total size: {stats['total_size_mb']} MB")
        print(f"  Cache directory: {stats['cache_dir']}")
        
        # List all caches
        all_caches = cache.list_all()
        print(f"\nCached items:")
        for key, info in all_caches.items():
            print(f"  {key}: {info['data_type']} (created: {info['created_time'][:19]})")


if __name__ == "__main__":
    # Run integration test
    test_integration_example()
    
    print("\n" + "=" * 50)
    print("Run 'pytest test_cache.py -v' for full test suite")
