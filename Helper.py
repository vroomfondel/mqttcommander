"""General helper utilities used by development scripts and examples.

Contains JSON pretty-print helpers, a complex JSON encoder, deep update for
dict/list structures, and utilities for formatting exceptions. Docstrings are
written in Google style.
"""

import datetime
import json
import traceback
import uuid
from enum import Enum
from typing import Any, Dict, List


def get_loguru_logger_info() -> None:
    """Inspect and log loguru handlers and filters for debugging."""
    # deferred import
    from loguru import logger

    def inspect_loggers() -> List[Dict[str, Any]]:
        """Return a list describing all configured loguru handlers."""
        handlers_info = []

        lvint_to_lvname: Dict[int, str] = {lvv.no: lvv.name for lvv in logger._core.levels.values()}  # type: ignore

        for handler_id, handler in logger._core.handlers.items():  # type: ignore
            info = {
                "id": handler_id,
                "level": handler._levelno,
                "level_name": lvint_to_lvname[handler._levelno],  # handler._level_name,
                "format": handler._formatter,
                "sink": str(handler._sink),
                "filter": handler._filter.__name__ if callable(handler._filter) else str(handler._filter),
                "colorize": getattr(handler, "_colorize", None),
                "serialize": getattr(handler, "_serialize", None),
            }
            handlers_info.append(info)

        return handlers_info

    def get_all_filters() -> List[Any]:
        """Return all filters registered on loguru handlers."""
        filters = []

        for handler_id, handler in logger._core.handlers.items():  # type: ignore
            filter_func = handler._filter
            if filter_func is not None:
                filters.append(
                    {
                        "handler_id": handler_id,
                        "filter": filter_func,
                        "filter_name": filter_func.__name__ if callable(filter_func) else str(filter_func),
                    }
                )

        return filters

    for handler in inspect_loggers():
        logger.info(f"Handler {handler['id']}:")
        logger.info(f"  Level: {handler['level_name']} ({handler['level']})")
        logger.info(f"  Format: {handler['format']}")
        logger.info(f"  Sink: {handler['sink']}")
        logger.info(f"  Filter: {handler['filter']}")
        logger.info("")

    # only filters:
    for f in get_all_filters():
        logger.info(f"Handler {f['handler_id']}: {f['filter_name']}")


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
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()  # strftime("%Y-%m-%d %H:%M:%S %Z")
        elif isinstance(obj, datetime.date):
            return obj.strftime("%Y-%m-%d")
        elif isinstance(obj, datetime.timedelta):
            return str(obj)
        elif isinstance(obj, dict) or isinstance(obj, list):
            robj: str = get_pretty_dict_json_no_sort(obj)
            return robj
        else:
            return json.JSONEncoder.default(self, obj)


def print_pretty_dict_json(data: Any, indent: int = 4) -> None:
    """Log a pretty-formatted JSON representation using loguru.

    Args:
        data: Any JSON-serializable structure.
        indent: Indentation to use.
    """
    from loguru import logger

    logger.info(json.dumps(data, indent=indent, sort_keys=True, cls=ComplexEncoder, default=str))


def get_pretty_dict_json(data: Any, indent: int = 4) -> str:
    """Return a pretty-formatted JSON string with keys sorted.

    Args:
        data: Any JSON-serializable structure.
        indent: Indentation to use.

    Returns:
        str: JSON string.
    """
    return json.dumps(data, indent=indent, sort_keys=True, cls=ComplexEncoder, default=str)


def get_pretty_dict_json_no_sort(data: Any, indent: int = 4) -> str:
    """Return a pretty-formatted JSON string without sorting keys.

    Args:
        data: Any JSON-serializable structure.
        indent: Indentation to use.

    Returns:
        str: JSON string.
    """
    return json.dumps(data, indent=indent, sort_keys=False, cls=ComplexEncoder, default=str)


def update_deep(base: Dict[str, Any] | List[Any], u: Dict[str, Any] | List[Any]) -> Dict[str, Any] | List[Any]:
    """Recursively merge ``u`` into ``base`` for dicts and lists.

    Args:
        base: Base dictionary or list to be mutated/returned.
        u: Update structure (dict/list) to merge in.

    Returns:
        dict | list: The updated base structure.
    """
    if isinstance(u, dict):
        if not isinstance(base, dict):
            base = {}

        for k, v in u.items():
            if isinstance(v, dict) or isinstance(v, list):
                base[k] = update_deep(base.get(k, {}), v)
            else:
                base[k] = v

    elif isinstance(u, list):
        if not isinstance(base, list):
            base = []  # may destroy the existing data if mismatch!!!

        # Stelle sicher, dass base lang genug ist
        # geht auch kompakter, aber so ist es gut lesbar
        while len(base) < len(u):
            base.append(None)

        # Stelle sicher, dass base nicht länger ist...
        # geht auch kompakter, aber so ist es gut lesbar
        while len(base) > len(u):
            base.pop()

        for i, v in enumerate(u):
            if isinstance(v, dict) or isinstance(v, list):
                base[i] = update_deep(base[i] if base[i] is not None else ({} if isinstance(v, dict) else []), v)  # type: ignore
            else:
                base[i] = v

    return base


def get_exception_tb_as_string(exc: Exception) -> str:
    """Return a full traceback string for an exception.

    Args:
        exc: Exception instance.

    Returns:
        str: Multiline traceback string.
    """
    tb1: traceback.TracebackException = traceback.TracebackException.from_exception(exc)
    tbsg = tb1.format()
    tbs = ""

    for line in tbsg:
        tbs = tbs + "\n" + line

    return tbs
