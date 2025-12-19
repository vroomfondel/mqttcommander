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


def compare_tasmota_versions(v1: str, v2: str) -> int:
    """Compare two Tasmota version strings.

    Args:
        v1: First version string (e.g., "13.2.0(tasmota)").
        v2: Second version string.

    Returns:
        int: -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2.
    """
    import re

    def parse_version(v: str) -> list[int]:
        """Extract the major.minor.patch part from a version string.

        Args:
            v: Version string.

        Returns:
            list[int]: [major, minor, patch] or [0, 0, 0] if no match.
        """
        # Extract the major.minor.patch part
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
        if match:
            return [int(x) for x in match.groups()]
        return [0, 0, 0]

    parts1 = parse_version(v1)
    parts2 = parse_version(v2)

    for p1, p2 in zip(parts1, parts2):
        if p1 < p2:
            return -1
        if p1 > p2:
            return 1
    return 0
