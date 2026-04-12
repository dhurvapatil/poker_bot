"""Tests for pokerbot.equity — covers all 10 cases from plan §10.3."""

import pytest
from treys import Card

from pokerbot.equity import calculate_equity
from pokerbot.range_parser import parse_range


# Helpers to build card lists quickly
def _h(s: str) -> list[int]:
    """Parse a string like 'AhKd' into a list of treys Card ints."""
    cards = []
    for i in range(0, len(s), 2):
        cards.append(Card.new(s[i:i+2]))
    return cards


# High sim count + fixed seed for stable results
SIM = 50_000
SEED = 42


class TestEquityPremiums:
    """Tests 1, 3: premium vs premium matchups."""

    def test_equity_aa_vs_kk_preflop(self):
        """#1 — AA vs KK preflop ≈ 81%."""
        hole = _h("AhAd")
        board = []
        villain = parse_range("KK", dead_cards=hole)
        eq = calculate_equity(hole, board, villain, num_simulations=SIM, seed=SEED)
        assert 76 <= eq <= 86, f"AA vs KK equity {eq:.1f}% out of range"

    def test_equity_set_vs_overpair(self):
        """#3 — Set of 9s vs QQ on Ts9h2c ≈ 85-95%.

        Plan used TT here, but Ts is on the board so TT makes a *set of Tens*
        (set-over-set), not an overpair. Using QQ instead — a true overpair.
        """
        hole = _h("9s9d")
        board = _h("Ts9h2c")
        villain = parse_range("QQ", dead_cards=hole + board)
        eq = calculate_equity(hole, board, villain, num_simulations=SIM, seed=SEED)
        assert 80 <= eq <= 97, f"Set vs overpair equity {eq:.1f}% out of range"


class TestEquityDraws:
    """Tests 2, 4: drawing hands."""

    def test_equity_ak_vs_pairs_flop(self):
        """#2 — AhKd vs TT+ on Ts9h2c ≈ 15-25% (behind on flop)."""
        hole = _h("AhKd")
        board = _h("Ts9h2c")
        villain = parse_range("TT+", dead_cards=hole + board)
        eq = calculate_equity(hole, board, villain, num_simulations=SIM, seed=SEED)
        assert 10 <= eq <= 30, f"AK vs TT+ on paired flop {eq:.1f}% out of range"

    def test_equity_flush_draw(self):
        """#4 — Ah5h vs KK on Kh9h2c ≈ 35%."""
        hole = _h("Ah5h")
        board = _h("Kh9h2c")
        villain = parse_range("KK", dead_cards=hole + board)
        eq = calculate_equity(hole, board, villain, num_simulations=SIM, seed=SEED)
        assert 25 <= eq <= 45, f"Flush draw vs set {eq:.1f}% out of range"


class TestEquityRiver:
    """Tests 5, 6: river — deterministic, no Monte Carlo."""

    def test_equity_river_winner(self):
        """#5 — AhKd vs QQ on AsTd5c3h2s → 100% (top pair beats underpair)."""
        hole = _h("AhKd")
        board = _h("AsTd5c3h2s")
        villain = parse_range("QQ", dead_cards=hole + board)
        eq = calculate_equity(hole, board, villain)
        assert eq == pytest.approx(100.0)

    def test_equity_river_loser(self):
        """#6 — 7h6d vs AA on AsTd5c3h2s → 0% (pair of aces beats nothing)."""
        hole = _h("7h6d")
        board = _h("AsTd5c3h2s")
        villain = parse_range("AA", dead_cards=hole + board)
        eq = calculate_equity(hole, board, villain)
        assert eq == pytest.approx(0.0)


class TestEquityPreflop:
    """Tests 7, 8: preflop scenarios."""

    def test_equity_coinflip(self):
        """#7 — AhKd vs QQ preflop ≈ 43% (classic coinflip)."""
        hole = _h("AhKd")
        board = []
        villain = parse_range("QQ", dead_cards=hole)
        eq = calculate_equity(hole, board, villain, num_simulations=SIM, seed=SEED)
        assert 38 <= eq <= 50, f"AKo vs QQ coinflip {eq:.1f}% out of range"

    def test_equity_wide_range(self):
        """#8 — AhKd vs '22+, AT+, KT+' preflop ≈ 55-65%."""
        hole = _h("AhKd")
        board = []
        villain = parse_range("22+, AT+, KT+", dead_cards=hole)
        eq = calculate_equity(hole, board, villain, num_simulations=SIM, seed=SEED)
        assert 50 <= eq <= 70, f"AKo vs wide range {eq:.1f}% out of range"


class TestEquityEdgeCases:
    """Tests 9, 10: error handling and determinism."""

    def test_equity_empty_range(self):
        """#9 — empty villain range → ValueError."""
        hole = _h("AhKd")
        with pytest.raises(ValueError, match="empty"):
            calculate_equity(hole, [], [])

    def test_equity_deterministic_seed(self):
        """#10 — same seed produces same result within ±1%."""
        hole = _h("AhKd")
        villain = parse_range("QQ", dead_cards=hole)

        eq1 = calculate_equity(hole, [], villain, num_simulations=SIM, seed=99)
        eq2 = calculate_equity(hole, [], villain, num_simulations=SIM, seed=99)
        assert eq1 == pytest.approx(eq2, abs=0.01)

    def test_equity_different_seeds_vary(self):
        """Extra — different seeds can give slightly different results."""
        hole = _h("AhKd")
        villain = parse_range("QQ", dead_cards=hole)

        eq1 = calculate_equity(hole, [], villain, num_simulations=5_000, seed=1)
        eq2 = calculate_equity(hole, [], villain, num_simulations=5_000, seed=2)
        # Both should be in the right ballpark but may differ slightly
        assert 35 <= eq1 <= 55
        assert 35 <= eq2 <= 55


class TestEquityAdditional:
    """Extra tests for correctness."""

    def test_equity_river_tie(self):
        """Board plays — both have same kicker, should tie often."""
        # Board: AKQJT (broadway straight on board)
        hole = _h("2h3d")
        board = _h("AhKdQcJsTs")
        villain = parse_range("22", dead_cards=hole + board)
        eq = calculate_equity(hole, board, villain)
        # Both play the board straight → 100% tie → 50% equity
        assert eq == pytest.approx(50.0)

    def test_equity_turn(self):
        """Turn scenario (4 board cards) works correctly."""
        hole = _h("AhKh")
        board = _h("Qh9h2c4d")  # nut flush draw on turn
        villain = parse_range("QQ", dead_cards=hole + board)
        eq = calculate_equity(hole, board, villain, num_simulations=SIM, seed=SEED)
        # One card to come, ~9 flush outs + overcard outs ≈ 25-40%
        assert 15 <= eq <= 45, f"Turn flush draw equity {eq:.1f}% out of range"

    def test_equity_dominated_preflop(self):
        """AKo vs AA preflop ≈ 7% (heavily dominated)."""
        hole = _h("AhKd")
        villain = parse_range("AA", dead_cards=hole)
        eq = calculate_equity(hole, [], villain, num_simulations=SIM, seed=SEED)
        assert 2 <= eq <= 15, f"AK vs AA equity {eq:.1f}% out of range"
