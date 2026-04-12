"""OpenRouter LLM Advisor integration."""

from __future__ import annotations

import os
import re
import requests
from dataclasses import dataclass
from dotenv import load_dotenv

from treys import Card

from pokerbot.math_engine import PokerMetrics

# Ensure .env is loaded
load_dotenv()


@dataclass
class Decision:
    reasoning: str
    action: str        # "FOLD" | "CALL" | "RAISE" | "ERROR"
    raise_size: str    # e.g. "120" or "N/A"
    confidence: str    # "LOW" | "MEDIUM" | "HIGH"
    raw_response: str  # Full output for debugging


_SYSTEM_PROMPT = """You are an expert No-Limit Texas Hold'em poker advisor.
You will be given a hand situation with all relevant computed metrics.
Your job is to recommend exactly ONE action: FOLD, CALL, or RAISE.

Rules:
1. Analyze the situation step by step.
2. Consider: pot odds vs equity, SPR, position, board texture, villain range, MDF, EV of calling.
3. If recommending RAISE, suggest a size (as a fraction of pot or exact chips).
4. Be concise but thorough.

Respond in this exact format:

REASONING:
<your step-by-step analysis>

DECISION: <FOLD|CALL|RAISE>
RAISE_SIZE: <amount or "N/A">
CONFIDENCE: <LOW|MEDIUM|HIGH>"""


_USER_PROMPT_TEMPLATE = """=== HAND SITUATION ===
Hole Cards: {hole_cards_pretty}
Board: {board_pretty} ({street})
Position: {position}

Pot: {pot}
Bet to Call: {bet_to_call}
My Stack: {my_stack}
Opponent Stack: {opp_stack}

Villain Range: {villain_range_str}

=== COMPUTED METRICS ===
Pot Odds: {pot_odds_pct:.1f}%
SPR: {spr:.2f}
MDF: {mdf:.1f}%
Outs: {outs_str}
Equity vs Range: {equity_pct:.1f}%
EV of Calling: {ev_call:+.1f} chips

=== TASK ===
Recommend an action: FOLD, CALL, or RAISE. Provide full reasoning."""


def _format_cards(cards: list[int]) -> str:
    if not cards:
        return "(none)"
    return " ".join(Card.int_to_str(c) for c in cards)


def build_prompt(
    hole_cards: list[int],
    board: list[int],
    pot: float,
    bet_to_call: float,
    my_stack: float,
    opp_stack: float,
    position: str,
    street: str,
    villain_range_str: str,
    metrics: PokerMetrics,
) -> str:
    """Build the exact user prompt string from the game state + metrics."""
    outs_str = str(metrics.outs)
    if metrics.outs == -1:
        outs_str = "-1 (N/A preflop)"

    return _USER_PROMPT_TEMPLATE.format(
        hole_cards_pretty=_format_cards(hole_cards),
        board_pretty=_format_cards(board),
        street=street,
        position=position,
        pot=pot,
        bet_to_call=bet_to_call,
        my_stack=my_stack,
        opp_stack=opp_stack,
        villain_range_str=villain_range_str,
        pot_odds_pct=metrics.pot_odds_pct,
        spr=metrics.spr,
        mdf=metrics.mdf,
        outs_str=outs_str,
        equity_pct=metrics.equity_pct,
        ev_call=metrics.ev_call,
    )


def parse_response(text: str) -> Decision:
    """Parse the LLM response text into a Decision dataclass."""
    action_match = re.search(r"DECISION:\s*(FOLD|CALL|RAISE)", text, re.IGNORECASE)
    raise_match = re.search(r"RAISE_SIZE:\s*(.+)", text, re.IGNORECASE)
    conf_match = re.search(r"CONFIDENCE:\s*(LOW|MEDIUM|HIGH)", text, re.IGNORECASE)

    if not action_match:
        return Decision(
            action="ERROR",
            reasoning=text,
            raise_size="N/A",
            confidence="N/A",
            raw_response=text,
        )

    action = action_match.group(1).upper()
    raise_size = raise_match.group(1).strip() if raise_match else "N/A"
    confidence = conf_match.group(1).upper() if conf_match else "N/A"

    # Extract reasoning: everything before "DECISION:"
    parts = text.split("DECISION:", 1)
    reasoning = parts[0].replace("REASONING:", "").strip()

    return Decision(
        action=action,
        reasoning=reasoning,
        raise_size=raise_size,
        confidence=confidence,
        raw_response=text,
    )


def get_decision(user_prompt: str) -> Decision:
    """Call the OpenRouter API and return a parsed Decision."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "z-ai/glm-4.5-air:free",
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 1024,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]
        return parse_response(raw_text)
    
    except requests.exceptions.Timeout:
        return Decision(
            action="ERROR",
            reasoning="API request timed out (30s)",
            raise_size="N/A",
            confidence="N/A",
            raw_response="",
        )
    except requests.exceptions.RequestException as e:
        return Decision(
            action="ERROR",
            reasoning=f"API error: {str(e)}",
            raise_size="N/A",
            confidence="N/A",
            raw_response="",
        )
