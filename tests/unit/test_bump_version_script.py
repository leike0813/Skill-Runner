from pathlib import Path

from scripts import bump_version


def _write_pyproject(path: Path, version: str = "0.7.2") -> None:
    path.write_text(
        "\n".join(
            [
                "[project]",
                'name = "skill-runner"',
                f'version = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_bump_version_updates_only_project_version(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    _write_pyproject(pyproject)

    bump_version.write_project_version(pyproject, "v0.7.3")

    assert bump_version.read_project_version(pyproject) == "0.7.3"
    assert 'name = "skill-runner"' in pyproject.read_text(encoding="utf-8")


def test_check_tag_passes_when_tag_matches_project_version(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    _write_pyproject(pyproject, "0.7.3")

    bump_version.check_tag(pyproject, "v0.7.3")


def test_check_tag_fails_when_tag_does_not_match_project_version(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    _write_pyproject(pyproject, "0.7.2")

    try:
        bump_version.check_tag(pyproject, "v0.7.3")
    except bump_version.VersionError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("expected VersionError")


def test_invalid_semver_is_rejected():
    for value in ("0.7", "0.7.3.1", "release-0.7.3", "01.7.3"):
        try:
            bump_version.normalize_version(value)
        except bump_version.VersionError:
            continue
        raise AssertionError(f"expected VersionError for {value}")
