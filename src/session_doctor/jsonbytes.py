"""Bytes-safe JSON for per-chat row bundles.

Real Hermes message rows can carry BLOB columns (e.g. display_identity),
which sqlite3 returns as bytes — and plain json.dumps chokes on those with
"Object of type bytes is not JSON serializable". This module encodes bytes
as {"$bytes": "<base64>"} on write and decodes back to bytes on read, so
bundles round-trip BLOBs exactly. Plain strings pass through untouched, so
bundles written before this codec still load fine.
"""
from __future__ import annotations
import base64
import json

_MARKER = "$bytes"


def to_jsonable(v):
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {_MARKER: base64.b64encode(bytes(v)).decode("ascii")}
    if isinstance(v, dict):
        return {k: to_jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [to_jsonable(x) for x in v]
    return v


def from_jsonable(v):
    if isinstance(v, dict):
        if set(v.keys()) == {_MARKER} and isinstance(v[_MARKER], str):
            return base64.b64decode(v[_MARKER].encode("ascii"))
        return {k: from_jsonable(x) for k, x in v.items()}
    if isinstance(v, list):
        return [from_jsonable(x) for x in v]
    return v


def dumps(obj, **kw) -> str:
    return json.dumps(to_jsonable(obj), **kw)


def loads(s: str):
    return from_jsonable(json.loads(s))


def json_default(o):
    """json.dumps(default=...) fallback so API payloads never 500 on bytes."""
    if isinstance(o, (bytes, bytearray, memoryview)):
        return to_jsonable(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
