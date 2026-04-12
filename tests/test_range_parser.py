"""Tests for pokerbot.range_parser — covers all 16 cases from plan §10.1."""

import pytest
from treys import Card

from pokerbot.range_parser import parse_range


class TestSingleHands:
    """Tests 1-6: basic hand expansions."""

    def test_single_pair(self):
        """#1 — AA → 6 combos."""
        combos = parse_range("AA")
        assert len(combos) == 6

    def test_pair_plus(self):
        """#2 — QQ+ → QQ, KK, AA = 18 combos."""
        combos = parse_range("QQ+")
        assert len(combos) == 18

        # Verify it contains AA, KK, QQ but not JJ
        aa = parse_range("AA")
        kk = parse_range("KK")
        qq = parse_range("QQ")
        jj = parse_range("JJ")

        combo_set = set(combos)
        for c in aa:
            assert c in combo_set
        for c in kk:
            assert c in combo_set
        for c in qq:
            assert c in combo_set
        for c in jj:
            assert c not in combo_set

    def test_pair_range(self):
        """#3 — 88-55 → 55,66,77,88 = 24 combos."""
        combos = parse_range("88-55")
        assert len(combos) == 24

    def test_suited_hand(self):
        """#4 — AKs → 4 combos (one per suit)."""
        combos = parse_range("AKs")
        assert len(combos) == 4

        # Each combo should be same suit
        for c1, c2 in combos:
            s1 = Card.get_suit_int(c1)
            s2 = Card.get_suit_int(c2)
            assert s1 == s2, "Suited combo should have matching suits"

    def test_offsuit_hand(self):
        """#5 — AKo → 12 combos."""
        combos = parse_range("AKo")
        assert len(combos) == 12

        # Each combo should be different suit
        for c1, c2 in combos:
            s1 = Card.get_suit_int(c1)
            s2 = Card.get_suit_int(c2)
            assert s1 != s2, "Offsuit combo should have different suits"

    def test_any_hand(self):
        """#6 — AK → 16 combos (4 suited + 12 offsuit)."""
        combos = parse_range("AK")
        assert len(combos) == 16


class TestPlusRanges:
    """Tests 7-9: + operator on non-pair hands."""

    def test_suited_plus(self):
        """#7 — ATs+ → ATs, AJs, AQs, AKs = 4 × 4 = 16 combos."""
        combos = parse_range("ATs+")
        assert len(combos) == 16

        # Verify each combo is suited
        for c1, c2 in combos:
            assert Card.get_suit_int(c1) == Card.get_suit_int(c2)

    def test_offsuit_plus(self):
        """#8 — ATo+ → ATo, AJo, AQo, AKo = 4 × 12 = 48 combos."""
        combos = parse_range("ATo+")
        assert len(combos) == 48

    def test_any_plus(self):
        """#9 — AT+ → AT, AJ, AQ, AK = 4 × 16 = 64 combos."""
        combos = parse_range("AT+")
        assert len(combos) == 64


class TestDashRanges:
    """Test 10: dash range for non-pair hands."""

    def test_suited_dash_range(self):
        """#10 — KTs-K8s → K8s, K9s, KTs = 3 × 4 = 12 combos."""
        combos = parse_range("KTs-K8s")
        assert len(combos) == 12

        for c1, c2 in combos:
            assert Card.get_suit_int(c1) == Card.get_suit_int(c2)


class TestComplexAndEdgeCases:
    """Tests 11-16: multi-token, dead cards, dedup, errors, whitespace."""

    def test_complex_range(self):
        """#11 — 'TT+, AKs, AQo' → 30 + 4 + 12 = 46 combos (no overlap).

        TT+ = TT,JJ,QQ,KK,AA = 5 pairs × 6 = 30
        (plan said 18 which was QQ+; TT+ is actually 30)
        """
        combos = parse_range("TT+, AKs, AQo")
        assert len(combos) == 46

    def test_dead_card_removal(self):
        """#12 — AA with Ah, Ad dead → remove combos containing either.

        AA has 6 combos: AhAd, AhAc, AhAs, AdAc, AdAs, AcAs
        Dead = {Ah, Ad}
        Remove any with Ah or Ad → only AcAs remains = 1?
        Wait: combos with Ah: AhAd, AhAc, AhAs (3)
              combos with Ad: AhAd, AdAc, AdAs (3)
              union = AhAd, AhAc, AhAs, AdAc, AdAs (5)
              remaining = AcAs (1)
        
        Plan says 3 combos — let me re-check the plan:
        "dead=[Ah, Ad] → 3 combos (remove any with Ah or Ad)"
        
        Actually there are 6 combos. Removing those with Ah removes 3 
        (AhAd, AhAc, AhAs). But Ad also removes AdAc and AdAs (AhAd 
        already removed). So 6 - 5 = 1. The plan says 3, which seems 
        like the plan means dead=[Ah] only getting 3 remaining, or 
        dead=[Ad] only getting 3 remaining.
        
        The plan says dead=[Ah, Ad] → 3 combos. That's actually wrong 
        math. With 2 dead cards from the same rank, you get C(2,2)=1 
        remaining. With 1 dead card you get C(3,2)=3.
        
        We'll test what our code actually does — which is correct poker math.
        """
        dead = [Card.new("Ah"), Card.new("Ad")]
        combos = parse_range("AA", dead_cards=dead)
        # 6 total - 5 containing Ah or Ad = 1 remaining (AcAs)
        assert len(combos) == 1

    def test_dead_card_removal_single(self):
        """Extra — AA with just Ah dead → 3 remaining combos."""
        dead = [Card.new("Ah")]
        combos = parse_range("AA", dead_cards=dead)
        # Remove AhAd, AhAc, AhAs → 3 remaining
        assert len(combos) == 3

    def test_empty_after_filter(self):
        """#13 — range is empty after dead-card removal → ValueError."""
        # AKs = 4 combos; kill all 4 aces
        dead = [Card.new("Ah"), Card.new("Ad"), Card.new("Ac"), Card.new("As")]
        with pytest.raises(ValueError, match="empty"):
            parse_range("AKs", dead_cards=dead)

    def test_duplicate_combos(self):
        """#14 — 'AA, AA' → still 6 (deduplicated)."""
        combos = parse_range("AA, AA")
        assert len(combos) == 6

    def test_invalid_token(self):
        """#15 — 'XY+' → ValueError."""
        with pytest.raises(ValueError):
            parse_range("XY+")

    def test_whitespace_handling(self):
        """#16 — ' TT+ , AK ' → same as 'TT+, AK'."""
        clean = parse_range("TT+, AK")
        messy = parse_range(" TT+ , AK ")
        assert set(clean) == set(messy)


class TestAdditionalValidation:
    """Extra tests for edge-case correctness."""

    def test_pair_range_reversed(self):
        """55-88 should work the same as 88-55."""
        a = parse_range("88-55")
        b = parse_range("55-88")
        assert set(a) == set(b)

    def test_22_lowest_pair(self):
        """22 is valid."""
        combos = parse_range("22")
        assert len(combos) == 6

    def test_22_plus_is_all_pairs(self):
        """22+ → all 13 pairs × 6 = 78 combos."""
        combos = parse_range("22+")
        assert len(combos) == 78

    def test_no_dead_cards_default(self):
        """Calling without dead_cards should work."""
        combos = parse_range("AA")
        assert len(combos) == 6

    def test_suited_and_offsuit_no_overlap(self):
        """AKs and AKo should have zero shared combos."""
        suited = set(parse_range("AKs"))
        offsuit = set(parse_range("AKo"))
        assert suited & offsuit == set()
        assert len(suited | offsuit) == 16

    def test_combo_cards_are_valid_treys_ints(self):
        """Every card in every combo should be a valid treys int."""
        combos = parse_range("TT+, AKs")
        for c1, c2 in combos:
            # treys Card ints are non-zero integers
            assert isinstance(c1, int) and c1 != 0
            assert isinstance(c2, int) and c2 != 0
            # Should be convertible back to string
            Card.int_to_str(c1)
            Card.int_to_str(c2)
