"""Accommodation search agent for student clients."""

import sys
from pathlib import Path


def main() -> None:
    """Console entry point (`accom-agent`): runs main.py's interactive flow."""
    # The modules use flat imports (e.g. `from schemas import ...`), so make this
    # folder importable before loading them.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    from main import main as run_main

    run_main()
