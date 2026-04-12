"""Tests for pokerbot.input_parser — covers all 23 cases from plan §10.4."""

import pytest
from treys import Card

from pokerbot.input_parser import (
    parse_hole_cards,
    parse_board,
    validate_no_overlap,
    parse_street,
    validate_street_board,
    parse_position,
    parse_pot,
    parse_bet_to_call,
    parse_stack,
)


# ── Hole Cards ────────────────────────────────────────────────────────

class TestParseHoleCards:
    """Tests 1-8: hole card parsing & validation."""

    def test_parse_hole_cards_valid(self):
        """#1 — basic valid input."""
        result = parse_hole_cards("AhKd")
        assert len(result) == 2
        assert result[0] == Card.new("Ah")
        assert result[1] == Card.new("Kd")

    def test_parse_hole_cards_lowercase(self):
        """#2 — case insensitivity."""
        result = parse_hole_cards("ahkd")
        assert result == [Card.new("Ah"), Card.new("Kd")]

    def test_parse_hole_cards_with_space(self):
        """#3 — whitespace between cards."""
        result = parse_hole_cards("Ah Kd")
        assert result == [Card.new("Ah"), Card.new("Kd")]

    def test_parse_hole_cards_invalid_rank(self):
        """#4 — bad rank character."""
        with pytest.raises(ValueError, match="[Ii]nvalid rank"):
            parse_hole_cards("XhKd")

    def test_parse_hole_cards_invalid_suit(self):
        """#5 — bad suit character."""
        with pytest.raises(ValueError, match="[Ii]nvalid suit"):
            parse_hole_cards("AxKd")

    def test_parse_hole_cards_one_card(self):
        """#6 — too few cards."""
        with pytest.raises(ValueError, match="exactly 2"):
            parse_hole_cards("Ah")

    def test_parse_hole_cards_three_cards(self):
        """#7 — too many cards."""
        with pytest.raises(ValueError, match="exactly 2"):
            parse_hole_cards("AhKdQs")

    def test_parse_hole_cards_duplicate(self):
        """#8 — same card twice."""
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            parse_hole_cards("AhAh")


# ── Board ─────────────────────────────────────────────────────────────

class TestParseBoard:
    """Tests 9-14: board parsing & validation."""

    def test_parse_board_flop(self):
        """#9 — 3 cards (flop)."""
        result = parse_board("Ts9h2c")
        assert len(result) == 3
        assert result[0] == Card.new("Ts")
        assert result[1] == Card.new("9h")
        assert result[2] == Card.new("2c")

    def test_parse_board_turn(self):
        """#10 — 4 cards (turn)."""
        result = parse_board("Ts9h2c5d")
        assert len(result) == 4

    def test_parse_board_river(self):
        """#11 — 5 cards (river)."""
        result = parse_board("Ts9h2c5d8s")
        assert len(result) == 5

    def test_parse_board_empty(self):
        """#12 — empty string → preflop."""
        assert parse_board("") == []
        assert parse_board("   ") == []

    def test_parse_board_invalid_count(self):
        """#13 — 2 cards is invalid."""
        with pytest.raises(ValueError, match="0, 3, 4, or 5"):
            parse_board("Ts9h")

    def test_board_hole_overlap(self):
        """#14 — card in both hole and board."""
        hole = parse_hole_cards("AhKd")
        board = parse_board("Ah9h2c")
        with pytest.raises(ValueError, match="both"):
            validate_no_overlap(hole, board)


# ── Street ────────────────────────────────────────────────────────────

class TestParseStreet:
    """Tests 15-16, 19-20: street parsing & board consistency."""

    def test_parse_street_valid(self):
        """#15 — case insensitive variants."""
        assert parse_street("flop") == "flop"
        assert parse_street("FLOP") == "flop"
        assert parse_street("Flop") == "flop"
        assert parse_street("preflop") == "preflop"
        assert parse_street("turn") == "turn"
        assert parse_street("river") == "river"

    def test_parse_street_invalid(self):
        """#16 — typo."""
        with pytest.raises(ValueError, match="[Ii]nvalid street"):
            parse_street("flopp")

    def test_street_board_consistency_preflop(self):
        """#19 — preflop expects 0 board cards."""
        board = parse_board("Ts9h2c")  # 3 cards
        with pytest.raises(ValueError, match="expects 0"):
            validate_street_board("preflop", board)

    def test_street_board_consistency_flop(self):
        """#20 — flop expects 3 board cards, not 4."""
        board = parse_board("Ts9h2c5d")  # 4 cards
        with pytest.raises(ValueError, match="expects 3"):
            validate_street_board("flop", board)

    def test_street_board_consistency_turn_ok(self):
        """Extra — turn with 4 cards is fine."""
        board = parse_board("Ts9h2c5d")  # 4 cards
        validate_street_board("turn", board)  # should not raise

    def test_street_board_consistency_river_ok(self):
        """Extra — river with 5 cards is fine."""
        board = parse_board("Ts9h2c5d8s")  # 5 cards
        validate_street_board("river", board)  # should not raise


# ── Position ──────────────────────────────────────────────────────────

class TestParsePosition:
    """Tests 17-18: position parsing & validation."""

    def test_parse_position_valid(self):
        """#17 — case insensitive."""
        assert parse_position("BTN") == "BTN"
        assert parse_position("btn") == "BTN"
        assert parse_position("Bb") == "BB"
        assert parse_position("utg") == "UTG"
        assert parse_position("  CO  ") == "CO"

    def test_parse_position_invalid(self):
        """#18 — not in valid set."""
        with pytest.raises(ValueError, match="[Ii]nvalid position"):
            parse_position("BUTTON")


# ── Numeric Validations ──────────────────────────────────────────────

class TestNumericValidation:
    """Tests 21-23: pot, bet, stack guards."""

    def test_pot_positive_zero(self):
        """#21 — pot = 0 is invalid."""
        with pytest.raises(ValueError, match="[Pp]ot"):
            parse_pot(0)

    def test_pot_positive_negative(self):
        """#21 — pot = -5 is invalid."""
        with pytest.raises(ValueError, match="[Pp]ot"):
            parse_pot(-5)

    def test_pot_positive_ok(self):
        """#21 — pot = 100 is fine."""
        assert parse_pot(100) == 100.0

    def test_bet_non_negative(self):
        """#22 — bet = -1 is invalid."""
        with pytest.raises(ValueError, match="[Bb]et"):
            parse_bet_to_call(-1)

    def test_bet_zero_ok(self):
        """#22 — bet = 0 is valid (check option)."""
        assert parse_bet_to_call(0) == 0.0

    def test_stack_positive_zero(self):
        """#23 — stack = 0 is invalid."""
        with pytest.raises(ValueError, match="must be > 0"):
            parse_stack(0, "My stack")

    def test_stack_positive_negative(self):
        """#23 — stack = -100 is invalid."""
        with pytest.raises(ValueError, match="must be > 0"):
            parse_stack(-100, "Opponent stack")

    def test_stack_positive_ok(self):
        """#23 — stack = 500 is fine."""
        assert parse_stack(500) == 500.0
