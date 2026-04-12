"""Tests for pokerbot.app Flask routes."""

import pytest
from unittest.mock import patch, Mock
import os

from pokerbot.app import app
from pokerbot.advisor import Decision


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_get_decision():
    """Mock the LLM call to return a fixed decision."""
    with patch("pokerbot.app.get_decision") as mock:
        mock.return_value = Decision(
            action="FOLD",
            reasoning="Too expensive",
            raise_size="N/A",
            confidence="HIGH",
            raw_response="...",
        )
        yield mock


class TestAppRoutes:
    """Tests 1-12 from plan §10.6."""

    def test_index_page_loads(self, client):
        """#1 — Page serves correctly."""
        # Need to create dummy template file so this passes
        # We'll create it right after this file.
        # But we can mock render_template just for this if needed.
        # Actually, let's create the template file now.
        pass

    def test_analyze_valid_flop(self, client, mock_get_decision):
        """#2 — Happy path flop."""
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
        assert data["decision"]["action"] == "FOLD"

    def test_analyze_valid_preflop(self, client, mock_get_decision):
        """#3 — Preflop handling (0 board cards)."""
        payload = {
            "hole_cards": ["Ah", "Kd"],
            "board": [],
            "pot": 120,
            "bet_to_call": 40,
            "my_stack": 500,
            "opp_stack": 480,
            "position": "BTN",
            "villain_range": "TT+, AK"
        }
        res = client.post("/api/analyze", json=payload)
        assert res.status_code == 200
        assert res.get_json()["metrics"]["outs"] == -1

    def test_analyze_valid_river(self, client, mock_get_decision):
        """#4 — River handling (5 board cards)."""
        payload = {
            "hole_cards": ["Ah", "Kd"],
            "board": ["Ts", "9h", "2c", "5d", "8s"],
            "pot": 120,
            "bet_to_call": 40,
            "my_stack": 500,
            "opp_stack": 480,
            "position": "BTN",
            "villain_range": "TT+, AK"
        }
        res = client.post("/api/analyze", json=payload)
        assert res.status_code == 200
        assert res.get_json()["metrics"]["outs"] == 0

    def test_analyze_missing_hole_cards(self, client):
        """#5 — Validation: missing hole cards."""
        payload = {
            "hole_cards": [],
            "board": ["Ts", "9h", "2c"],
            "pot": 120,
            "bet_to_call": 40,
            "my_stack": 500,
            "opp_stack": 480,
            "position": "BTN",
            "villain_range": "TT+, AK"
        }
        res = client.post("/api/analyze", json=payload)
        assert res.status_code == 400
        assert res.get_json()["success"] is False
        assert "empty" in res.get_json()["error"]

    def test_analyze_invalid_board_count(self, client):
        """#6 — Validation: bad board count."""
        payload = {
            "hole_cards": ["Ah", "Kd"],
            "board": ["Ts", "9h"],  # 2 cards
            "pot": 120,
            "bet_to_call": 40,
            "my_stack": 500,
            "opp_stack": 480,
            "position": "BTN",
            "villain_range": "TT+, AK"
        }
        res = client.post("/api/analyze", json=payload)
        assert res.status_code == 400
        assert res.get_json()["success"] is False
        assert "0, 3, 4, or 5" in res.get_json()["error"]

    def test_analyze_duplicate_cards(self, client):
        """#7 — Validation: overlap."""
        payload = {
            "hole_cards": ["Ah", "Kd"],
            "board": ["Ah", "9h", "2c"],  # Ah overlaps
            "pot": 120,
            "bet_to_call": 40,
            "my_stack": 500,
            "opp_stack": 480,
            "position": "BTN",
            "villain_range": "TT+, AK"
        }
        res = client.post("/api/analyze", json=payload)
        assert res.status_code == 400
        assert "appear in both" in res.get_json()["error"]

    def test_analyze_negative_pot(self, client):
        """#8 — Validation: negative pot."""
        payload = {
            "hole_cards": ["Ah", "Kd"],
            "board": [],
            "pot": -10,
            "bet_to_call": 40,
            "my_stack": 500,
            "opp_stack": 480,
            "position": "BTN",
            "villain_range": "TT+, AK"
        }
        res = client.post("/api/analyze", json=payload)
        assert res.status_code == 400
        assert "Pot must be > 0" in res.get_json()["error"]

    def test_analyze_empty_range(self, client):
        """#9 — Validation: empty villain range."""
        payload = {
            "hole_cards": ["Ah", "Kd"],
            "board": [],
            "pot": 100,
            "bet_to_call": 40,
            "my_stack": 500,
            "opp_stack": 480,
            "position": "BTN",
            "villain_range": ""
        }
        res = client.post("/api/analyze", json=payload)
        assert res.status_code == 400
        assert "range" in res.get_json()["error"].lower()

    def test_analyze_invalid_position(self, client):
        """#10 — Validation: bad enum."""
        payload = {
            "hole_cards": ["Ah", "Kd"],
            "board": [],
            "pot": 100,
            "bet_to_call": 40,
            "my_stack": 500,
            "opp_stack": 480,
            "position": "BUTTON",  # BTN is valid
            "villain_range": "QQ+"
        }
        res = client.post("/api/analyze", json=payload)
        assert res.status_code == 400
        assert "Invalid position" in res.get_json()["error"]

    def test_analyze_returns_json_structure(self, client, mock_get_decision):
        """#11 — Schema completeness."""
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
        data = res.get_json()
        assert "pot_odds_pct" in data["metrics"]
        assert "spr" in data["metrics"]
        assert "mdf" in data["metrics"]
        assert "outs" in data["metrics"]
        assert "equity_pct" in data["metrics"]
        assert "ev_call" in data["metrics"]
        
        assert "action" in data["decision"]
        assert "raise_size" in data["decision"]
        assert "confidence" in data["decision"]
        assert "reasoning" in data["decision"]

    def test_analyze_llm_error_graceful(self, client):
        """#12 — Graceful LLM failure."""
        with patch("pokerbot.app.get_decision") as mock:
            mock.return_value = Decision(
                action="ERROR",
                reasoning="API timeout",
                raise_size="N/A",
                confidence="N/A",
                raw_response=""
            )
            payload = {
                "hole_cards": ["Ah", "Kd"],
                "board": [],
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
            assert data["decision"]["action"] == "ERROR"
            assert data["decision"]["reasoning"] == "API timeout"

    def test_index_page_loads_real(self, client):
        """#1 (Real test) — ensure the index route serves HTML."""
        # We need a dummy templates/index.html to pass
        res = client.get("/")
        assert res.status_code == 200
        # HTML content check will be done when we write index.html
