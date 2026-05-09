"""Behavior tests for full-hand setup preview."""

import pytest

from pokerbot.app import app
from pokerbot.hand_state import preview_full_hand


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_hero_button_setup_posts_blinds_and_makes_hero_first_actor():
    """Hero BTN/SB starts heads-up hand by posting SB and acting first preflop."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [],
    }

    hand_state = preview_full_hand(payload)

    assert hand_state["street"] == "preflop"
    assert hand_state["pot_bb"] == 1.5
    assert hand_state["hero_stack_bb"] == 99.5
    assert hand_state["villain_stack_bb"] == 99.0
    assert hand_state["current_actor"] == "hero"
    assert hand_state["last_aggressor"] is None
    assert hand_state["bet_to_call_bb"] == 0.5
    assert hand_state["legal_actions"] == ["fold", "call", "raise"]
    assert hand_state["analyze_allowed"] is True
    assert hand_state["disabled_reason"] is None


def test_hero_big_blind_setup_posts_blinds_and_makes_villain_first_actor():
    """Hero BB posts the big blind and waits for Villain to act preflop."""
    payload = {
        "setup": {
            "hero_position": "BB",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [],
    }

    hand_state = preview_full_hand(payload)

    assert hand_state["pot_bb"] == 1.5
    assert hand_state["hero_stack_bb"] == 99.0
    assert hand_state["villain_stack_bb"] == 99.5
    assert hand_state["current_actor"] == "villain"
    assert hand_state["analyze_allowed"] is False
    assert hand_state["disabled_reason"] == "Villain is to act"


def test_small_blind_position_behaves_like_button_in_heads_up_setup():
    """Hero SB is accepted as an alias for the heads-up button seat."""
    payload = {
        "setup": {
            "hero_position": "SB",
            "hero_stack_bb": 50,
            "villain_stack_bb": 75,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Qs", "Qh"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [],
    }

    hand_state = preview_full_hand(payload)

    assert hand_state["pot_bb"] == 1.5
    assert hand_state["hero_stack_bb"] == 49.5
    assert hand_state["villain_stack_bb"] == 74.0
    assert hand_state["current_actor"] == "hero"


def test_setup_rejects_non_positive_hero_stack():
    """Hero cannot start a full-hand preview with zero or negative stack."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 0,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [],
    }

    with pytest.raises(ValueError, match="Hero stack must be > 0"):
        preview_full_hand(payload)


def test_setup_rejects_invalid_heads_up_position():
    """Full-hand v1 only accepts heads-up BTN/SB or BB positions."""
    payload = {
        "setup": {
            "hero_position": "CO",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [],
    }

    with pytest.raises(ValueError, match="Hero position must be BTN/SB or BB"):
        preview_full_hand(payload)


def test_setup_rejects_unknown_villain_profile():
    """Villain profile must be one of the supported full-hand profile labels."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Wizard",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [],
    }

    with pytest.raises(ValueError, match="Invalid villain profile"):
        preview_full_hand(payload)


def test_setup_requires_exactly_two_unique_hero_hole_cards():
    """Hero setup is invalid until exactly two unique hole cards are selected."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [],
    }

    with pytest.raises(ValueError, match="Hero must have exactly 2 hole cards"):
        preview_full_hand(payload)


def test_setup_rejects_duplicate_hero_hole_cards():
    """Hero setup cannot use the same physical card twice."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Ah"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [],
    }

    with pytest.raises(ValueError, match="Hero hole cards must be unique"):
        preview_full_hand(payload)


def test_setup_rejects_invalid_hero_card_syntax():
    """Hero hole cards must be valid rank/suit card tokens."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kx"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [],
    }

    with pytest.raises(ValueError, match="Invalid suit"):
        preview_full_hand(payload)


def test_full_hand_preview_api_returns_auto_blinds_state(client):
    """Preview endpoint returns the setup-derived starting state as JSON."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [],
    }

    response = client.post("/api/full_hand/preview", json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["hand_state"]["pot_bb"] == 1.5
    assert data["hand_state"]["current_actor"] == "hero"


def test_full_hand_preview_api_returns_validation_error_for_invalid_setup(client):
    """Preview endpoint rejects impossible setup payloads with a clear 400."""
    payload = {
        "setup": {
            "hero_position": "UTG",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [],
    }

    response = client.post("/api/full_hand/preview", json=payload)

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Hero position" in data["error"]


def test_full_hand_preview_api_rejects_missing_json_payload(client):
    """Preview endpoint requires a JSON payload."""
    response = client.post("/api/full_hand/preview")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["error"] == "No JSON payload provided"


def test_button_raise_and_big_blind_call_closes_preflop_with_derived_pot_and_stacks():
    """User can build a legal preflop raise/call and see derived pot/stacks."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [
            {"actor": "hero", "type": "raise", "amount_added": 2.0, "input_mode": "raise_to", "input_amount": 2.5},
            {"actor": "villain", "type": "call"},
        ],
    }

    hand_state = preview_full_hand(payload)

    assert hand_state["pot_bb"] == 5.0
    assert hand_state["hero_stack_bb"] == 97.5
    assert hand_state["villain_stack_bb"] == 97.5
    assert hand_state["street"] == "preflop"
    assert hand_state["street_status"] == "awaiting_board"
    assert hand_state["awaiting_board"] == "flop"
    assert hand_state["legal_actions"] == []
    assert hand_state["analyze_allowed"] is False
    assert hand_state["disabled_reason"] == "Awaiting flop cards"


def test_preflop_preview_rejects_call_when_not_facing_a_bet():
    """Calling is illegal after the actor has already matched the current bet."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [
            {"actor": "hero", "type": "raise", "amount_added": 2.0},
            {"actor": "villain", "type": "call"},
            {"actor": "hero", "type": "call"},
        ],
    }

    with pytest.raises(ValueError, match="Cannot add actions while awaiting flop cards"):
        preview_full_hand(payload)


def test_preflop_preview_rejects_raise_that_does_not_reopen_action():
    """A preflop raise must be at least a legal minimum raise size."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [{"actor": "hero", "type": "raise", "amount_added": 1.0}],
    }

    with pytest.raises(ValueError, match="Raise must be at least"):
        preview_full_hand(payload)


def test_preflop_preview_rejects_action_from_wrong_actor():
    """User cannot add a preflop action for a player who is not to act."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [{"actor": "villain", "type": "call"}],
    }

    with pytest.raises(ValueError, match="Hero is to act"):
        preview_full_hand(payload)


def test_full_hand_preview_api_returns_preflop_timeline_state(client):
    """Preview endpoint replays legal preflop actions for the hand builder."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": [], "turn": [], "river": []},
        "actions": [
            {"actor": "hero", "type": "raise", "amount_added": 2.0},
            {"actor": "villain", "type": "call"},
        ],
    }

    response = client.post("/api/full_hand/preview", json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["hand_state"]["pot_bb"] == 5.0
    assert data["hand_state"]["awaiting_board"] == "flop"


def test_user_can_build_complete_legal_hand_to_river_hero_decision():
    """A full preflop-to-river timeline derives the river decision state."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": ["Ks", "9h", "4c"], "turn": ["2h"], "river": ["Jd"]},
        "actions": [
            {"actor": "hero", "type": "raise", "amount_added": 2.0},
            {"actor": "villain", "type": "call"},
            {"street": "flop", "actor": "villain", "type": "check"},
            {"street": "flop", "actor": "hero", "type": "bet", "amount_added": 2.0},
            {"street": "flop", "actor": "villain", "type": "call"},
            {"street": "turn", "actor": "villain", "type": "check"},
            {"street": "turn", "actor": "hero", "type": "check"},
            {"street": "river", "actor": "villain", "type": "bet", "amount_added": 6.0},
        ],
    }

    hand_state = preview_full_hand(payload)

    assert hand_state["street"] == "river"
    assert hand_state["pot_bb"] == 15.0
    assert hand_state["hero_stack_bb"] == 95.5
    assert hand_state["villain_stack_bb"] == 89.5
    assert hand_state["current_actor"] == "hero"
    assert hand_state["bet_to_call_bb"] == 6.0
    assert hand_state["legal_actions"] == ["fold", "call", "raise"]
    assert hand_state["analyze_allowed"] is True


def test_analyze_full_hand_returns_hand_state_and_range_fallback(client):
    """User can click Analyze at a Hero decision point and see range analysis."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": ["Ks", "9h", "4c"], "turn": ["2h"], "river": ["Jd"]},
        "actions": [
            {"actor": "hero", "type": "raise", "amount_added": 2.0},
            {"actor": "villain", "type": "call"},
            {"street": "flop", "actor": "villain", "type": "check"},
            {"street": "flop", "actor": "hero", "type": "bet", "amount_added": 2.0},
            {"street": "flop", "actor": "villain", "type": "call"},
            {"street": "turn", "actor": "villain", "type": "check"},
            {"street": "turn", "actor": "hero", "type": "check"},
            {"street": "river", "actor": "villain", "type": "bet", "amount_added": 6.0},
        ],
    }

    response = client.post("/api/analyze_full_hand", json=payload)

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["hand_state"]["street"] == "river"
    assert data["baseline_range"]["range"]
    assert data["range_analysis"]["estimated_range"] == data["baseline_range"]["range"]
    assert data["range_analysis"]["confidence"] == "LOW"
    assert data["range_analysis"]["fallback_used"] is True


def test_analyze_full_hand_returns_math_from_estimated_range(client):
    """Analyze shows equity and poker math from the full-hand derived state."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": ["Ks", "9h", "4c"], "turn": ["2h"], "river": ["Jd"]},
        "actions": [
            {"actor": "hero", "type": "raise", "amount_added": 2.0},
            {"actor": "villain", "type": "call"},
            {"street": "flop", "actor": "villain", "type": "check"},
            {"street": "flop", "actor": "hero", "type": "bet", "amount_added": 2.0},
            {"street": "flop", "actor": "villain", "type": "call"},
            {"street": "turn", "actor": "villain", "type": "check"},
            {"street": "turn", "actor": "hero", "type": "check"},
            {"street": "river", "actor": "villain", "type": "bet", "amount_added": 6.0},
        ],
    }

    response = client.post("/api/analyze_full_hand", json=payload)

    assert response.status_code == 200
    metrics = response.get_json()["metrics"]
    assert metrics["pot_odds_pct"] == pytest.approx(28.6, abs=0.1)
    assert metrics["spr"] == pytest.approx(5.97, abs=0.01)
    assert "equity_pct" in metrics
    assert "ev_call" in metrics
    assert metrics["outs"] == 0


def test_analyze_full_hand_returns_final_decision_section(client):
    """Analyze returns a final fold/call/raise decision with reasoning."""
    payload = {
        "setup": {
            "hero_position": "BTN",
            "hero_stack_bb": 100,
            "villain_stack_bb": 100,
            "villain_profile": "Unknown",
            "hero_hole_cards": ["Ah", "Kd"],
        },
        "board": {"flop": ["Ks", "9h", "4c"], "turn": ["2h"], "river": ["Jd"]},
        "actions": [
            {"actor": "hero", "type": "raise", "amount_added": 2.0},
            {"actor": "villain", "type": "call"},
            {"street": "flop", "actor": "villain", "type": "check"},
            {"street": "flop", "actor": "hero", "type": "bet", "amount_added": 2.0},
            {"street": "flop", "actor": "villain", "type": "call"},
            {"street": "turn", "actor": "villain", "type": "check"},
            {"street": "turn", "actor": "hero", "type": "check"},
            {"street": "river", "actor": "villain", "type": "bet", "amount_added": 6.0},
        ],
    }

    response = client.post("/api/analyze_full_hand", json=payload)

    assert response.status_code == 200
    decision = response.get_json()["decision"]
    assert decision["action"] in ["FOLD", "CALL", "RAISE"]
    assert decision["confidence"] in ["LOW", "MEDIUM", "HIGH"]
    assert decision["reasoning"]
    assert "sensitivity_note" in decision


def test_index_page_renders_full_hand_setup_workflow(client):
    """Home page exposes the Phase 1 full-hand setup workflow."""
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Full-Hand Setup" in html
    assert "Hero Position" in html
    assert "Villain Profile" in html
    assert "Auto-Blinds Preview" in html


def test_index_page_renders_full_hand_analyze_results_sections(client):
    """Home page exposes the complete full-hand Analyze workflow sections."""
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Analyze Full Hand" in html
    assert "Range Analysis" in html
    assert "Math" in html
    assert "Final Decision" in html


def test_index_page_renders_complete_hand_builder_controls(client):
    """Home page lets the user add board cards and postflop actions through river."""
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Complete Hand Builder" in html
    assert "Flop" in html
    assert "Turn" in html
    assert "River" in html
    assert "Check" in html
    assert "Bet" in html
    assert "All-In" in html


def test_index_page_renders_preflop_action_builder(client):
    """Home page lets the user build legal preflop actions after setup."""
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Preflop Action Builder" in html
    assert "Raise To" in html
    assert "Action Timeline" in html
