"""Content block type enumeration for multimodal content."""

from enum import Enum


class ContentBlockType(str, Enum):
    """Enumeration of content block types in multimodal responses."""

    TEXT = "text"
    IMAGE_URL = "image_url"
    AUDIO = "audio"
    VIDEO = "video"
