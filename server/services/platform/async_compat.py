from __future__ import annotations

import inspect
from typing import Any, TypeVar

T = TypeVar("T")


async def maybe_await(value: T | Any) -> T:
    if inspect.isawaitable(value):
        return await value
    return value

