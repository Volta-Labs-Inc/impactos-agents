"""Filesystem locations and vendored-dependency injection.

The CLI ships a vendored copy of ``openpyxl`` under ``vendor/`` and injects it on
``sys.path`` so no global install is needed. It also locates the repository root
(which holds ``contract/`` and the bundled BAI template) and resolves the
workspace tree beneath the current project directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

# cli/impactos_agent/paths.py -> parents[2] is the repository root.
PACKAGE_DIR = Path(__file__).resolve().parent
CLI_DIR = PACKAGE_DIR.parent
REPO_ROOT = CLI_DIR.parent

VENDOR_DIR = REPO_ROOT / "vendor"
CONTRACT_DIR = REPO_ROOT / "contract"
ASSETS_DIR = PACKAGE_DIR / "assets"

# The bundled BAI v5 template every export is built from. A copy travels with
# the package so export never depends on files outside the CLI.
BUNDLED_TEMPLATE = ASSETS_DIR / "bai-template-v5.xlsx"

# The BAI export column->contract mapping (issue #2 artifact).
BAI_EXPORT_CONTRACT = CONTRACT_DIR / "exports" / "bai-template-v5.json"
DATA_CONTRACT = CONTRACT_DIR / "data-contract.json"
TRACKS = CONTRACT_DIR / "tracks.json"
REPORTING_PROFILE = CONTRACT_DIR / "reporting-profile.json"


def inject_vendor() -> None:
    """Put the vendored dependencies at the front of ``sys.path`` (idempotent)."""
    if VENDOR_DIR.exists():
        vendored = str(VENDOR_DIR)
        if vendored not in sys.path:
            sys.path.insert(0, vendored)


# Workspace subdirectories created by ``init``. The whole tree is git-ignored;
# only ``.gitkeep`` is committed (see .gitignore).
WORKSPACE_SUBDIRS = [
    "sources",
    "reports",
    "state",
    "provenance",
    "briefs",
    "evidence",
]

# Committed (version-controlled) directories the workspace flow relies on.
COMMITTED_DIRS = [
    "mappings",
    "operating-notes",
]


def workspace_dir(project_root: Path) -> Path:
    return project_root / "workspace"


def config_path(project_root: Path) -> Path:
    return workspace_dir(project_root) / "config.json"
