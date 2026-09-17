#!/usr/bin/env python3
"""Direct entrypoint: put cli/ on sys.path and run the CLI.

Used by ``bin/impactos`` and the pre-commit hook so no install step is needed.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from impactos_agent.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
