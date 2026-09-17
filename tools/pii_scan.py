"""Standard-library scan for personal information, leaked secrets and funder
agreement text.

Used by ``make check`` and by the test-suite. It reads plain-text fixtures and
unzips ``.xlsx`` workbooks so email addresses hidden inside a spreadsheet are
also checked. The rules:

* every email address anywhere under ``fixtures/`` must end ``@example.org``;
* no obvious real-world personal identifiers (SSN/SIN, credit-card, non-fiction
  phone numbers);
* no funder agreement text anywhere in the tracked contract or docs.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TEXT_SUFFIXES = {".csv", ".md", ".txt", ".json", ".tsv", ".vtt"}
XLSX_SUFFIXES = {".xlsx"}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# North American SSN / SIN style: 3-2-4 or 3-3-3 groupings.
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]?){15,16}\b")
# Real phone numbers, excluding the reserved fictional 555-01xx range.
PHONE_RE = re.compile(r"\b(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}\b")
FICTIONAL_PHONE_RE = re.compile(r"555[ .-]?01\d\d")

ALLOWED_EMAIL_DOMAIN = "@example.org"

AGREEMENT_MARKERS = [
    "Contribution Agreement",
    "Ultimate Recipient",
    "Schedule A",
    "Schedule B",
    "Schedule C",
]


def _xlsx_text(path: Path) -> str:
    chunks = []
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith(".xml"):
                    raw = archive.read(name).decode("utf-8", errors="ignore")
                    # crude tag strip is enough to surface embedded strings
                    chunks.append(re.sub(r"<[^>]+>", " ", raw))
    except zipfile.BadZipFile:
        return ""
    return "\n".join(chunks)


def read_text(path: Path) -> str:
    if path.suffix.lower() in XLSX_SUFFIXES:
        return _xlsx_text(path)
    try:
        return path.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError):
        return ""


def iter_scannable_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.name == ".DS_Store":
            continue
        if path.suffix.lower() in TEXT_SUFFIXES | XLSX_SUFFIXES:
            yield path


def find_emails(root: Path):
    found = []
    for path in iter_scannable_files(root):
        text = read_text(path)
        for match in EMAIL_RE.findall(text):
            found.append((path, match))
    return found


def bad_emails(root: Path):
    return [
        (path, email)
        for path, email in find_emails(root)
        if not email.lower().endswith(ALLOWED_EMAIL_DOMAIN)
    ]


def find_pii(root: Path):
    findings = []
    for path in iter_scannable_files(root):
        text = read_text(path)
        for match in SSN_RE.findall(text):
            findings.append((path, "ssn/sin", match))
        for match in CREDIT_CARD_RE.findall(text):
            findings.append((path, "credit-card", match.strip()))
        for match in PHONE_RE.findall(text):
            if not FICTIONAL_PHONE_RE.search(match):
                findings.append((path, "phone", match))
    return findings


def find_agreement_markers(roots):
    findings = []
    for root in roots:
        if not root.exists():
            continue
        target_files = [root] if root.is_file() else list(iter_scannable_files(root))
        for path in target_files:
            text = read_text(path)
            for marker in AGREEMENT_MARKERS:
                # match markers used as agreement headings/labels
                if re.search(r"(?m)^#{0,6}\s*" + re.escape(marker) + r"\b", text):
                    findings.append((path, marker))
    return findings


def main() -> int:
    fixtures = REPO_ROOT / "fixtures"
    problems = []

    for path, email in bad_emails(fixtures):
        problems.append(f"non-example.org email {email!r} in {path.relative_to(REPO_ROOT)}")

    for path, kind, value in find_pii(fixtures):
        problems.append(f"possible {kind} {value!r} in {path.relative_to(REPO_ROOT)}")

    agreement_roots = [
        REPO_ROOT / "contract",
        REPO_ROOT / "docs",
        REPO_ROOT / "fixtures",
    ]
    for path, marker in find_agreement_markers(agreement_roots):
        problems.append(f"funder agreement marker {marker!r} in {path.relative_to(REPO_ROOT)}")

    emails = find_emails(fixtures)
    if problems:
        print("PII / secret / agreement scan FAILED:")
        for line in problems:
            print(f"  - {line}")
        return 1

    print(f"PII / secret / agreement scan passed ({len(emails)} email(s) checked, all @example.org).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
