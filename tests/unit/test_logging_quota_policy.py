import os
from pathlib import Path

from server.logging_config import enforce_log_dir_quota


def _touch(path: Path, size: int, mtime: int) -> None:
    path.write_bytes(b"x" * size)
    os.utime(path, (mtime, mtime))


def test_enforce_log_dir_quota_evicts_oldest_archives_only(tmp_path):
    active = tmp_path / "skill_runner.log"
    older_archive = tmp_path / "skill_runner.log.2026-03-01"
    newer_archive = tmp_path / "skill_runner.log.2026-03-02"
    unrelated = tmp_path / "other.log.2026-03-01"

    _touch(active, size=80, mtime=10)
    _touch(older_archive, size=120, mtime=1)
    _touch(newer_archive, size=120, mtime=2)
    _touch(unrelated, size=200, mtime=0)

    deleted = enforce_log_dir_quota(
        log_dir=tmp_path,
        active_log=active,
        max_bytes=250,
    )

    assert deleted == 1
    assert active.exists()
    assert not older_archive.exists()
    assert newer_archive.exists()
    assert unrelated.exists()


def test_enforce_log_dir_quota_disabled_when_max_bytes_is_zero(tmp_path):
    active = tmp_path / "skill_runner.log"
    archive = tmp_path / "skill_runner.log.2026-03-01"

    _touch(active, size=100, mtime=1)
    _touch(archive, size=100, mtime=2)

    deleted = enforce_log_dir_quota(
        log_dir=tmp_path,
        active_log=active,
        max_bytes=0,
    )

    assert deleted == 0
    assert active.exists()
    assert archive.exists()
