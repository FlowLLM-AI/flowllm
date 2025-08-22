"""
DataFrame cache utility tests and usage examples
"""

import os
import sys
import time

import numpy as np
import pandas as pd

# Add project root directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from flowllm.storage.cache.dataframe_cache import DataFrameCache, save_dataframe, load_dataframe


def create_sample_dataframe(rows: int = 100) -> pd.DataFrame:
    """Create sample DataFrame"""
    np.random.seed(42)
    data = {
        'id': range(1, rows + 1),
        'name': [f'User_{i}' for i in range(1, rows + 1)],
        'age': np.random.randint(18, 80, rows),
        'salary': np.random.normal(50000, 15000, rows).round(2),
        'department': np.random.choice(['Engineering', 'Sales', 'Marketing', 'HR'], rows),
        'join_date': pd.date_range('2020-01-01', periods=rows, freq='D')
    }
    return pd.DataFrame(data)


def test_basic_operations():
    """Test basic operations"""
    print("=== Test Basic Operations ===")
    
    # Create cache instance
    cache = DataFrameCache("test_cache")
    
    # Create sample data
    df = create_sample_dataframe(50)
    print(f"Created DataFrame with {len(df)} rows of data")
    
    # Save data (expires after 1 hour)
    success = cache.save("employee_data", df, expire_hours=1)
    print(f"Save result: {'Success' if success else 'Failed'}")
    
    # Check if exists
    exists = cache.exists("employee_data")
    print(f"Data exists: {exists}")
    
    # Load data
    loaded_df = cache.load("employee_data")
    if loaded_df is not None:
        print(f"Successfully loaded data with {len(loaded_df)} rows")
        print("First 5 rows:")
        print(loaded_df.head())
    else:
        print("Failed to load")
    
    # Get cache info
    info = cache.get_info("employee_data")
    if info:
        print(f"\nCache info:")
        print(f"  Created time: {info['created_time']}")
        print(f"  File size: {info['file_size']} bytes")
        print(f"  Row count: {info['row_count']}")
        print(f"  Column count: {info['column_count']}")


def test_expiry_functionality():
    """Test expiry functionality"""
    print("\n=== Test Expiry Functionality ===")
    
    cache = DataFrameCache("test_cache")
    df = create_sample_dataframe(20)
    
    # Save data that expires quickly (0.001 hours = 3.6 seconds)
    cache.save("temp_data", df, expire_hours=0.001)
    print("Saved data that expires after 3.6 seconds")
    
    # Check immediately
    exists_before = cache.exists("temp_data")
    print(f"Immediate existence check: {exists_before}")
    
    # Wait for expiration
    print("Waiting 5 seconds...")
    time.sleep(5)
    
    # Check again
    exists_after = cache.exists("temp_data")
    print(f"Existence check after 5 seconds: {exists_after}")
    
    # Try to load expired data
    expired_df = cache.load("temp_data")
    print(f"Try to load expired data: {'Success' if expired_df is not None else 'Failed (automatically cleaned)'}")


def test_cache_management():
    """Test cache management functionality"""
    print("\n=== Test Cache Management Functionality ===")
    
    cache = DataFrameCache("test_cache")
    
    # Create multiple caches
    for i in range(3):
        df = create_sample_dataframe(10 + i * 10)
        cache.save(f"dataset_{i}", df, expire_hours=24)
    
    # Create an expired cache
    df_expired = create_sample_dataframe(5)
    cache.save("expired_dataset", df_expired, expire_hours=0.001)
    time.sleep(4)  # Wait for expiration
    
    # List all caches
    all_caches = cache.list_all(include_expired=True)
    print(f"Total cache count: {len(all_caches)}")
    
    active_caches = cache.list_all(include_expired=False)
    print(f"Active cache count: {len(active_caches)}")
    
    # Get statistics
    stats = cache.get_cache_stats()
    print(f"\nCache statistics:")
    print(f"  Total count: {stats['total_count']}")
    print(f"  Active count: {stats['active_count']}")
    print(f"  Expired count: {stats['expired_count']}")
    print(f"  Total size: {stats['total_size_mb']} MB")
    
    # Clean expired caches
    cleaned_count = cache.clean_expired()
    print(f"Cleaned {cleaned_count} expired caches")
    
    # Clear all caches
    cache.clear_all()
    print("Cleared all caches")


def test_convenience_functions():
    """Test convenience functions"""
    print("\n=== Test Convenience Functions ===")
    
    df = create_sample_dataframe(30)
    
    # Use convenience function to save
    success = save_dataframe("convenience_test", df, expire_hours=2)
    print(f"Convenience save: {'Success' if success else 'Failed'}")
    
    # Use convenience function to load
    loaded_df = load_dataframe("convenience_test")
    print(f"Convenience load: {'Success' if loaded_df is not None else 'Failed'}")
    
    if loaded_df is not None:
        print(f"Data shape: {loaded_df.shape}")


def test_custom_csv_params():
    """Test custom CSV parameters"""
    print("\n=== Test Custom CSV Parameters ===")
    
    cache = DataFrameCache("test_cache")
    df = create_sample_dataframe(20)
    
    # Save with custom parameters
    success = cache.save(
        "custom_csv", 
        df, 
        expire_hours=1,
        index=True,  # Save index
        sep=';'      # Use semicolon separator
    )
    print(f"Save with custom CSV parameters: {'Success' if success else 'Failed'}")
    
    # Load with corresponding parameters
    loaded_df = cache.load(
        "custom_csv",
        sep=';',           # Use semicolon separator
        index_col=0        # First column as index
    )
    
    if loaded_df is not None:
        print(f"Successfully loaded custom format data, shape: {loaded_df.shape}")
        print("Index name:", loaded_df.index.name)
    
    # Cleanup
    cache.delete("custom_csv")


if __name__ == "__main__":
    print("DataFrame Cache Utility Test")
    print("=" * 50)
    
    try:
        test_basic_operations()
        test_expiry_functionality()
        test_cache_management()
        test_convenience_functions()
        test_custom_csv_params()
        
        print("\n" + "=" * 50)
        print("All tests completed!")
        
    except Exception as e:
        print(f"Error occurred during testing: {e}")
        import traceback
        traceback.print_exc()
