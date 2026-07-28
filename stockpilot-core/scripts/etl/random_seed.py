"""The single seed behind every randomised derivation step.

One Generator, constructed once per pipeline run and threaded through
each step in a fixed order, so the whole pipeline is reproducible from
an empty database. See docs/data-derivation.md.
"""

import numpy as np

RANDOM_SEED = 42


def create_rng() -> np.random.Generator:
    return np.random.default_rng(RANDOM_SEED)
