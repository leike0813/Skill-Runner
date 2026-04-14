from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .execution_adapter import CodexExecutionAdapter

__all__ = ["CodexExecutionAdapter"]


def __getattr__(name: str):
    if name == "CodexExecutionAdapter":
        from .execution_adapter import CodexExecutionAdapter

        return CodexExecutionAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
