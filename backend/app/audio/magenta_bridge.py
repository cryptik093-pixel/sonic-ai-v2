from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

BLOCKING_MAGENTA_PINS = {
    "tensorflow",
    "numpy",
    "scipy",
    "librosa",
    "numba",
}


@dataclass(frozen=True)
class MagentaRepositoryInfo:
    """Static compatibility summary for a local Magenta source checkout."""

    path: Path
    exists: bool
    setup_py_exists: bool
    readme_exists: bool
    pinned_dependencies: tuple[str, ...]
    blocking_pins: tuple[str, ...]
    can_import_in_runtime: bool
    recommendation: str


def inspect_magenta_repository(path: str | Path) -> MagentaRepositoryInfo:
    """Inspect a Magenta checkout without importing or executing Magenta code."""

    repo_path = Path(path)
    if repo_path.suffix.lower() == ".zip":
        return inspect_magenta_zip(repo_path)

    setup_py = repo_path / "setup.py"
    readme = repo_path / "README.md"
    pinned_dependencies = _extract_pinned_dependencies(setup_py) if setup_py.exists() else ()
    blocking_pins = tuple(
        dependency
        for dependency in pinned_dependencies
        if _dependency_name(dependency) in BLOCKING_MAGENTA_PINS
    )
    can_import = bool(repo_path.exists() and setup_py.exists() and not blocking_pins)
    recommendation = (
        "Magenta source can be inspected as a research reference, but this checkout "
        "must stay outside the Sonic AI V2 FastAPI runtime."
        if blocking_pins
        else "No blocking pins found in setup.py; still install only in an isolated sandbox."
    )

    return MagentaRepositoryInfo(
        path=repo_path,
        exists=repo_path.exists(),
        setup_py_exists=setup_py.exists(),
        readme_exists=readme.exists(),
        pinned_dependencies=pinned_dependencies,
        blocking_pins=blocking_pins,
        can_import_in_runtime=can_import,
        recommendation=recommendation,
    )


def inspect_magenta_zip(path: str | Path) -> MagentaRepositoryInfo:
    """Inspect the local Magenta source zip without extracting or importing it."""

    zip_path = Path(path)
    if not zip_path.exists():
        return MagentaRepositoryInfo(
            path=zip_path,
            exists=False,
            setup_py_exists=False,
            readme_exists=False,
            pinned_dependencies=(),
            blocking_pins=(),
            can_import_in_runtime=False,
            recommendation="Magenta zip was not found.",
        )

    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        setup_name = _find_archive_member(names, "setup.py")
        readme_name = _find_archive_member(names, "README.md")
        pinned_dependencies = (
            _extract_pinned_dependencies_from_text(
                archive.read(setup_name).decode("utf-8", errors="replace")
            )
            if setup_name
            else ()
        )

    blocking_pins = tuple(
        dependency
        for dependency in pinned_dependencies
        if _dependency_name(dependency) in BLOCKING_MAGENTA_PINS
    )
    return MagentaRepositoryInfo(
        path=zip_path,
        exists=True,
        setup_py_exists=setup_name is not None,
        readme_exists=readme_name is not None,
        pinned_dependencies=pinned_dependencies,
        blocking_pins=blocking_pins,
        can_import_in_runtime=False,
        recommendation=(
            "Magenta zip can be extracted for research, but it must stay "
            "outside the Sonic AI V2 FastAPI runtime."
        ),
    )


def _extract_pinned_dependencies(setup_py: Path) -> tuple[str, ...]:
    text = setup_py.read_text(encoding="utf-8", errors="replace")
    return _extract_pinned_dependencies_from_text(text)


def _extract_pinned_dependencies_from_text(text: str) -> tuple[str, ...]:
    match = re.search(r"REQUIRED_PACKAGES\s*=\s*\[(?P<body>.*?)\]", text, re.DOTALL)
    if not match:
        return ()
    return tuple(re.findall(r"['\"]([^'\"]+==[^'\"]+)['\"]", match.group("body")))


def _dependency_name(dependency: str) -> str:
    return dependency.split("==", maxsplit=1)[0].strip().lower().replace("_", "-")


def _find_archive_member(names: Mapping[str, object] | set[str], filename: str) -> str | None:
    suffix = f"/{filename}"
    for name in sorted(names):
        if name == filename or name.endswith(suffix):
            return name
    return None
