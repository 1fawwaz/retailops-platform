"""The single seed behind every randomised derivation step.

One Generator, constructed once per pipeline run and threaded through
each step in a fixed order, so the whole pipeline is reproducible from
an empty database. See docs/data-derivation.md.
"""

RANDOM_SEED = 42
