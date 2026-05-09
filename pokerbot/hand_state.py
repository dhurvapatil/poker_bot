"""Full-hand timeline state derivation for heads-up cash games."""

from __future__ import annotations


VALID_PROFILES = {
    "Unknown",
    "Nit",
    "Tight Passive",
    "Tight Aggressive",
    "Loose Passive / Calling Station",
    "Loose Aggressive",
    "Maniac",
    "Solid Reg",
    "Weak Recreational",
}


def preview_full_hand(payload: dict) -> dict:
    """Return the derived full-hand state for the current builder payload.

    Phase 1 supports setup-only previews: blinds are posted automatically and no
    user actions are replayed yet.
    """
    setup = payload.get("setup") if isinstance(payload, dict) else None
    if not isinstance(setup, dict):
        raise ValueError("Missing setup")

    hero_position = _normalize_heads_up_position(setup.get("hero_position", ""))
    hero_stack = _parse_positive_bb(setup.get("hero_stack_bb"), "Hero stack")
    villain_stack = _parse_positive_bb(setup.get("villain_stack_bb"), "Villain stack")
    _validate_profile(setup.get("villain_profile", "Unknown"))
    _validate_hole_cards(setup.get("hero_hole_cards"))

    if hero_position in {"BTN", "SB"}:
        stacks = {"hero": hero_stack - 0.5, "villain": villain_stack - 1.0}
        contributions = {"hero": 0.5, "villain": 1.0}
        current_actor = "hero"
    else:
        stacks = {"hero": hero_stack - 1.0, "villain": villain_stack - 0.5}
        contributions = {"hero": 1.0, "villain": 0.5}
        current_actor = "villain"

    if stacks["hero"] < 0:
        raise ValueError("Hero stack is too small to post blind")
    if stacks["villain"] < 0:
        raise ValueError("Villain stack is too small to post blind")

    _validate_board(payload.get("board", {}), setup.get("hero_hole_cards"))

    pot = 1.5
    street = "preflop"
    current_bet = 1.0
    last_raise_size = 1.0
    last_aggressor = None
    street_status = "active"
    awaiting_board = None
    checked_actor = None

    actions = payload.get("actions", []) or []
    for action in actions:
        action_street = action.get("street", "preflop")
        if current_actor is None:
            if awaiting_board and action_street == awaiting_board:
                _ensure_board_available(payload.get("board", {}), awaiting_board)
                street = awaiting_board
                contributions = {"hero": 0.0, "villain": 0.0}
                current_bet = 0.0
                last_raise_size = 0.0
                current_actor = _postflop_first_actor(hero_position)
                street_status = "active"
                awaiting_board = None
                checked_actor = None
            elif awaiting_board:
                raise ValueError(f"Cannot add actions while awaiting {awaiting_board} cards")
            else:
                raise ValueError("Cannot add actions after hand ended")

        actor = action.get("actor")
        action_type = action.get("type")
        if actor != current_actor:
            raise ValueError(f"{current_actor.capitalize()} is to act")
        if action_street != street:
            raise ValueError(f"Current street is {street}")

        if action_type == "raise":
            amount_added = _parse_positive_bb(action.get("amount_added"), "Raise amount")
            new_bet = contributions[actor] + amount_added
            minimum_raise_to = current_bet + last_raise_size
            if new_bet < minimum_raise_to:
                raise ValueError(f"Raise must be at least to {minimum_raise_to}bb")
            if amount_added > stacks[actor]:
                raise ValueError("Action amount cannot exceed remaining stack")
            stacks[actor] -= amount_added
            contributions[actor] = new_bet
            pot += amount_added
            last_raise_size = new_bet - current_bet
            current_bet = new_bet
            last_aggressor = actor
            checked_actor = None
            current_actor = _other_actor(actor)
        elif action_type == "bet":
            if current_bet != 0:
                raise ValueError("Bet is only legal when no bet exists")
            amount_added = _parse_positive_bb(action.get("amount_added"), "Bet amount")
            if amount_added > stacks[actor]:
                raise ValueError("Action amount cannot exceed remaining stack")
            stacks[actor] -= amount_added
            contributions[actor] = amount_added
            pot += amount_added
            current_bet = amount_added
            last_raise_size = amount_added
            last_aggressor = actor
            checked_actor = None
            current_actor = _other_actor(actor)
        elif action_type == "call":
            amount_to_call = current_bet - contributions[actor]
            if amount_to_call <= 0:
                raise ValueError("Call is only legal when facing a bet")
            if amount_to_call > stacks[actor]:
                raise ValueError("Call amount cannot exceed remaining stack")
            stacks[actor] -= amount_to_call
            contributions[actor] += amount_to_call
            pot += amount_to_call
            current_actor = _other_actor(actor)
            if contributions["hero"] == contributions["villain"]:
                awaiting_board = _next_board_after(street)
                street_status = "awaiting_board" if awaiting_board else "hand_complete"
                current_actor = None
        elif action_type == "check":
            if current_bet != contributions[actor]:
                raise ValueError("Check is only legal when not facing a bet")
            if checked_actor and checked_actor != actor:
                awaiting_board = _next_board_after(street)
                street_status = "awaiting_board" if awaiting_board else "hand_complete"
                current_actor = None
            else:
                checked_actor = actor
                current_actor = _other_actor(actor)
        elif action_type == "fold":
            street_status = "hand_ended"
            current_actor = None
        else:
            raise ValueError(f"Unsupported action '{action_type}'")

    bet_to_call = 0.0 if current_actor is None else max(0.0, current_bet - contributions[current_actor])
    legal_actions = [] if current_actor is None else ["fold", "call", "raise"]
    disabled_reason = _disabled_reason(current_actor, street_status, awaiting_board)

    return {
        "street": street,
        "pot_bb": pot,
        "hero_stack_bb": stacks["hero"],
        "villain_stack_bb": stacks["villain"],
        "current_actor": current_actor,
        "last_aggressor": last_aggressor,
        "bet_to_call_bb": bet_to_call,
        "legal_actions": legal_actions,
        "analyze_allowed": current_actor == "hero" and street_status == "active",
        "disabled_reason": disabled_reason,
        "street_status": street_status,
        "awaiting_board": awaiting_board,
    }


def _other_actor(actor: str) -> str:
    return "villain" if actor == "hero" else "hero"


def _postflop_first_actor(hero_position: str) -> str:
    return "villain" if hero_position in {"BTN", "SB"} else "hero"


def _next_board_after(street: str) -> str | None:
    return {"preflop": "flop", "flop": "turn", "turn": "river"}.get(street)


def _ensure_board_available(board: object, street: str) -> None:
    if not isinstance(board, dict):
        raise ValueError("Board must be grouped by street")
    expected_counts = {"flop": 3, "turn": 1, "river": 1}
    cards = board.get(street, [])
    if not isinstance(cards, list) or len(cards) != expected_counts[street]:
        raise ValueError(f"{street.capitalize()} cards are required")


def _validate_board(board: object, hero_cards: object) -> None:
    if board in (None, {}):
        return
    if not isinstance(board, dict):
        raise ValueError("Board must be grouped by street")
    all_cards = []
    for street in ("flop", "turn", "river"):
        cards = board.get(street, []) or []
        if not isinstance(cards, list):
            raise ValueError(f"{street.capitalize()} cards must be a list")
        all_cards.extend(str(card).strip() for card in cards)
    hero = [str(card).strip() for card in (hero_cards or [])]
    combined = hero + all_cards
    if len(combined) != len(set(combined)):
        raise ValueError("Duplicate cards are not allowed")
    from pokerbot.input_parser import parse_board

    if all_cards:
        parse_board(" ".join(all_cards))


def _disabled_reason(current_actor: str | None, street_status: str, awaiting_board: str | None) -> str | None:
    if awaiting_board:
        return f"Awaiting {awaiting_board} cards"
    if street_status == "hand_ended":
        return "Hand ended"
    if current_actor == "villain":
        return "Villain is to act"
    return None


def _normalize_heads_up_position(raw: object) -> str:
    value = str(raw).strip().upper()
    if value not in {"BTN", "SB", "BB"}:
        raise ValueError("Hero position must be BTN/SB or BB")
    return value


def _parse_positive_bb(raw: object, label: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number") from None
    if value <= 0:
        raise ValueError(f"{label} must be > 0")
    return value


def _validate_profile(raw: object) -> None:
    profile = str(raw).strip() if raw is not None else "Unknown"
    if profile not in VALID_PROFILES:
        raise ValueError("Invalid villain profile")


def _validate_hole_cards(raw: object) -> None:
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError("Hero must have exactly 2 hole cards")
    normalized = [str(card).strip() for card in raw]
    if len(set(normalized)) != 2:
        raise ValueError("Hero hole cards must be unique")
    # Reuse the existing public parser for syntax validation.
    from pokerbot.input_parser import parse_hole_cards

    parse_hole_cards(" ".join(normalized))
