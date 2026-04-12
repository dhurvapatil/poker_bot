"""Poker math engine — pot odds, SPR, MDF, outs, EV calculations."""

from __future__ import annotations

from dataclasses import dataclass

from treys import Card

from pokerbot.constants import RANKS, RANK_ORDER, SUITS


# ── Data class for computed metrics ───────────────────────────────────

@dataclass
class PokerMetrics:
    pot_odds_pct: float
    spr: float
    mdf: float
    outs: int            # -1 if preflop
    equity_pct: float
    ev_call: float


# ── Individual metric functions ───────────────────────────────────────

def calc_pot_odds(pot: float, bet_to_call: float) -> float:
    """Return pot odds as a percentage.

    pot_odds_pct = bet_to_call / (pot + bet_to_call) * 100
    If bet_to_call == 0 → 0.0 (free check).
    """
    if bet_to_call == 0:
        return 0.0
    return bet_to_call / (pot + bet_to_call) * 100


def calc_spr(my_stack: float, opp_stack: float, pot: float) -> float:
    """Return stack-to-pot ratio.

    spr = effective_stack / pot
    effective_stack = min(my_stack, opp_stack)
    """
    if pot == 0:
        return float("inf")
    effective_stack = min(my_stack, opp_stack)
    return effective_stack / pot


def calc_mdf(pot: float, bet_to_call: float) -> float:
    """Return minimum defence frequency as a percentage.

    mdf = pot / (pot + bet_to_call) * 100
    If bet_to_call == 0 → 100.0.
    """
    if bet_to_call == 0:
        return 100.0
    return pot / (pot + bet_to_call) * 100


def calc_ev_call(equity_pct: float, pot: float, bet_to_call: float) -> float:
    """Return expected value of calling.

    ev_call = equity_frac * (pot + bet_to_call) - (1 - equity_frac) * bet_to_call
    """
    eq = equity_pct / 100.0
    return eq * (pot + bet_to_call) - (1 - eq) * bet_to_call


# ── Outs estimation ──────────────────────────────────────────────────

def _get_rank(card: int) -> str:
    """Extract rank character from a treys Card int."""
    return Card.get_rank_int(card)


def _get_suit(card: int) -> int:
    """Extract suit int from a treys Card int."""
    return Card.get_suit_int(card)


def _rank_char(card: int) -> str:
    """Return rank as a character (A, K, Q, … 2) from a treys Card int."""
    rank_int = Card.get_rank_int(card)
    # treys: rank_int 0=2, 1=3, … 12=A
    int_to_char = "23456789TJQKA"
    return int_to_char[rank_int]


def _rank_value(card: int) -> int:
    """Return numeric rank value: 2=2, 3=3, … T=10, J=11, Q=12, K=13, A=14."""
    return Card.get_rank_int(card) + 2


def _has_flush_draw(hole: list[int], board: list[int]) -> bool:
    """Check if hero has a flush draw (exactly 4 cards to a flush)."""
    all_cards = hole + board
    suit_counts: dict[int, int] = {}
    for c in all_cards:
        s = _get_suit(c)
        suit_counts[s] = suit_counts.get(s, 0) + 1

    for s, count in suit_counts.items():
        if count == 4:
            # At least one hole card must contribute to the draw
            hole_in_suit = sum(1 for c in hole if _get_suit(c) == s)
            if hole_in_suit >= 1:
                return True
    return False


def _straight_draw_outs(hole: list[int], board: list[int]) -> int:
    """Return straight draw outs: 8 for OESD, 4 for gutshot, 0 otherwise.

    Uses all 5 cards (2 hole + 3 board on flop, or 2+4 on turn).
    Checks if any rank would complete a 5-card straight.
    Only counts draws where at least one hole card participates.
    """
    all_cards = hole + board
    rank_vals = sorted(set(_rank_value(c) for c in all_cards))
    hole_rank_vals = set(_rank_value(c) for c in hole)

    # Handle Ace-low: A can also be 1
    if 14 in rank_vals:
        rank_vals_extended = sorted(set(rank_vals + [1]))
    else:
        rank_vals_extended = rank_vals

    if 14 in hole_rank_vals:
        hole_rank_vals_extended = hole_rank_vals | {1}
    else:
        hole_rank_vals_extended = hole_rank_vals

    rank_set = set(rank_vals_extended)
    completing_ranks: set[int] = set()

    # For every possible 5-card straight window (low..low+4),
    # check if we have exactly 4 of the 5 and the missing rank is not on board
    for low in range(1, 11):  # straights: A-5 through T-A
        window = set(range(low, low + 5))
        have = window & rank_set
        missing = window - rank_set

        if len(have) == 4 and len(missing) == 1:
            miss = missing.pop()
            # At least one of our hole cards must be in this straight
            if hole_rank_vals_extended & have:
                completing_ranks.add(miss)

    if not completing_ranks:
        return 0

    # Each completing rank has 4 suits, minus any already on board/hand
    known_rank_vals = [_rank_value(c) for c in all_cards]
    total_outs = 0
    for r in completing_ranks:
        # 4 cards of this rank in the deck, minus any we already see
        used = known_rank_vals.count(r)
        total_outs += (4 - used)

    # Heuristic classification: if we found 2+ completing ranks → likely OESD (8),
    # if 1 completing rank → gutshot (4). But use actual card counts.
    return total_outs


def _overcard_outs(hole: list[int], board: list[int]) -> int:
    """Return outs from overcards (cards higher than any board card).

    Only counts if hero has no pair with the board.
    2 overcards = 6 outs, 1 overcard = 3 outs.
    """
    if not board:
        return 0

    board_ranks = [_rank_value(c) for c in board]
    hole_ranks = [_rank_value(c) for c in hole]
    max_board = max(board_ranks)

    # Check if either hole card pairs the board
    for hr in hole_ranks:
        if hr in board_ranks:
            return 0  # We have a pair, overcards don't apply

    overcards = [hr for hr in hole_ranks if hr > max_board]
    # Each overcard has 3 remaining copies (we have 1, none on board)
    return len(overcards) * 3


def _made_hand_improvement_outs(hole: list[int], board: list[int]) -> int:
    """Return outs for improving made hands (set→FH/quads, two pair→FH, pair→trips)."""
    all_cards = hole + board
    hole_ranks = [_rank_value(c) for c in hole]
    board_ranks = [_rank_value(c) for c in board]

    # Count rank occurrences across all cards
    rank_counts: dict[int, int] = {}
    for c in all_cards:
        r = _rank_value(c)
        rank_counts[r] = rank_counts.get(r, 0) + 1

    outs = 0

    # ── Set (3 of a kind using both/one hole card + board) ──
    # Set → full house or quads
    for hr in hole_ranks:
        if rank_counts.get(hr, 0) == 3:
            # We have a set — can improve to FH or quads
            # Quads: 1 out (remaining card of our set rank)
            remaining_set_cards = 4 - rank_counts[hr]
            outs += remaining_set_cards  # usually 1

            # Full house: any board card that pairs up
            for br in board_ranks:
                if br != hr:
                    remaining = 4 - rank_counts.get(br, 0)
                    outs += remaining
            return outs  # set is the dominant draw, return early

    # ── Two pair (both hole cards pair board cards) ──
    hole_paired_with_board = [hr for hr in hole_ranks if hr in board_ranks]
    if len(hole_paired_with_board) == 2:
        # Two pair → full house: either of our paired ranks trips up
        for hr in hole_paired_with_board:
            remaining = 4 - rank_counts.get(hr, 0)
            outs += remaining
        return outs

    # ── Single pair (one hole card pairs a board card) ──
    if len(hole_paired_with_board) == 1:
        hr = hole_paired_with_board[0]
        if rank_counts.get(hr, 0) == 2:
            # Pair → trips: 2 remaining cards of that rank
            remaining = 4 - rank_counts.get(hr, 0)
            outs += remaining

    # ── Pocket pair that didn't hit board ──
    if hole_ranks[0] == hole_ranks[1] and hole_ranks[0] not in board_ranks:
        # Pocket pair → set: 2 outs
        outs += 2

    return outs


def count_outs(hole_cards: list[int], board: list[int]) -> int:
    """Estimate the number of outs for improving the hand.

    Returns:
        -1 on preflop (not applicable)
         0 on river (no cards to come)
         Estimated outs on flop/turn
    """
    if len(board) == 0:
        return -1  # preflop
    if len(board) == 5:
        return 0   # river

    flush_outs = 9 if _has_flush_draw(hole_cards, board) else 0
    straight_outs = _straight_draw_outs(hole_cards, board)
    made_outs = _made_hand_improvement_outs(hole_cards, board)

    # Only count overcard outs when we have NO draw (flush or straight).
    # When draws are present, overcards are either already counted in
    # the draw outs (e.g. Ah in a heart flush draw) or the draw itself
    # is the primary equity source — adding overcards double-counts.
    if flush_outs == 0 and straight_outs == 0 and made_outs == 0:
        over_outs = _overcard_outs(hole_cards, board)
    else:
        over_outs = 0

    # Combine draws but reduce for overlap
    # If we have both flush and straight draws, some outs may overlap
    # (a card that completes both). Subtract estimated overlap.
    total = flush_outs + straight_outs + over_outs + made_outs

    if flush_outs > 0 and straight_outs > 0:
        # Roughly 1-2 cards complete both draws (suited connectors)
        overlap = min(2, straight_outs)
        total -= overlap

    # Cap at 21 (theoretical max for realistic draws)
    total = min(total, 21)

    return total


# ── Full metrics computation ─────────────────────────────────────────

def compute_metrics(
    hole_cards: list[int],
    board: list[int],
    pot: float,
    bet_to_call: float,
    my_stack: float,
    opp_stack: float,
    equity_pct: float,
    street: str,
) -> PokerMetrics:
    """Compute all poker math metrics for a given game state.

    equity_pct must be pre-computed (by equity.py) and passed in.
    """
    return PokerMetrics(
        pot_odds_pct=calc_pot_odds(pot, bet_to_call),
        spr=calc_spr(my_stack, opp_stack, pot),
        mdf=calc_mdf(pot, bet_to_call),
        outs=count_outs(hole_cards, board),
        equity_pct=equity_pct,
        ev_call=calc_ev_call(equity_pct, pot, bet_to_call),
    )
