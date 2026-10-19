"""Run from a checkout without requiring pip or a virtual environment."""
from pathlib import Path
import sys

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / "src"))
from kstack.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
