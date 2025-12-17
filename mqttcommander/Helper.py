"""Helper utilities for JSON pretty printing and complex encoding.

This module provides convenience functions to pretty print dictionaries and
serialize complex objects (datetime, UUID, timedelta, etc.) to JSON.
"""

import json
from datetime import datetime, date, timedelta
from typing import Any
from uuid import UUID


def print_pretty_dict_json(data: Any, indent: int = 4) -> None:
    """Print a dictionary as pretty-formatted JSON.

    Args:
        data: Any JSON-serializable data structure.
        indent: Indentation level for formatting.
    """
    print(json.dumps(data, indent=indent, sort_keys=True, cls=ComplexEncoder, default=str))


def get_pretty_dict_json(data: Any, indent: int = 4) -> str:
    """Return a pretty-formatted JSON string with keys sorted.

    Args:
        data: Any JSON-serializable data structure.
        indent: Indentation level for formatting.

    Returns:
        str: JSON string.
    """
    return json.dumps(data, indent=indent, sort_keys=True, cls=ComplexEncoder, default=str)


def get_pretty_dict_json_no_sort(data: Any, indent: int = 4) -> str:
    """Return a pretty-formatted JSON string without sorting keys.

    Args:
        data: Any JSON-serializable data structure.
        indent: Indentation level for formatting.

    Returns:
        str: JSON string.
    """
    return json.dumps(data, indent=indent, sort_keys=False, cls=ComplexEncoder, default=str)


class ComplexEncoder(json.JSONEncoder):
    """JSON encoder that supports common Python types used in this project."""

    def default(self, obj: Any) -> Any:
        """Serialize complex objects to JSON-friendly representations.

        Args:
            obj: Object to serialize.

        Returns:
            Any: JSON-serializable representation.
        """
        if hasattr(obj, "repr_json"):
            return obj.repr_json()
        elif hasattr(obj, "as_string"):
            return obj.as_string()
        elif isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()  # strftime("%Y-%m-%d %H:%M:%S %Z")
        elif isinstance(obj, date):
            return obj.strftime("%Y-%m-%d")
        elif isinstance(obj, timedelta):
            return str(obj)
        elif isinstance(obj, dict) or isinstance(obj, list):
            robj: str = get_pretty_dict_json_no_sort(obj)
            return robj
        else:
            return json.JSONEncoder.default(self, obj)
