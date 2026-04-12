"""Parse and validate all poker game-state inputs."""

from __future__ import annotations

import re
from treys import Card

from pokerbot.constants import (
    RANKS,
    SUITS,
    POSITIONS,
    STREETS,
    STREET_BOARD_COUNT,
    VALID_BOARD_COUNTS,
)

# ── Regex to extract individual card tokens (rank + suit) ─────────────
_CARD_RE = re.compile(r"[2-9TJQKA][shdc]", re.IGNORECASE)


# ── Card helpers ──────────────────────────────────────────────────────
def _normalise_card(card_str: str) -> str:
    """Normalise a 2-char card string: rank uppercase, suit lowercase.

    e.g.  'ah' → 'Ah',  'tS' → 'Ts'
    """
    if len(card_str) != 2:
        raise ValueError(f"Invalid card string (must be 2 chars): '{card_str}'")
    rank = card_str[0].upper()
    suit = card_str[1].lower()
    if rank not in RANKS:
        raise ValueError(f"Invalid rank '{card_str[0]}' in card '{card_str}'")
    if suit not in SUITS:
        raise ValueError(f"Invalid suit '{card_str[1]}' in card '{card_str}'")
    return f"{rank}{suit}"


def _tokenise_cards(text: str) -> list[str]:
    """Extract card tokens from a string like 'AhKd' or 'Ah Kd' or 'Ts9h2c'.

    Returns list of normalised 2-char card strings.
    """
    raw = _CARD_RE.findall(text)
    return [_normalise_card(c) for c in raw]


def _check_duplicates(cards: list[str], label: str = "cards") -> None:
    """Raise ValueError if any card string appears more than once."""
    seen: set[str] = set()
    for c in cards:
        if c in seen:
            raise ValueError(f"Duplicate card '{c}' in {label}")
        seen.add(c)


# ── Public parsers ────────────────────────────────────────────────────

def parse_hole_cards(text: str) -> list[int]:
    """Parse a hole-cards string into a list of 2 treys Card ints.

    Accepts formats like 'AhKd', 'Ah Kd', 'ah kd'.
    Raises ValueError on bad input.
    """
    # Strip and validate characters first
    stripped = text.strip()
    if not stripped:
        raise ValueError("Hole cards string is empty")

    # Check for invalid characters before tokenising
    cleaned = re.sub(r"\s+", "", stripped)
    for i in range(0, len(cleaned), 2):
        chunk = cleaned[i : i + 2]
        if len(chunk) == 2:
            rank, suit = chunk[0].upper(), chunk[1].lower()
            if rank not in RANKS:
                raise ValueError(f"Invalid rank '{chunk[0]}' in card '{chunk}'")
            if suit not in SUITS:
                raise ValueError(f"Invalid suit '{chunk[1]}' in card '{chunk}'")

    tokens = _tokenise_cards(stripped)

    if len(tokens) < 2:
        raise ValueError(
            f"Hole cards must be exactly 2 cards, got {len(tokens)}: '{text}'"
        )
    if len(tokens) > 2:
        raise ValueError(
            f"Hole cards must be exactly 2 cards, got {len(tokens)}: '{text}'"
        )

    _check_duplicates(tokens, "hole cards")
    return [Card.new(c) for c in tokens]


def parse_board(text: str) -> list[int]:
    """Parse a board string into a list of 0/3/4/5 treys Card ints.

    Empty string → [] (preflop).
    Raises ValueError for invalid counts (1, 2, 6+).
    """
    stripped = text.strip()
    if not stripped:
        return []

    tokens = _tokenise_cards(stripped)

    if len(tokens) not in VALID_BOARD_COUNTS:
        raise ValueError(
            f"Board must have 0, 3, 4, or 5 cards, got {len(tokens)}: '{text}'"
        )

    _check_duplicates(tokens, "board")
    return [Card.new(c) for c in tokens]


def validate_no_overlap(hole_cards: list[int], board: list[int]) -> None:
    """Raise ValueError if any card appears in both hole and board."""
    overlap = set(hole_cards) & set(board)
    if overlap:
        # Pretty-print the overlapping cards
        overlapping = [Card.int_to_str(c) for c in overlap]
        raise ValueError(
            f"Card(s) appear in both hole cards and board: {overlapping}"
        )


def parse_street(text: str) -> str:
    """Normalise and validate street string.

    Returns lowercase: 'preflop', 'flop', 'turn', 'river'.
    """
    val = text.strip().lower()
    if val not in STREETS:
        raise ValueError(
            f"Invalid street '{text}'. Must be one of: {sorted(STREETS)}"
        )
    return val


def validate_street_board(street: str, board: list[int]) -> None:
    """Ensure the street is consistent with the number of board cards."""
    expected = STREET_BOARD_COUNT[street]
    actual = len(board)
    if actual != expected:
        raise ValueError(
            f"Street '{street}' expects {expected} board card(s), got {actual}"
        )


def parse_position(text: str) -> str:
    """Normalise and validate position string. Returns uppercase."""
    val = text.strip().upper()
    if val not in POSITIONS:
        raise ValueError(
            f"Invalid position '{text}'. Must be one of: {sorted(POSITIONS)}"
        )
    return val


def parse_pot(value: float) -> float:
    """Validate pot size. Must be > 0."""
    if value <= 0:
        raise ValueError(f"Pot must be > 0, got {value}")
    return float(value)


def parse_bet_to_call(value: float) -> float:
    """Validate bet to call. Must be >= 0."""
    if value < 0:
        raise ValueError(f"Bet to call must be >= 0, got {value}")
    return float(value)


def parse_stack(value: float, label: str = "Stack") -> float:
    """Validate a stack size. Must be > 0."""
    if value <= 0:
        raise ValueError(f"{label} must be > 0, got {value}")
    return float(value)


def derive_street(board: list[int]) -> str:
    """Derive street name from board card count."""
    count = len(board)
    for street, expected in STREET_BOARD_COUNT.items():
        if expected == count:
            return street
    raise ValueError(f"Cannot derive street from {count} board cards")


# ── Convenience: parse everything at once ─────────────────────────────

def parse_game_state(
    hole_cards_str: str,
    board_str: str,
    pot: float,
    bet_to_call: float,
    my_stack: float,
    opp_stack: float,
    position_str: str,
    street_str: str,
    villain_range_str: str,
) -> dict:
    """Parse and validate every input field. Returns a dict of parsed values.

    Raises ValueError with a descriptive message on any bad input.
    """
    hole = parse_hole_cards(hole_cards_str)
    board = parse_board(board_str)
    validate_no_overlap(hole, board)

    street = parse_street(street_str)
    validate_street_board(street, board)

    position = parse_position(position_str)
    pot_val = parse_pot(pot)
    bet_val = parse_bet_to_call(bet_to_call)
    my_stack_val = parse_stack(my_stack, "My stack")
    opp_stack_val = parse_stack(opp_stack, "Opponent stack")

    # villain_range is validated later by range_parser; just ensure non-empty
    vr = villain_range_str.strip()
    if not vr:
        raise ValueError("Villain range must not be empty")

    return {
        "hole_cards": hole,
        "board": board,
        "pot": pot_val,
        "bet_to_call": bet_val,
        "my_stack": my_stack_val,
        "opp_stack": opp_stack_val,
        "position": position,
        "street": street,
        "villain_range": vr,
    }
