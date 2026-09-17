"""Generate and verify ``contract/release-manifest.json``.

The manifest records the contract version and the sha256 of every contract file
so a consumer can confirm it has the exact bytes the contract was released with.

Usage:
    python3 tools/release_manifest.py generate   # (re)write the manifest
    python3 tools/release_manifest.py check       # verify hashes match on disk
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = REPO_ROOT / "contract"
MANIFEST_PATH = CONTRACT_DIR / "release-manifest.json"

# The contract files whose bytes the manifest pins. The manifest itself and the
# JSON Schemas (validation tooling) are excluded.
CONTRACT_FILES = [
    "VERSION",
    "data-contract.json",
    "tracks.json",
    "reporting-profile.json",
    "acceptance-rules.json",
    "exports/bai-template-v5.json",
]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _version() -> str:
    return (CONTRACT_DIR / "VERSION").read_text(encoding="utf-8").strip()


def build_manifest() -> dict:
    files = []
    for rel in CONTRACT_FILES:
        path = CONTRACT_DIR / rel
        files.append(
            {
                "path": rel,
                "sha256": sha256_of(path),
                "bytes": path.stat().st_size,
            }
        )
    return {
        "contract_version": _version(),
        "generated_at": _dt.datetime(2026, 9, 16, tzinfo=_dt.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "notes": "sha256 of each contract file; regenerate with tools/release_manifest.py generate.",
        "files": files,
    }


def generate() -> int:
    manifest = build_manifest()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST_PATH.relative_to(REPO_ROOT)} ({len(manifest['files'])} files)")
    return 0


def check() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    problems = []

    if manifest.get("contract_version") != _version():
        problems.append(
            f"contract_version {manifest.get('contract_version')!r} != VERSION {_version()!r}"
        )

    listed = {entry["path"] for entry in manifest["files"]}
    expected = set(CONTRACT_FILES)
    if listed != expected:
        problems.append(f"manifest files {sorted(listed)} != expected {sorted(expected)}")

    for entry in manifest["files"]:
        path = CONTRACT_DIR / entry["path"]
        if not path.exists():
            problems.append(f"missing file {entry['path']}")
            continue
        actual = sha256_of(path)
        if actual != entry["sha256"]:
            problems.append(f"sha256 mismatch for {entry['path']}: {actual} != {entry['sha256']}")
        if "bytes" in entry and entry["bytes"] != path.stat().st_size:
            problems.append(f"byte-count mismatch for {entry['path']}")

    if problems:
        print("release-manifest check FAILED:")
        for line in problems:
            print(f"  - {line}")
        return 1
    print(f"release-manifest check passed ({len(manifest['files'])} files verified).")
    return 0


def main(argv) -> int:
    if len(argv) != 2 or argv[1] not in {"generate", "check"}:
        print(__doc__)
        return 2
    return generate() if argv[1] == "generate" else check()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
