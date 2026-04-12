"""Parse poker hand range strings into concrete (card1, card2) combos.

Supported syntax examples:
    AA, QQ+, 88-55, AKs, AKo, AK, ATs+, ATo+, AT+, KTs-K8s
"""

from __future__ import annotations

import re
from itertools import combinations
from treys import Card

from pokerbot.constants import RANKS, RANK_ORDER, SUITS


# ── Helpers ───────────────────────────────────────────────────────────

def _rank_index(r: str) -> int:
    """Return rank index (A=0, K=1, … 2=12). Raises ValueError for bad rank."""
    r = r.upper()
    if r not in RANK_ORDER:
        raise ValueError(f"Invalid rank: '{r}'")
    return RANK_ORDER[r]


def _ranks_between(high: str, low: str) -> list[str]:
    """Return ranks from *low* up to *high* inclusive (ascending by strength).

    e.g. _ranks_between('T', '7') → ['7', '8', '9', 'T']
    """
    hi = _rank_index(high)
    lo = _rank_index(low)
    if hi > lo:
        hi, lo = lo, hi  # swap so hi_idx < lo_idx (stronger is lower index)
    return [RANKS[i] for i in range(lo, hi - 1, -1)]


def _pair_combos(rank: str) -> set[tuple[int, int]]:
    """All 6 combos of a pocket pair for a given rank."""
    cards = [Card.new(f"{rank}{s}") for s in SUITS]
    return {(a, b) for a, b in combinations(cards, 2)}


def _suited_combos(rank1: str, rank2: str) -> set[tuple[int, int]]:
    """4 suited combos for two distinct ranks."""
    combos: set[tuple[int, int]] = set()
    for s in SUITS:
        c1 = Card.new(f"{rank1}{s}")
        c2 = Card.new(f"{rank2}{s}")
        combos.add((c1, c2))
    return combos


def _offsuit_combos(rank1: str, rank2: str) -> set[tuple[int, int]]:
    """12 offsuit combos for two distinct ranks."""
    combos: set[tuple[int, int]] = set()
    for s1 in SUITS:
        for s2 in SUITS:
            if s1 == s2:
                continue
            c1 = Card.new(f"{rank1}{s1}")
            c2 = Card.new(f"{rank2}{s2}")
            combos.add((c1, c2))
    return combos


def _all_combos(rank1: str, rank2: str) -> set[tuple[int, int]]:
    """All 16 combos (4 suited + 12 offsuit) for two distinct ranks."""
    return _suited_combos(rank1, rank2) | _offsuit_combos(rank1, rank2)


# ── Regex patterns for token detection ────────────────────────────────

# Order matters — more specific patterns first.
#   group names:  r1/r2 = ranks, suf = suffix (s/o), plus = '+', lo = dash-range low
_PATTERNS = [
    # Pair dash-range:  88-55
    re.compile(
        r"^(?P<r1>[2-9TJQKA])(?P=r1)-(?P<r2>[2-9TJQKA])(?P=r2)$",
        re.IGNORECASE,
    ),
    # Pair+:  QQ+
    re.compile(
        r"^(?P<r1>[2-9TJQKA])(?P=r1)(?P<plus>\+)$",
        re.IGNORECASE,
    ),
    # Pair exact:  AA
    re.compile(
        r"^(?P<r1>[2-9TJQKA])(?P=r1)$",
        re.IGNORECASE,
    ),
    # Non-pair dash-range (suited/offsuit):  KTs-K8s  or  KTo-K8o
    re.compile(
        r"^(?P<r1>[2-9TJQKA])(?P<r2>[2-9TJQKA])(?P<suf>[so])-"
        r"(?P<r3>[2-9TJQKA])(?P<r4>[2-9TJQKA])(?P<suf2>[so])$",
        re.IGNORECASE,
    ),
    # Non-pair+:  ATs+  ATo+  AT+
    re.compile(
        r"^(?P<r1>[2-9TJQKA])(?P<r2>[2-9TJQKA])(?P<suf>[so])?(?P<plus>\+)$",
        re.IGNORECASE,
    ),
    # Non-pair exact:  AKs  AKo  AK
    re.compile(
        r"^(?P<r1>[2-9TJQKA])(?P<r2>[2-9TJQKA])(?P<suf>[so])?$",
        re.IGNORECASE,
    ),
]


def _expand_token(token: str) -> set[tuple[int, int]]:
    """Expand a single range token into a set of (card1, card2) combos."""
    token = token.strip()
    if not token:
        raise ValueError("Empty range token")

    for i, pat in enumerate(_PATTERNS):
        m = pat.match(token)
        if not m:
            continue

        if i == 0:
            # ── Pair dash-range: 88-55 ──
            r1 = m.group("r1").upper()
            r2 = m.group("r2").upper()
            ranks = _ranks_between(r1, r2)
            combos: set[tuple[int, int]] = set()
            for r in ranks:
                combos |= _pair_combos(r)
            return combos

        if i == 1:
            # ── Pair+: QQ+ ──
            r1 = m.group("r1").upper()
            idx = _rank_index(r1)
            combos = set()
            # From this rank up to Aces (index 0)
            for ri in range(idx, -1, -1):
                combos |= _pair_combos(RANKS[ri])
            return combos

        if i == 2:
            # ── Pair exact: AA ──
            r1 = m.group("r1").upper()
            return _pair_combos(r1)

        if i == 3:
            # ── Non-pair dash-range: KTs-K8s ──
            r1 = m.group("r1").upper()
            r2 = m.group("r2").upper()
            r3 = m.group("r3").upper()
            r4 = m.group("r4").upper()
            suf = m.group("suf").lower()
            suf2 = m.group("suf2").lower()

            if r1 != r3:
                raise ValueError(
                    f"Dash range high cards must match: '{token}'"
                )
            if suf != suf2:
                raise ValueError(
                    f"Dash range suffixes must match: '{token}'"
                )

            # The kicker ranks to iterate
            kicker_ranks = _ranks_between(r2, r4)
            combos = set()
            for kr in kicker_ranks:
                if suf == "s":
                    combos |= _suited_combos(r1, kr)
                else:
                    combos |= _offsuit_combos(r1, kr)
            return combos

        if i == 4:
            # ── Non-pair+: ATs+ / ATo+ / AT+ ──
            r1 = m.group("r1").upper()
            r2 = m.group("r2").upper()
            suf_raw = m.group("suf")
            suf = suf_raw.lower() if suf_raw else None

            # Ensure r1 is the higher rank
            if _rank_index(r1) > _rank_index(r2):
                r1, r2 = r2, r1

            # Iterate kicker from r2 up to one below r1
            r1_idx = _rank_index(r1)
            r2_idx = _rank_index(r2)

            combos = set()
            for ki in range(r2_idx, r1_idx, -1):
                kr = RANKS[ki]
                if suf == "s":
                    combos |= _suited_combos(r1, kr)
                elif suf == "o":
                    combos |= _offsuit_combos(r1, kr)
                else:
                    combos |= _all_combos(r1, kr)
            return combos

        if i == 5:
            # ── Non-pair exact: AKs / AKo / AK ──
            r1 = m.group("r1").upper()
            r2 = m.group("r2").upper()
            suf_raw = m.group("suf")
            suf = suf_raw.lower() if suf_raw else None

            if r1 == r2:
                # Actually a pair — shouldn't reach here due to pattern order,
                # but guard anyway.
                return _pair_combos(r1)

            if suf == "s":
                return _suited_combos(r1, r2)
            elif suf == "o":
                return _offsuit_combos(r1, r2)
            else:
                return _all_combos(r1, r2)

    raise ValueError(f"Unrecognised range token: '{token}'")


# ── Public API ────────────────────────────────────────────────────────

def parse_range(
    range_str: str,
    dead_cards: list[int] | None = None,
) -> list[tuple[int, int]]:
    """Parse a poker range string into concrete hand combos.

    Args:
        range_str:  Comma-separated range, e.g. "TT+, AKs, AQo"
        dead_cards: treys Card ints that are already on board / in hero's hand.
                    Combos containing any dead card are removed.

    Returns:
        De-duplicated list of (card1, card2) tuples (treys ints).

    Raises:
        ValueError: on unparseable tokens or if range is empty after filtering.
    """
    if dead_cards is None:
        dead_cards = []

    dead_set = set(dead_cards)

    tokens = [t.strip() for t in range_str.split(",")]
    tokens = [t for t in tokens if t]  # drop empties

    if not tokens:
        raise ValueError("Range string is empty")

    all_combos: set[tuple[int, int]] = set()
    for tok in tokens:
        all_combos |= _expand_token(tok)

    # Normalise each combo so (a, b) and (b, a) are treated as the same
    normalised: set[tuple[int, int]] = set()
    for c1, c2 in all_combos:
        key = (min(c1, c2), max(c1, c2))
        normalised.add(key)

    # Remove combos containing dead cards
    if dead_set:
        filtered = {
            combo for combo in normalised
            if combo[0] not in dead_set and combo[1] not in dead_set
        }
    else:
        filtered = normalised

    if not filtered:
        raise ValueError(
            "Villain range is empty after removing dead cards"
        )

    return sorted(filtered)
