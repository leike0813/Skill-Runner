from __future__ import annotations

from .live_journal_base import _BaseLiveJournal


class FcmpLiveJournal(_BaseLiveJournal):
    def __init__(self) -> None:
        super().__init__(max_events_per_run=4096, terminal_retention_sec=15 * 60)


fcmp_live_journal = FcmpLiveJournal()
