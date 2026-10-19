from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def matches_filters(metadata: Mapping[str, Any], filters: Mapping[str, Any] | None) -> bool:
    """Exact-match metadata filtering.

    A list on either side means "any of": `{"tag": ["a", "b"]}` matches chunks
    tagged `a` or `b`, and a chunk whose `tags` list contains the value matches too.
    """
    for key, expected in (filters or {}).items():
        value = metadata.get(key)
        expected_set = _as_set(expected)
        if isinstance(value, list | tuple | set):
            if not expected_set & set(value):
                return False
        elif value not in expected_set:
            return False
    return True


def acl_allows(metadata: Mapping[str, Any], groups: Iterable[str] | None) -> bool:
    acl = metadata.get("acl")
    if not acl:
        return True
    return bool(_as_set(acl) & set(groups or ()))


def _as_set(value: Any) -> set[Any]:
    if isinstance(value, list | tuple | set | frozenset):
        return set(value)
    return {value}
