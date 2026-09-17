"""Secret and PII scan of staged or tracked files.

Run by the pre-commit hook (staged files) and by CI (tracked files). A hit exits
non-zero so the commit is refused. The scan reads only text files under version
control; the git-ignored ``workspace/`` tree (where personal data legitimately
lives) is never staged or tracked, so it is never scanned. Vendored third-party
code and binaries are skipped.
"""

from __future__ import annotations

import re
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

from .result import Result

TEXT_SUFFIXES = {
    ".py", ".csv", ".tsv", ".md", ".txt", ".json", ".vtt", ".yml", ".yaml",
    ".toml", ".ini", ".cfg", ".env", ".sh", ".cmd", ".bat", ".xml", ".html",
}
XLSX_SUFFIXES = {".xlsx", ".xlsm"}
SKIP_PREFIXES = ("vendor/", ".git/")

ALLOWED_EMAIL_DOMAIN = "@example.org"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
SIN_RE = re.compile(r"\b\d{3}[ -]\d{3}[ -]\d{3}\b")
CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]?){15,16}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}\b")
FICTIONAL_PHONE_RE = re.compile(r"555[ .-]?01\d\d")

SECRET_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[0-9A-Za-z_]{22,}\b")),
    ("generic-secret", re.compile(
        r"(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password|passwd)"
        r"\s*[:=]\s*['\"][^'\"\s]{16,}['\"]"
    )),
]


def _git_files(project_root: Path, mode: str) -> List[Path]:
    if mode == "tracked":
        args = ["git", "ls-files"]
    else:
        args = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"]
    try:
        output = subprocess.run(
            args, cwd=str(project_root), capture_output=True, text=True, check=True
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    files = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith(SKIP_PREFIXES):
            continue
        path = project_root / line
        if path.suffix.lower() in (TEXT_SUFFIXES | XLSX_SUFFIXES) and path.is_file():
            files.append(path)
    return files


def _read_scannable(path: Path) -> str:
    """Return scannable text for a file, unzipping xlsx so embedded strings show."""
    if path.suffix.lower() in XLSX_SUFFIXES:
        chunks = []
        try:
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.endswith(".xml"):
                        raw = archive.read(name).decode("utf-8", errors="ignore")
                        chunks.append(re.sub(r"<[^>]+>", " ", raw))
        except (zipfile.BadZipFile, OSError):
            return ""
        return "\n".join(chunks)
    return path.read_text(encoding="utf-8-sig")


def scan_text(text: str) -> List[Tuple[str, str]]:
    """Return a list of ``(kind, value)`` findings for one file's text."""
    findings: List[Tuple[str, str]] = []
    for email in EMAIL_RE.findall(text):
        if not email.lower().endswith(ALLOWED_EMAIL_DOMAIN):
            findings.append(("non-example.org email", email))
    for match in SSN_RE.findall(text):
        findings.append(("ssn", match))
    for match in SIN_RE.findall(text):
        findings.append(("sin", match))
    for match in CREDIT_CARD_RE.findall(text):
        findings.append(("credit-card", match.strip()))
    for match in PHONE_RE.findall(text):
        if not FICTIONAL_PHONE_RE.search(match):
            findings.append(("phone", match))
    for kind, pattern in SECRET_PATTERNS:
        for match in pattern.findall(text):
            snippet = match if isinstance(match, str) else match[0]
            findings.append((kind, snippet[:24] + ("…" if len(snippet) > 24 else "")))
    return findings


def run_check(project_root: Path, mode: str = "staged") -> Result:
    result = Result("check")
    files = _git_files(project_root, mode)
    scanned = 0
    hits: List[Dict[str, str]] = []
    for path in files:
        try:
            text = _read_scannable(path)
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        for kind, value in scan_text(text):
            rel = path.relative_to(project_root).as_posix()
            hits.append({"file": rel, "kind": kind, "value": value})
    result.data = {
        "mode": mode,
        "files_scanned": scanned,
        "hit_count": len(hits),
        "hits": hits,
    }
    if hits:
        for hit in hits:
            result.add_error(f"{hit['kind']} in {hit['file']}: {hit['value']}")
        result.summary = f"Refusing: {len(hits)} secret/PII hit(s) in {scanned} scanned file(s)."
    else:
        result.summary = f"No secret/PII hits in {scanned} scanned {mode} file(s)."
    return result
