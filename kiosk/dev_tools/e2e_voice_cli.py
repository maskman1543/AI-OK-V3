"""Compatibility CLI for the GUI-ready voice assistant orchestrator."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kiosk.orchestrator import main


if __name__ == "__main__":
    main()
