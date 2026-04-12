"""Monte Carlo equity calculator using treys."""

from __future__ import annotations

import random
from treys import Card, Evaluator, Deck

# Single shared evaluator instance (stateless, thread-safe for reads)
_evaluator = Evaluator()


# Static full deck for deterministic Monte Carlo
_FULL_DECK = []
for r in "23456789TJQKA":
    for s in "shdc":
        _FULL_DECK.append(Card.new(f"{r}{s}"))

def _full_deck() -> list[int]:
    """Return all 52 treys Card ints in a deterministic order."""
    return _FULL_DECK


def calculate_equity(
    hole_cards: list[int],
    board: list[int],
    villain_range: list[tuple[int, int]],
    num_simulations: int = 10_000,
    seed: int | None = None,
) -> float:
    """Calculate hero equity vs a villain range via Monte Carlo simulation.

    Args:
        hole_cards:      Hero's 2 hole cards (treys ints).
        board:           Community cards so far (0, 3, 4, or 5 treys ints).
        villain_range:   List of (card1, card2) villain hand combos.
        num_simulations: Number of Monte Carlo iterations (ignored on river).
        seed:            Optional RNG seed for reproducibility.

    Returns:
        Equity as a percentage (0.0 – 100.0).

    Raises:
        ValueError: If villain_range is empty.
    """
    if not villain_range:
        raise ValueError("Villain range is empty after removing dead cards")

    # Filter villain combos that collide with hero's hole cards or board
    dead = set(hole_cards) | set(board)
    valid_combos = [
        (c1, c2) for c1, c2 in villain_range
        if c1 not in dead and c2 not in dead
    ]

    if not valid_combos:
        raise ValueError("Villain range is empty after removing dead cards")

    # River: exhaustive enumeration (no randomness needed)
    if len(board) == 5:
        return _equity_river(hole_cards, board, valid_combos)

    # Flop / turn / preflop: Monte Carlo
    return _equity_monte_carlo(
        hole_cards, board, valid_combos, num_simulations, seed
    )


def _equity_river(
    hole_cards: list[int],
    board: list[int],
    villain_combos: list[tuple[int, int]],
) -> float:
    """Exact equity on the river — enumerate all villain hands."""
    wins = 0
    ties = 0
    total = 0

    hero_score = _evaluator.evaluate(board, hole_cards)

    for v1, v2 in villain_combos:
        villain_score = _evaluator.evaluate(board, [v1, v2])
        total += 1
        if hero_score < villain_score:      # lower = better in treys
            wins += 1
        elif hero_score == villain_score:
            ties += 1

    if total == 0:
        raise ValueError("No valid villain combos to evaluate")

    return (wins + ties * 0.5) / total * 100


def _equity_monte_carlo(
    hole_cards: list[int],
    board: list[int],
    villain_combos: list[tuple[int, int]],
    num_simulations: int,
    seed: int | None,
) -> float:
    """Monte Carlo equity for preflop / flop / turn."""
    rng = random.Random(seed)

    # Build the remaining deck (remove hero + board)
    dead = set(hole_cards) | set(board)
    full_deck = _full_deck()

    cards_to_deal = 5 - len(board)
    wins = 0
    ties = 0
    total = 0

    for _ in range(num_simulations):
        # Pick a random villain hand
        v1, v2 = rng.choice(villain_combos)

        # Villain cards must not collide with hero or board
        # (already pre-filtered, but still check for dealt community cards)
        villain_dead = dead | {v1, v2}

        # Remaining deck for community cards
        remaining = [c for c in full_deck if c not in villain_dead]

        if len(remaining) < cards_to_deal:
            continue  # shouldn't happen, but guard

        # Deal random community cards
        community = rng.sample(remaining, cards_to_deal)
        full_board = board + community

        # Evaluate
        hero_score = _evaluator.evaluate(full_board, hole_cards)
        villain_score = _evaluator.evaluate(full_board, [v1, v2])

        total += 1
        if hero_score < villain_score:
            wins += 1
        elif hero_score == villain_score:
            ties += 1

    if total == 0:
        raise ValueError("No valid simulations completed")

    return (wins + ties * 0.5) / total * 100
