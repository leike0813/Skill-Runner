from __future__ import annotations

from server.runtime.observability.live_journal_base import _BaseLiveJournal


class ChatReplayLiveJournal(_BaseLiveJournal):
    def __init__(self) -> None:
        super().__init__(max_events_per_run=4096, terminal_retention_sec=15 * 60)


chat_replay_live_journal = ChatReplayLiveJournal()
