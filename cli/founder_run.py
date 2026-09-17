#!/usr/bin/env python3
"""Direct entrypoint for the founder shim: put cli/ on sys.path and run it.

Used by ``bin/impactos-founder`` so no install step is needed.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from impactos_agent.founder import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
