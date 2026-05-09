"""Simple heads-up preflop baseline ranges for full-hand analysis."""

DEFAULT_BASELINE = {
    "name": "Generic heads-up continuing range",
    "range": "22+, A2s+, K5s+, Q8s+, J8s+, T8s+, 98s, A8o+, KTo+, QTo+, JTo",
}


def select_baseline_range(actions: list[dict]) -> dict:
    """Return a broad parser-compatible baseline for the current v1 line."""
    return dict(DEFAULT_BASELINE)
