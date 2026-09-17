"""Source systems unchanged: a full init -> parse -> apply -> export run never
modifies any source file, and the parse layer contains no write primitives."""

from __future__ import annotations

import hashlib
import re
import tempfile
import unittest
from pathlib import Path

import impactos_support as support


def _hash_tree(root: Path) -> dict:
    digests = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digests[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


class SourcesUntouchedTests(unittest.TestCase):
    def test_full_run_does_not_modify_any_source_file(self):
        before = _hash_tree(support.FIXTURE)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            support.run("init", project_root=project)
            support.build_records(project)  # parses the fixture CSV + xlsx, applies mappings
            support.export(project)
        after = _hash_tree(support.FIXTURE)
        self.assertEqual(before, after, msg="a source file under fixtures/ was modified")

    def test_parse_layer_has_no_write_primitives(self):
        # The module that reads source files must never write. This is a static
        # guarantee complementing the empirical hash check above.
        text = (support.CLI_DIR / "impactos_agent" / "parsers.py").read_text(encoding="utf-8")
        self.assertNotIn(".write_text(", text)
        self.assertNotIn(".write_bytes(", text)
        self.assertFalse(re.search(r"open\([^)]*['\"][wax]", text), "parsers.py must not open files for writing")


if __name__ == "__main__":
    unittest.main()
