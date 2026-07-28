"""Run the ETL pipeline: Stage 1 Task 3, steps (a) through (g).

Reproducible from an empty database -- see docs/data-derivation.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.etl.clean import clean, load_raw  # noqa: E402


def step_a_clean() -> None:
    print("Step (a): clean")
    print("Loading raw data...")
    raw_df = load_raw()

    _, counts = clean(raw_df)
    for key, value in counts.items():
        print(f"  {key}: {value}")


def main() -> None:
    step_a_clean()


if __name__ == "__main__":
    main()
