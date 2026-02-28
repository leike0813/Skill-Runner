from pathlib import Path

from server.services.skill.skill_install_store import SkillInstallStore


def test_skill_install_store_lifecycle(tmp_path):
    store = SkillInstallStore(db_path=tmp_path / "skill_installs.db")
    request_id = "req-1"

    store.create_install(request_id)
    row = store.get_install(request_id)
    assert row is not None
    assert row["status"] == "queued"

    store.update_running(request_id)
    row = store.get_install(request_id)
    assert row is not None
    assert row["status"] == "running"

    store.update_succeeded(
        request_id=request_id,
        skill_id="demo-skill",
        version="1.0.0",
        action="install"
    )
    row = store.get_install(request_id)
    assert row is not None
    assert row["status"] == "succeeded"
    assert row["skill_id"] == "demo-skill"
    assert row["version"] == "1.0.0"
    assert row["action"] == "install"


def test_skill_install_store_failed(tmp_path):
    store = SkillInstallStore(db_path=tmp_path / "skill_installs.db")
    request_id = "req-2"
    store.create_install(request_id)
    store.update_failed(request_id, "boom")
    row = store.get_install(request_id)
    assert row is not None
    assert row["status"] == "failed"
    assert row["error"] == "boom"


def test_skill_install_store_list_order(tmp_path):
    store = SkillInstallStore(db_path=tmp_path / "skill_installs.db")
    store.create_install("req-1")
    store.create_install("req-2")
    rows = store.list_installs(limit=10)
    ids = [row["request_id"] for row in rows]
    assert set(ids) == {"req-1", "req-2"}
