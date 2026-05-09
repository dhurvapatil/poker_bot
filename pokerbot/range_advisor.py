"""Villain range analysis for full-hand timelines."""

from __future__ import annotations

from pokerbot.range_parser import parse_range


def fallback_range_analysis(baseline_range: dict, dead_cards: list[str] | None = None, reason: str = "Range advisor fallback used") -> dict:
    """Return a valid low-confidence range analysis from a built-in baseline."""
    estimated_range = baseline_range["range"]
    parse_range(estimated_range, dead_cards=[])
    return {
        "estimated_range": estimated_range,
        "confidence": "LOW",
        "overall_tendency": "uncertain",
        "categories": {
            "value": {"weight": "NONE", "examples": []},
            "draws": {"weight": "NONE", "examples": []},
            "bluffs": {"weight": "NONE", "examples": []},
        },
        "reasoning": reason,
        "fallback_used": True,
        "raw_response": "",
    }


def estimate_villain_range(payload: dict, hand_state: dict, baseline_range: dict) -> dict:
    """Estimate villain range.

    Phase 4 starts with robust fallback behavior; LLM prompting can deepen this
    module without changing the API/front-end contract.
    """
    return fallback_range_analysis(baseline_range)
