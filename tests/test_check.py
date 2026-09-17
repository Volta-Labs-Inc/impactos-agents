"""SR-12 (part 2): the secret/PII scan flags planted secrets and personal data,
passes on clean content, and the installed pre-commit hook refuses a commit that
stages planted PII."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import impactos_support as support
from impactos_agent import check

REAL_RUN_PY = support.CLI_DIR / "run.py"


def _git(args, cwd, **kw):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, **kw)


def _init_repo(path: Path) -> None:
    _git(["init", "-q"], path, check=True)
    _git(["config", "user.email", "t@example.org"], path, check=True)
    _git(["config", "user.name", "t"], path, check=True)


# Sensitive strings are assembled from fragments so this test FILE contains no
# literal PII/secret pattern that would trip the scanner on itself.
_SSN = "123-45-" + "6789"
_SIN = "046 454 " + "286"
_AWS = "AKIA" + "IOSFODNN7" + "EXAMPLE"
_PRIVATE_KEY = "-----BEGIN RSA " + "PRIVATE KEY-----"
_GMAIL = "real.person@" + "gmail.com"
_SECRET_LINE = "api_key" + ' = "' + "abcdEFGH1234567890xyz" + '"'


class ScanUnitTests(unittest.TestCase):
    def test_clean_text_has_no_hits(self):
        self.assertEqual(check.scan_text("just some notes, a@example.org, all fine"), [])

    def test_detects_ssn_and_private_key_and_aws_and_email(self):
        kinds = {k for k, _ in check.scan_text(
            f"SSN {_SSN}\n{_PRIVATE_KEY}\n{_AWS}\ncontact {_GMAIL}\n"
        )}
        self.assertIn("ssn", kinds)
        self.assertIn("private-key", kinds)
        self.assertIn("aws-access-key", kinds)
        self.assertIn("non-example.org email", kinds)

    def test_generic_secret_assignment(self):
        kinds = {k for k, _ in check.scan_text(_SECRET_LINE)}
        self.assertIn("generic-secret", kinds)


class StagedCheckTests(unittest.TestCase):
    def test_clean_staged_files_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            (repo / "notes.md").write_text("Harbourline notes, contact a@example.org\n", encoding="utf-8")
            _git(["add", "notes.md"], repo, check=True)
            result = check.run_check(repo, "staged")
            self.assertEqual(result.exit_code, 0, msg=result.errors)
            self.assertGreaterEqual(result.data["files_scanned"], 1)

    def test_planted_pii_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            (repo / "leak.csv").write_text(f"name,ssn\nJane Roe,{_SSN}\n", encoding="utf-8")
            _git(["add", "leak.csv"], repo, check=True)
            result = check.run_check(repo, "staged")
            self.assertEqual(result.exit_code, 1)
            self.assertTrue(any(h["kind"] == "ssn" for h in result.data["hits"]))


@unittest.skipIf(os.name == "nt", "POSIX shell hook execution differs on Windows")
class HookEndToEndTests(unittest.TestCase):
    def _install_hook(self, repo: Path) -> None:
        hooks = repo / ".hooks"
        hooks.mkdir()
        hook = hooks / "pre-commit"
        hook.write_text(
            "#!/bin/sh\n"
            f'exec "{sys.executable}" "{REAL_RUN_PY}" check\n',
            encoding="utf-8",
        )
        os.chmod(hook, 0o755)
        _git(["config", "core.hooksPath", ".hooks"], repo, check=True)

    def test_commit_with_planted_pii_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self._install_hook(repo)
            (repo / "leak.txt").write_text(f"SIN {_SIN} for Jane\n", encoding="utf-8")
            _git(["add", "leak.txt"], repo, check=True)
            committed = _git(["commit", "-m", "should be blocked"], repo)
            self.assertNotEqual(committed.returncode, 0, msg="commit must be refused")

    def test_clean_commit_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            self._install_hook(repo)
            (repo / "ok.md").write_text("clean content, a@example.org\n", encoding="utf-8")
            _git(["add", "ok.md"], repo, check=True)
            committed = _git(["commit", "-m", "clean"], repo)
            self.assertEqual(committed.returncode, 0, msg=committed.stderr)


class RepoSelfScanTests(unittest.TestCase):
    def test_this_repo_has_no_tracked_secrets_or_pii(self):
        result = check.run_check(support.REPO_ROOT, "tracked")
        self.assertEqual(result.exit_code, 0, msg=result.errors)


if __name__ == "__main__":
    unittest.main()
