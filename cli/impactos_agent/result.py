"""Command result envelope and verdict exit codes.

Every command returns a :class:`Result`. Exit codes follow the contract used by
the BAI verifier: ``0`` pass, ``2`` pass-with-warnings, ``1`` fail. A command
prints either a short human summary or, with ``--json``, the full envelope.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List

EXIT_PASS = 0
EXIT_WARNINGS = 2
EXIT_FAIL = 1


@dataclass
class Result:
    command: str
    data: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    summary: str = ""

    @property
    def verdict(self) -> str:
        if self.errors:
            return "fail"
        if self.warnings:
            return "warnings"
        return "pass"

    @property
    def exit_code(self) -> int:
        return {"fail": EXIT_FAIL, "warnings": EXIT_WARNINGS, "pass": EXIT_PASS}[self.verdict]

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "verdict": self.verdict,
            "exit_code": self.exit_code,
            "data": self.data,
            "warnings": self.warnings,
            "errors": self.errors,
        }

    def emit(self, as_json: bool, stream=None) -> int:
        stream = stream or sys.stdout
        if as_json:
            stream.write(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")
        else:
            self._emit_human(stream)
        return self.exit_code

    def _emit_human(self, stream) -> None:
        label = {"pass": "OK", "warnings": "WARNINGS", "fail": "FAIL"}[self.verdict]
        stream.write(f"[{self.command}] {label}\n")
        if self.summary:
            stream.write(self.summary.rstrip("\n") + "\n")
        for warning in self.warnings:
            stream.write(f"  ! {warning}\n")
        for error in self.errors:
            stream.write(f"  x {error}\n")
