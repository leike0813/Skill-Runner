from __future__ import annotations

from server.runtime.adapter.types import RuntimeStreamRawRow

from .raw_row_coalescer import coalesce_raw_rows


def coalesce_rasp_raw_rows(
    raw_rows: list[RuntimeStreamRawRow],
    *,
    min_rows: int | None = None,
) -> tuple[list[RuntimeStreamRawRow], dict[str, int]]:
    if min_rows is None:
        return coalesce_raw_rows(raw_rows)
    return coalesce_raw_rows(raw_rows, min_rows=min_rows)

