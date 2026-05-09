"""Flask Web UI for PokerBot."""

from __future__ import annotations

import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

from pokerbot.input_parser import parse_game_state, derive_street, parse_hole_cards, parse_board
from pokerbot.range_parser import parse_range
from pokerbot.math_engine import compute_metrics
from pokerbot.equity import calculate_equity
from pokerbot.advisor import build_prompt, get_decision
from pokerbot.hand_state import preview_full_hand
from pokerbot.preflop_ranges import select_baseline_range
from pokerbot.range_advisor import estimate_villain_range


# Load env to check API key early
load_dotenv()

app = Flask(__name__)


@app.route("/")
def index():
    """Serve the single-page UI."""
    has_api_key = bool(os.getenv("OPENROUTER_API_KEY"))
    return render_template("index.html", has_api_key=has_api_key)


@app.route("/api/full_hand/preview", methods=["POST"])
def full_hand_preview():
    """Preview derived full-hand state for the hand builder."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "No JSON payload provided"}), 400

    try:
        return jsonify({"success": True, "hand_state": preview_full_hand(data)})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Internal Error: {str(e)}"}), 500


def _make_full_hand_decision(hand_state: dict, range_analysis: dict, metrics: dict) -> dict:
    legal = [action.upper() for action in hand_state.get("legal_actions", [])]
    if "CALL" in legal and metrics["ev_call"] >= 0:
        action = "CALL"
        reasoning = "Calling is supported because computed call EV is non-negative against the estimated range."
    elif "FOLD" in legal:
        action = "FOLD"
        reasoning = "Folding is preferred because computed call EV is negative against the estimated range."
    elif "CHECK" in legal:
        action = "CHECK"
        reasoning = "No bet is faced, so checking is available."
    else:
        action = legal[0] if legal else "ERROR"
        reasoning = "No standard decision action was available."
    return {
        "action": action,
        "raise_to_bb": None,
        "amount_to_add_bb": None,
        "confidence": "LOW" if range_analysis.get("fallback_used") else "MEDIUM",
        "reasoning": reasoning,
        "sensitivity_note": "Decision is sensitive to the estimated villain range; fallback ranges are intentionally broad.",
        "raw_response": "",
    }


def _compute_full_hand_metrics(data: dict, hand_state: dict, range_analysis: dict) -> dict:
    setup = data["setup"]
    board_data = data.get("board", {})
    board_cards = (board_data.get("flop", []) or []) + (board_data.get("turn", []) or []) + (board_data.get("river", []) or [])
    hole = parse_hole_cards(" ".join(setup["hero_hole_cards"]))
    board = parse_board(" ".join(board_cards)) if board_cards else []
    villain_combos = parse_range(range_analysis["estimated_range"], dead_cards=hole + board)
    equity_pct = calculate_equity(hole, board, villain_combos, num_simulations=2_000, seed=1)
    computed = compute_metrics(
        hole_cards=hole,
        board=board,
        pot=hand_state["pot_bb"],
        bet_to_call=hand_state["bet_to_call_bb"],
        my_stack=hand_state["hero_stack_bb"],
        opp_stack=hand_state["villain_stack_bb"],
        equity_pct=equity_pct,
        street=hand_state["street"],
    )
    return {
        "pot_odds_pct": round(computed.pot_odds_pct, 1),
        "spr": round(computed.spr, 2),
        "mdf": round(computed.mdf, 1),
        "outs": computed.outs,
        "equity_pct": round(computed.equity_pct, 1),
        "ev_call": round(computed.ev_call, 1),
    }


@app.route("/api/analyze_full_hand", methods=["POST"])
def analyze_full_hand():
    """Analyze a validated full-hand decision point."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "No JSON payload provided"}), 400

    try:
        hand_state = preview_full_hand(data)
        if not hand_state.get("analyze_allowed"):
            return jsonify({"success": False, "error": hand_state.get("disabled_reason") or "Analyze is not allowed"}), 400
        baseline_range = select_baseline_range(data.get("actions", []))
        range_analysis = estimate_villain_range(data, hand_state, baseline_range)
        metrics = _compute_full_hand_metrics(data, hand_state, range_analysis)
        decision = _make_full_hand_decision(hand_state, range_analysis, metrics)
        return jsonify({
            "success": True,
            "hand_state": hand_state,
            "baseline_range": baseline_range,
            "range_analysis": range_analysis,
            "metrics": metrics,
            "decision": decision,
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Internal Error: {str(e)}"}), 500


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Receive game state, compute metrics, get LLM decision."""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No JSON payload provided"}), 400

    try:
        # Extract inputs
        hole_cards_str = " ".join(data.get("hole_cards", []))
        board_str = " ".join(data.get("board", []))
        pot = float(data.get("pot", 0))
        bet_to_call = float(data.get("bet_to_call", 0))
        my_stack = float(data.get("my_stack", 0))
        opp_stack = float(data.get("opp_stack", 0))
        position = data.get("position", "")
        villain_range_str = data.get("villain_range", "")

        # 1. Parse and validate inputs
        # Derive street server-side from board count
        board_count = len(data.get("board", []))
        street_map = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}
        if board_count not in street_map:
            raise ValueError(f"Board must have 0, 3, 4, or 5 cards (got {board_count})")
        street = street_map[board_count]

        # Use input_parser.py
        state = parse_game_state(
            hole_cards_str=hole_cards_str,
            board_str=board_str,
            pot=pot,
            bet_to_call=bet_to_call,
            my_stack=my_stack,
            opp_stack=opp_stack,
            position_str=position,
            street_str=street,
            villain_range_str=villain_range_str,
        )

        hole = state["hole_cards"]
        board = state["board"]

        # 2. Parse Villain Range & Compute Equity
        try:
            villain_combos = parse_range(
                state["villain_range"], dead_cards=hole + board
            )
        except ValueError as e:
            raise ValueError(f"Invalid villain range: {str(e)}")

        # For speed in UI, we might want 10k sims, but 5k is faster. Let's use 10k default.
        equity_pct = calculate_equity(
            hole_cards=hole,
            board=board,
            villain_range=villain_combos,
            num_simulations=10_000,
        )

        # 3. Compute Metrics
        metrics = compute_metrics(
            hole_cards=hole,
            board=board,
            pot=state["pot"],
            bet_to_call=state["bet_to_call"],
            my_stack=state["my_stack"],
            opp_stack=state["opp_stack"],
            equity_pct=equity_pct,
            street=state["street"],
        )

        # 4. Get LLM Decision
        prompt = build_prompt(
            hole_cards=hole,
            board=board,
            pot=state["pot"],
            bet_to_call=state["bet_to_call"],
            my_stack=state["my_stack"],
            opp_stack=state["opp_stack"],
            position=state["position"],
            street=state["street"],
            villain_range_str=state["villain_range"],
            metrics=metrics,
        )

        decision = get_decision(prompt)

        # 5. Return JSON
        return jsonify({
            "success": True,
            "metrics": {
                "pot_odds_pct": round(metrics.pot_odds_pct, 1),
                "spr": round(metrics.spr, 2),
                "mdf": round(metrics.mdf, 1),
                "outs": metrics.outs,
                "equity_pct": round(metrics.equity_pct, 1),
                "ev_call": round(metrics.ev_call, 1),
            },
            "decision": {
                "action": decision.action,
                "raise_size": decision.raise_size,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
            }
        })

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Internal Error: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
