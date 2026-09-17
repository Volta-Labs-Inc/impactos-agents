"""Enable ``python3 -m impactos_agent`` (cli/ must be on sys.path)."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
