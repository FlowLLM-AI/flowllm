"""HTTP method enumeration."""

from enum import Enum


class HttpEnum(str, Enum):
    """Enumeration of HTTP methods."""

    GET = "get"
    POST = "post"
    HEAD = "head"
    PUT = "put"
    DELETE = "delete"
