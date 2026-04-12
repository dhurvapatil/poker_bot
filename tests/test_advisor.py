"""Tests for pokerbot.advisor — covers all 8 cases from plan §10.5."""

import pytest
import requests
from unittest.mock import Mock, patch

from treys import Card

from pokerbot.math_engine import PokerMetrics
from pokerbot.advisor import (
    Decision,
    parse_response,
    build_prompt,
    get_decision,
)


class TestParseResponse:
    """Tests 1-4: Regex parsing of LLM output."""

    def test_parse_fold_response(self):
        """#1 — Valid FOLD."""
        text = "REASONING:\nBad odds\nDECISION: FOLD\nRAISE_SIZE: N/A\nCONFIDENCE: HIGH"
        d = parse_response(text)
        assert d.action == "FOLD"
        assert d.confidence == "HIGH"
        assert d.raise_size == "N/A"
        assert "Bad odds" in d.reasoning

    def test_parse_call_response(self):
        """#2 — Valid CALL."""
        text = "REASONING:\nGood odds\nDECISION: CALL\nRAISE_SIZE: N/A\nCONFIDENCE: MEDIUM"
        d = parse_response(text)
        assert d.action == "CALL"
        assert d.confidence == "MEDIUM"

    def test_parse_raise_response(self):
        """#3 — Valid RAISE."""
        text = "REASONING:\nStrong hand\nDECISION: RAISE\nRAISE_SIZE: 120\nCONFIDENCE: HIGH"
        d = parse_response(text)
        assert d.action == "RAISE"
        assert d.raise_size == "120"

    def test_parse_malformed_response(self):
        """#4 — Graceful degradation on bad format."""
        text = "I think you should fold because the odds are bad."
        d = parse_response(text)
        assert d.action == "ERROR"
        assert d.reasoning == text


class TestBuildPrompt:
    """Test 5: Prompt construction."""

    def test_prompt_contains_metrics(self):
        """#5 — Ensure all data is formatted into the string."""
        hole = [Card.new("Ah"), Card.new("Kd")]
        board = [Card.new("Ts"), Card.new("9h"), Card.new("2c")]
        metrics = PokerMetrics(
            pot_odds_pct=25.0,
            spr=4.0,
            mdf=75.0,
            outs=6,
            equity_pct=38.2,
            ev_call=-1.1,
        )

        prompt = build_prompt(
            hole_cards=hole,
            board=board,
            pot=120,
            bet_to_call=40,
            my_stack=500,
            opp_stack=480,
            position="BTN",
            street="flop",
            villain_range_str="TT+, AK",
            metrics=metrics,
        )

        assert "Ah Kd" in prompt
        assert "Ts 9h 2c" in prompt
        assert "(flop)" in prompt
        assert "BTN" in prompt
        assert "120" in prompt
        assert "TT+, AK" in prompt
        assert "25.0%" in prompt
        assert "4.00" in prompt
        assert "75.0%" in prompt
        assert "Outs: 6" in prompt
        assert "38.2%" in prompt
        assert "-1.1 chips" in prompt


class TestApiCall:
    """Tests 6-8: API interactions (mocked)."""

    @patch("os.getenv")
    def test_api_key_missing(self, mock_getenv):
        """#8 — Config validation."""
        mock_getenv.return_value = None
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY not set"):
            get_decision("Test prompt")

    @patch("requests.post")
    @patch("os.getenv")
    def test_api_error_handling(self, mock_getenv, mock_post):
        """#6 — HTTP error handling."""
        mock_getenv.return_value = "dummy_key"
        # Setup mock to raise HTTPError
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        d = get_decision("Test prompt")
        assert d.action == "ERROR"
        assert "500 Server Error" in d.reasoning

    @patch("requests.post")
    @patch("os.getenv")
    def test_api_timeout(self, mock_getenv, mock_post):
        """#7 — Timeout handling."""
        mock_getenv.return_value = "dummy_key"
        mock_post.side_effect = requests.exceptions.Timeout("Read timed out")

        d = get_decision("Test prompt")
        assert d.action == "ERROR"
        assert "timed out" in d.reasoning

    @patch("requests.post")
    @patch("os.getenv")
    def test_api_success(self, mock_getenv, mock_post):
        """Extra — successful API call."""
        mock_getenv.return_value = "dummy_key"
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "REASONING:\nFold it\nDECISION: FOLD\nRAISE_SIZE: N/A\nCONFIDENCE: HIGH"
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        d = get_decision("Test prompt")
        assert d.action == "FOLD"
        assert d.confidence == "HIGH"
        assert "Fold it" in d.reasoning
