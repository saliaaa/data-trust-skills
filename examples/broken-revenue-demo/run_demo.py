"""Entry point for `make demo`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data_trust.demo import main


if __name__ == "__main__":
    raise SystemExit(main())
