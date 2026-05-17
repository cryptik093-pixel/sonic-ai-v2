from pathlib import Path
from zipfile import ZipFile

from app.audio.magenta_bridge import inspect_magenta_repository, inspect_magenta_zip


def test_inspect_magenta_repository_blocks_conflicting_runtime_pins(tmp_path: Path) -> None:
    repo = tmp_path / "magenta-main"
    repo.mkdir()
    (repo / "README.md").write_text("Magenta", encoding="utf-8")
    (repo / "setup.py").write_text(
        """
REQUIRED_PACKAGES = [
    'tensorflow == 2.9.1',
    'numpy == 1.21.6',
    'scipy == 1.7.3',
    'librosa == 0.7.2',
]
""",
        encoding="utf-8",
    )

    info = inspect_magenta_repository(repo)

    assert info.exists is True
    assert info.setup_py_exists is True
    assert info.readme_exists is True
    assert info.can_import_in_runtime is False
    assert "tensorflow == 2.9.1" in info.blocking_pins
    assert "librosa == 0.7.2" in info.blocking_pins


def test_inspect_missing_magenta_repository_is_safe() -> None:
    info = inspect_magenta_repository("does-not-exist")

    assert info.exists is False
    assert info.setup_py_exists is False
    assert info.pinned_dependencies == ()
    assert info.can_import_in_runtime is False


def test_inspect_magenta_zip_reads_setup_without_extracting(tmp_path: Path) -> None:
    archive_path = tmp_path / "magenta-main.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("magenta-main/README.md", "Magenta")
        archive.writestr(
            "magenta-main/setup.py",
            """
REQUIRED_PACKAGES = [
    'tensorflow == 2.9.1',
    'librosa == 0.7.2',
]
""",
        )

    info = inspect_magenta_zip(archive_path)

    assert info.exists is True
    assert info.setup_py_exists is True
    assert info.readme_exists is True
    assert info.can_import_in_runtime is False
    assert info.blocking_pins == ("tensorflow == 2.9.1", "librosa == 0.7.2")
