from pydantic import BaseModel

from flowllm.config.pydantic_config_parser import PydanticConfigParser


class TestConfig(BaseModel):
    name: str = "test"
    port: int = 8080
    debug: bool = False


class ServerConfig(BaseModel):
    host: str = "localhost"
    port: int = 3000
    ssl: bool = False


def test_generic_config_parser():
    """Test that the generic config parser works correctly with type hints"""

    # Test with TestConfig
    parser1 = PydanticConfigParser[TestConfig](TestConfig)
    config1 = parser1.parse_args([])

    assert isinstance(config1, TestConfig)
    assert config1.name == "test"
    assert config1.port == 8080
    assert config1.debug is False

    # Test with ServerConfig
    parser2 = PydanticConfigParser[ServerConfig](ServerConfig)
    config2 = parser2.parse_args([])

    assert isinstance(config2, ServerConfig)
    assert config2.host == "localhost"
    assert config2.port == 3000
    assert config2.ssl is False

    # Test update_config returns correct type
    updated_config1 = parser1.update_config(name="updated", port=9090)
    assert isinstance(updated_config1, TestConfig)
    assert updated_config1.name == "updated"
    assert updated_config1.port == 9090

    updated_config2 = parser2.update_config(host="example.com", ssl=True)
    assert isinstance(updated_config2, ServerConfig)
    assert updated_config2.host == "example.com"
    assert updated_config2.ssl is True


def test_backward_compatibility():
    """Test that the parser still works without explicit generic type"""

    # Without explicit generic type (backward compatibility)
    parser = PydanticConfigParser(TestConfig)
    config = parser.parse_args([])

    assert isinstance(config, TestConfig)
    assert config.name == "test"
    assert config.port == 8080


if __name__ == "__main__":
    test_generic_config_parser()
    test_backward_compatibility()
    print("All tests passed!")
