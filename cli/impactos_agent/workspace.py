"""Workspace lifecycle: ``preflight``, ``init`` and ``state``."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from . import paths
from .result import Result

HOOK_DIR_NAME = ".githooks"
HOOK_RELPATH = f"{HOOK_DIR_NAME}/pre-commit"

PRE_COMMIT_HOOK = """#!/bin/sh
# impactOS pre-commit hook (installed by `impactos init`, core.hooksPath).
# Refuses a commit that stages a secret or personal information.
ROOT="$(git rev-parse --show-toplevel)"
if [ -x "$ROOT/bin/impactos" ]; then
    exec "$ROOT/bin/impactos" check
fi
exec python3 "$ROOT/cli/run.py" check
"""

WORKSPACE_CONFIG = {
    "impactos_workspace": "1.0.0",
    "deterministic": True,
    "notes": (
        "Holds source exports, contract records, reports and provenance. Git-ignored "
        "wholesale; nothing under workspace/ is committed. No model credentials live here."
    ),
}

ACCESS_STUB = {
    "access": "local-only",
    "note": "Who may reach this workspace is managed outside version control.",
}

SOURCE_MAP_JSON_STUB = {
    "source_map_version": "1.0.0",
    "notes": "Per data type: where the organisation's data lives and whether it stays put or moves.",
    "data_types": {},
}

SOURCE_MAP_MD_STUB = """# Source map

Where each impactOS data type lives for this deployment, and whether it stays in
the existing system or moves to an optional store. Filled in during onboarding.
"""


def _writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def preflight(project_root: Path) -> Result:
    result = Result("preflight")
    version = sys.version_info
    workspace = paths.workspace_dir(project_root)
    writable = _writable(workspace if workspace.exists() else project_root)

    openpyxl_ok = True
    openpyxl_version = None
    try:
        paths.inject_vendor()
        import openpyxl  # noqa: WPS433

        openpyxl_version = openpyxl.__version__
    except Exception as exc:  # noqa: BLE001
        openpyxl_ok = False
        result.add_error(f"vendored openpyxl not importable: {exc}")

    result.data = {
        "python_version": platform.python_version(),
        "python_ok": version >= (3, 9),
        "workspace_writable": writable,
        "workspace_exists": workspace.exists(),
        "vendored_openpyxl": openpyxl_version,
        "openpyxl_ok": openpyxl_ok,
        "bundled_template_present": paths.BUNDLED_TEMPLATE.exists(),
    }
    if version < (3, 9):
        result.add_error(f"Python 3.9+ required; found {platform.python_version()}")
    if not writable:
        result.add_error(f"workspace location is not writable: {workspace}")
    if not paths.BUNDLED_TEMPLATE.exists():
        result.add_error("bundled BAI template is missing")
    result.summary = (
        f"Python {platform.python_version()}, openpyxl {openpyxl_version}, "
        f"workspace {'writable' if writable else 'NOT writable'}."
    )
    return result


def _install_hook(project_root: Path, result: Result) -> Dict[str, Any]:
    hook_dir = project_root / HOOK_DIR_NAME
    hook_dir.mkdir(parents=True, exist_ok=True)
    hook_path = project_root / HOOK_RELPATH
    hook_path.write_text(PRE_COMMIT_HOOK, encoding="utf-8")
    os.chmod(hook_path, 0o755)
    configured = False
    try:
        subprocess.run(
            ["git", "config", "core.hooksPath", HOOK_DIR_NAME],
            cwd=str(project_root), capture_output=True, text=True, check=True,
        )
        configured = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        result.add_warning("could not set git core.hooksPath (not a git repo?); hook file written")
    return {"hook_path": HOOK_RELPATH, "hooks_path_configured": configured}


def init(project_root: Path) -> Result:
    result = Result("init")
    created: List[str] = []

    workspace = paths.workspace_dir(project_root)
    workspace.mkdir(parents=True, exist_ok=True)
    for name in paths.WORKSPACE_SUBDIRS:
        (workspace / name).mkdir(parents=True, exist_ok=True)
        created.append(f"workspace/{name}/")

    gitkeep = workspace / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")
    created.append("workspace/.gitkeep")

    config = paths.config_path(project_root)
    config.write_text(json.dumps(WORKSPACE_CONFIG, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    created.append("workspace/config.json")
    access = workspace / "access.json"
    if not access.exists():
        access.write_text(json.dumps(ACCESS_STUB, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    created.append("workspace/access.json")

    for name in paths.COMMITTED_DIRS:
        directory = project_root / name
        directory.mkdir(parents=True, exist_ok=True)
        keep = directory / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
        created.append(f"{name}/")

    source_map_json = project_root / "source-map.json"
    if not source_map_json.exists():
        source_map_json.write_text(json.dumps(SOURCE_MAP_JSON_STUB, indent=2) + "\n", encoding="utf-8")
        created.append("source-map.json")
    source_map_md = project_root / "source-map.md"
    if not source_map_md.exists():
        source_map_md.write_text(SOURCE_MAP_MD_STUB, encoding="utf-8")
        created.append("source-map.md")

    hook_info = _install_hook(project_root, result)

    result.data = {
        "workspace": str(workspace),
        "created": created,
        "database": None,
        **hook_info,
    }
    result.summary = (
        f"Initialised workspace at {workspace} ({len(created)} paths); "
        f"pre-commit hook {'configured' if hook_info['hooks_path_configured'] else 'written (not configured)'}."
    )
    return result


def state(project_root: Path) -> Result:
    result = Result("state")
    workspace = paths.workspace_dir(project_root)
    initialised = workspace.exists() and paths.config_path(project_root).exists()

    def _periods(subdir: str) -> List[str]:
        base = workspace / subdir
        if not base.exists():
            return []
        return sorted(p.name for p in base.iterdir() if p.is_dir())

    records_periods = []
    state_dir = workspace / "state"
    if state_dir.exists():
        records_periods = sorted(
            p.name for p in state_dir.iterdir() if p.is_dir() and (p / "records.json").exists()
        )

    hooks_configured = False
    try:
        out = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            cwd=str(project_root), capture_output=True, text=True, check=True,
        ).stdout.strip()
        hooks_configured = out == HOOK_DIR_NAME
    except (subprocess.CalledProcessError, FileNotFoundError):
        hooks_configured = False

    result.data = {
        "initialised": initialised,
        "workspace": str(workspace),
        "source_periods": _periods("sources"),
        "record_periods": records_periods,
        "report_periods": _periods("reports"),
        "mappings": sorted(p.name for p in (project_root / "mappings").glob("*.json")) if (project_root / "mappings").exists() else [],
        "hooks_path_configured": hooks_configured,
        "database": None,
    }
    if not initialised:
        result.add_warning("workspace is not initialised; run `impactos init`")
    result.summary = (
        f"initialised={initialised}; record periods={result.data['record_periods']}; "
        f"report periods={result.data['report_periods']}"
    )
    return result
