"""Constants for poker card representation and game rules."""

# ── Ranks (high to low) ──────────────────────────────────────────────
RANKS = "AKQJT98765432"
RANK_ORDER = {r: i for i, r in enumerate(RANKS)}  # A=0 (highest) … 2=12

# ── Suits ─────────────────────────────────────────────────────────────
SUITS = "shdc"  # spades, hearts, diamonds, clubs

# ── All 52 card strings ──────────────────────────────────────────────
ALL_CARDS = [f"{r}{s}" for r in RANKS for s in SUITS]

# ── Valid positions ───────────────────────────────────────────────────
POSITIONS = {"UTG", "UTG1", "UTG2", "MP", "MP1", "MP2", "HJ", "CO", "BTN", "SB", "BB"}

# ── Valid streets ─────────────────────────────────────────────────────
STREETS = {"preflop", "flop", "turn", "river"}

# ── Street → expected board card count ────────────────────────────────
STREET_BOARD_COUNT = {
    "preflop": 0,
    "flop": 3,
    "turn": 4,
    "river": 5,
}

# ── Valid board card counts (for when street is derived, not supplied) ─
VALID_BOARD_COUNTS = {0, 3, 4, 5}
