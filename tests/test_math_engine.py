"""Tests for pokerbot.math_engine — covers all 22 cases from plan §10.2."""

import pytest
from treys import Card

from pokerbot.math_engine import (
    calc_pot_odds,
    calc_spr,
    calc_mdf,
    calc_ev_call,
    count_outs,
    compute_metrics,
)


# ── Pot Odds ──────────────────────────────────────────────────────────

class TestPotOdds:
    """Tests 1-4."""

    def test_pot_odds_basic(self):
        """#1 — pot=120, bet=40 → 25.0%."""
        assert calc_pot_odds(120, 40) == pytest.approx(25.0)

    def test_pot_odds_zero_bet(self):
        """#2 — free check → 0.0%."""
        assert calc_pot_odds(100, 0) == 0.0

    def test_pot_odds_large_bet(self):
        """#3 — pot-sized bet → 50.0%."""
        assert calc_pot_odds(100, 100) == pytest.approx(50.0)

    def test_pot_odds_small_bet(self):
        """#4 — small bet into big pot → ~4.76%."""
        assert calc_pot_odds(200, 10) == pytest.approx(10 / 210 * 100, abs=0.01)


# ── SPR ───────────────────────────────────────────────────────────────

class TestSPR:
    """Tests 5-7."""

    def test_spr_basic(self):
        """#5 — effective stack is min(500, 480) = 480, pot=120 → 4.0."""
        assert calc_spr(500, 480, 120) == pytest.approx(4.0)

    def test_spr_short_stack(self):
        """#6 — I'm short: min(50, 1000) = 50, pot=100 → 0.5."""
        assert calc_spr(50, 1000, 100) == pytest.approx(0.5)

    def test_spr_equal_stacks(self):
        """#7 — equal stacks: min(300, 300) = 300, pot=100 → 3.0."""
        assert calc_spr(300, 300, 100) == pytest.approx(3.0)

    def test_spr_zero_pot(self):
        """Extra — pot=0 guard → inf."""
        assert calc_spr(500, 500, 0) == float("inf")


# ── MDF ───────────────────────────────────────────────────────────────

class TestMDF:
    """Tests 8-10."""

    def test_mdf_basic(self):
        """#8 — pot=120, bet=40 → 75.0%."""
        assert calc_mdf(120, 40) == pytest.approx(75.0)

    def test_mdf_zero_bet(self):
        """#9 — check → 100.0%."""
        assert calc_mdf(100, 0) == 100.0

    def test_mdf_overbet(self):
        """#10 — pot=100, bet=200 → ~33.3%."""
        assert calc_mdf(100, 200) == pytest.approx(100 / 300 * 100, abs=0.1)


# ── EV of Calling ────────────────────────────────────────────────────

class TestEVCall:
    """Tests 11-14."""

    def test_ev_call_positive(self):
        """#11 — equity=55%, pot=120, bet=40 → +70.0."""
        result = calc_ev_call(55, 120, 40)
        assert result == pytest.approx(70.0)

    def test_ev_call_breakeven(self):
        """#12 — equity=20%, pot=120, bet=40 → 0.0 (breakeven)."""
        result = calc_ev_call(20, 120, 40)
        # 0.2 * 160 - 0.8 * 40 = 32 - 32 = 0
        assert result == pytest.approx(0.0)

    def test_ev_call_zero_bet(self):
        """#13 — equity=50%, pot=100, bet=0 → +50.0."""
        result = calc_ev_call(50, 100, 0)
        # 0.5 * 100 - 0.5 * 0 = 50
        assert result == pytest.approx(50.0)

    def test_ev_call_dominated(self):
        """#14 — equity=10%, pot=100, bet=50 → -30.0."""
        result = calc_ev_call(10, 100, 50)
        # 0.1 * 150 - 0.9 * 50 = 15 - 45 = -30
        assert result == pytest.approx(-30.0)


# ── Outs ──────────────────────────────────────────────────────────────

class TestOuts:
    """Tests 15-22."""

    def test_outs_flush_draw(self):
        """#15 — Ah5h on Kh9h2c → 9 flush outs.

        Pure flush draw. Overcards are NOT added separately since
        hitting the Ah is already included in the 9 flush outs.
        """
        hole = [Card.new("Ah"), Card.new("5h")]
        board = [Card.new("Kh"), Card.new("9h"), Card.new("2c")]
        outs = count_outs(hole, board)
        assert outs == 9

    def test_outs_oesd(self):
        """#16 — 8h7h on 6c5dKs → 8 straight outs (OESD, no flush draw)."""
        hole = [Card.new("8h"), Card.new("7h")]
        board = [Card.new("6c"), Card.new("5d"), Card.new("Ks")]
        outs = count_outs(hole, board)
        # OESD: need 4 or 9 to complete. 4 fours + 4 nines = 8
        assert outs == 8

    def test_outs_gutshot(self):
        """#17 — AhTd on Kc9h5s.

        Ranks: A(14), K(13), T(10), 9, 5.
        No 4-of-5 straight window exists → no straight draw.
        A is the only overcard (A > K). T < K. → 3 overcard outs.
        """
        hole = [Card.new("Ah"), Card.new("Td")]
        board = [Card.new("Kc"), Card.new("9h"), Card.new("5s")]
        outs = count_outs(hole, board)
        assert outs == 3  # one overcard (Ace)

    def test_outs_gutshot_real(self):
        """Extra — actual gutshot: JhTd on Kc8h5s.

        Ranks: K(13), J(11), T(10), 8, 5.
        Window KQJ T(missing Q) or JT98(missing 9) → 
        JT98: have J,T,8 need 9 = gutshot. But K is in the way.
        Actually: window 8-9-T-J-Q: have 8,T,J → need 9 and Q (2 gaps, no).
        Window 9-T-J-Q-K: have T,J,K → need 9 and Q (2 gaps, no).
        Window T-J-Q-K-A: have T,J,K → need Q and A (2 gaps, no).
        
        Better example: 9d8h on Kc7s2d.
        Ranks: K(13), 9, 8, 7, 2.
        Window 6-7-8-9-T: have 7,8,9 need 6 and T (2 gaps, no).
        Window 5-6-7-8-9: have 7,8,9 need 5 and 6 (2 gaps, no).
        
        True gutshot: Td9d on 7c6s2h.
        Ranks: T(10), 9, 7, 6, 2.
        Window 6-7-8-9-T: have 6,7,9,T need 8 → GUTSHOT! 4 eights.
        """
        hole = [Card.new("Td"), Card.new("9d")]
        board = [Card.new("7c"), Card.new("6s"), Card.new("2h")]
        outs = count_outs(hole, board)
        # OESD: window 6-7-8-9-T needs 8 (4 outs) and
        # window 7-8-9-T-J needs 8 and J (2 gaps, no).
        # Actually 6-7-8-9-T: have 6,7,9,T need 8 = gutshot.
        # Also 8-9-T-J-Q: have 9,T need 8,J,Q (3 gaps, no).
        # And 5-6-7-8-9: have 6,7,9 need 5,8 (2 gaps, no).
        # So just 1 completing rank (8) × 4 suits = 4 outs.
        assert outs == 4

    def test_outs_two_overcards(self):
        """#18 — AhKd on 9h7c2s → 6 overcard outs."""
        hole = [Card.new("Ah"), Card.new("Kd")]
        board = [Card.new("9h"), Card.new("7c"), Card.new("2s")]
        outs = count_outs(hole, board)
        assert outs == 6

    def test_outs_preflop(self):
        """#19 — preflop → -1 (not applicable)."""
        hole = [Card.new("Ah"), Card.new("Kd")]
        outs = count_outs(hole, [])
        assert outs == -1

    def test_outs_river(self):
        """#20 — river → 0 (no cards to come)."""
        hole = [Card.new("Ah"), Card.new("Kd")]
        board = [Card.new("9h"), Card.new("7c"), Card.new("2s"),
                 Card.new("4d"), Card.new("Ts")]
        outs = count_outs(hole, board)
        assert outs == 0

    def test_outs_made_hand_set(self):
        """#21 — AhAd on As7c2d → set improvement outs.

        Set of aces. Improving to:
        - Quads: 1 remaining Ace = 1 out
        - Full house: board pairs (remaining 7s = 3, remaining 2s = 3) = 6 outs
        Total = 7 outs.
        """
        hole = [Card.new("Ah"), Card.new("Ad")]
        board = [Card.new("As"), Card.new("7c"), Card.new("2d")]
        outs = count_outs(hole, board)
        assert outs == 7

    def test_outs_combo_draw(self):
        """#22 — JhTh on 9h8h2c → flush draw + OESD combo draw.

        Flush draw: 9 outs
        OESD (need 7 or Q): 4+4 = 8 outs
        Overlap: 2 cards (7h and Qh complete both) → subtract 2
        Expected: 9 + 8 - 2 = 15 outs
        """
        hole = [Card.new("Jh"), Card.new("Th")]
        board = [Card.new("9h"), Card.new("8h"), Card.new("2c")]
        outs = count_outs(hole, board)
        assert 14 <= outs <= 16  # ~15 with overlap subtraction


# ── compute_metrics integration ───────────────────────────────────────

class TestComputeMetrics:
    """Smoke test for the combined metrics function."""

    def test_compute_metrics_flop(self):
        """All metrics computed together on a flop spot."""
        hole = [Card.new("Ah"), Card.new("Kd")]
        board = [Card.new("9h"), Card.new("7c"), Card.new("2s")]

        m = compute_metrics(
            hole_cards=hole,
            board=board,
            pot=120,
            bet_to_call=40,
            my_stack=500,
            opp_stack=480,
            equity_pct=38.2,
            street="flop",
        )

        assert m.pot_odds_pct == pytest.approx(25.0)
        assert m.spr == pytest.approx(4.0)
        assert m.mdf == pytest.approx(75.0)
        assert m.outs == 6  # two overcards
        assert m.equity_pct == pytest.approx(38.2)
        # ev_call = 0.382 * 160 - 0.618 * 40 = 61.12 - 24.72 = 36.4
        assert m.ev_call == pytest.approx(36.4)

    def test_compute_metrics_preflop(self):
        """Preflop: outs should be -1."""
        hole = [Card.new("Ah"), Card.new("Kd")]
        m = compute_metrics(
            hole_cards=hole,
            board=[],
            pot=30,
            bet_to_call=20,
            my_stack=1000,
            opp_stack=1000,
            equity_pct=55.0,
            street="preflop",
        )
        assert m.outs == -1
        assert m.pot_odds_pct == pytest.approx(40.0)

    def test_compute_metrics_river(self):
        """River: outs should be 0."""
        hole = [Card.new("Ah"), Card.new("Kd")]
        board = [Card.new("9h"), Card.new("7c"), Card.new("2s"),
                 Card.new("4d"), Card.new("Ts")]
        m = compute_metrics(
            hole_cards=hole,
            board=board,
            pot=200,
            bet_to_call=100,
            my_stack=400,
            opp_stack=600,
            equity_pct=30.0,
            street="river",
        )
        assert m.outs == 0
