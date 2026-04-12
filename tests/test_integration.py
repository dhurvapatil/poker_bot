"""End-to-end integration tests using the real OpenRouter API.

These tests hit the real Claude model to ensure the entire pipeline works.
"""

import pytest
import os
from pprint import pprint

from pokerbot.app import app
from pokerbot.input_parser import parse_game_state
from pokerbot.range_parser import parse_range
from pokerbot.equity import calculate_equity
from pokerbot.math_engine import compute_metrics
from pokerbot.advisor import build_prompt, get_decision

# Skip these tests if API key is not present, though the user said they added it.
pytestmark = pytest.mark.integration


def _run_pipeline(
    hole_str: str,
    board_str: str,
    pot: float,
    bet: float,
    my_stack: float,
    opp_stack: float,
    pos: str,
    street: str,
    v_range: str,
):
    """Helper to run the full Python pipeline."""
    state = parse_game_state(
        hole_str, board_str, pot, bet, my_stack, opp_stack, pos, street, v_range
    )
    hole = state["hole_cards"]
    board = state["board"]
    villain_combos = parse_range(state["villain_range"], dead_cards=hole + board)
    eq = calculate_equity(hole, board, villain_combos, num_simulations=5000)
    metrics = compute_metrics(
        hole, board, state["pot"], state["bet_to_call"], 
        state["my_stack"], state["opp_stack"], eq, state["street"]
    )
    prompt = build_prompt(
        hole, board, state["pot"], state["bet_to_call"], 
        state["my_stack"], state["opp_stack"], state["position"], 
        state["street"], state["villain_range"], metrics
    )
    return get_decision(prompt)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_full_pipeline_obvious_fold():
    """#1 — Obvious fold on river.
    Hero has 7 high, board is a royal flush, villain has AA. 
    Bet is huge relative to pot.
    """
    decision = _run_pipeline(
        hole_str="7h2c",
        board_str="AsKsQsJsTs",
        pot=50,
        bet=100,
        my_stack=500,
        opp_stack=500,
        pos="BB",
        street="river",
        v_range="AA",
    )
    print(f"\n--- OBVIOUS FOLD SCENARIO ---")
    print(f"Action: {decision.action} (Confidence: {decision.confidence})")
    print(f"Reasoning:\n{decision.reasoning}")
    
    assert decision.action in ["FOLD", "CALL", "RAISE"]
    assert decision.action == "FOLD"


def test_full_pipeline_obvious_call():
    """#2 — Obvious call/raise on flop.
    Hero has quad Aces. Bet is tiny.
    """
    decision = _run_pipeline(
        hole_str="AhAs",
        board_str="AcAdKs",
        pot=500,
        bet=10,
        my_stack=1000,
        opp_stack=1000,
        pos="BTN",
        street="flop",
        v_range="KK",
    )
    print(f"\n--- OBVIOUS CALL/RAISE SCENARIO ---")
    print(f"Action: {decision.action} (Confidence: {decision.confidence})")
    print(f"Reasoning:\n{decision.reasoning}")

    assert decision.action in ["FOLD", "CALL", "RAISE"]
    # With quads, either a call (to trap) or raise is acceptable.
    assert decision.action in ["CALL", "RAISE"]


def test_full_pipeline_preflop():
    """#3 — Standard preflop spot."""
    decision = _run_pipeline(
        hole_str="AhKd",
        board_str="",
        pot=30,
        bet=20,
        my_stack=500,
        opp_stack=500,
        pos="BTN",
        street="preflop",
        v_range="TT+, AQ+",
    )
    print(f"\n--- PREFLOP SCENARIO ---")
    print(f"Action: {decision.action} (Confidence: {decision.confidence})")
    print(f"Reasoning:\n{decision.reasoning}")

    assert decision.action in ["FOLD", "CALL", "RAISE"]


def test_full_via_flask_client(client):
    """#4 — End-to-end through the HTTP API."""
    payload = {
        "hole_cards": ["Ah", "Kd"],
        "board": ["Ts", "9h", "2c"],
        "pot": 120,
        "bet_to_call": 40,
        "my_stack": 500,
        "opp_stack": 480,
        "position": "BTN",
        "villain_range": "TT+, AK"
    }
    res = client.post("/api/analyze", json=payload)
    
    assert res.status_code == 200
    data = res.get_json()
    
    assert data["success"] is True
    assert "metrics" in data
    assert "decision" in data
    assert data["decision"]["action"] in ["FOLD", "CALL", "RAISE"]
    
    print(f"\n--- FLASK HTTP API SCENARIO ---")
    print(f"Action: {data['decision']['action']}")
    print(f"Reasoning:\n{data['decision']['reasoning']}")
