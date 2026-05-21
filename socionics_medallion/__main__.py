"""Enable `python -m socionics_medallion` (delegates to cli)."""

from __future__ import annotations

import sys

from socionics_medallion.cli import main

if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
