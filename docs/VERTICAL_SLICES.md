# Vertical Slice Implementation Plan — Full-Hand PokerBot Advisor

This plan restructures the PRD and issue breakdown into tight vertical slices. Each phase adds a real user-facing capability across data model, backend, API, frontend, and tests.

---

## HITL vs AFK Labels

- **AFK**: Can be implemented mostly autonomously from the spec and existing codebase.
- **HITL**: Human-in-the-loop review recommended because the phase involves UX feel, poker-strategy prompt quality, model behavior, visual polish, or product tradeoffs.

---

## Existing Codebase Context

Current app shape:

- `pokerbot/app.py`
  - Serves `/`
  - Has existing snapshot endpoint: `POST /api/analyze`
- `pokerbot/templates/index.html`
  - Current snapshot UI with card picker, pot input, bet-to-call input, stack inputs, position selector, villain range input, Analyze button, and results panel
- Existing reusable backend modules:
  - `input_parser.py`
  - `range_parser.py`
  - `math_engine.py`
  - `equity.py`
  - `advisor.py`
- Existing tests:
  - parser, range, math, equity, advisor, app, integration tests

The new flow should gradually replace the visible snapshot flow while keeping the app runnable after every phase.

---

# Phase 1 — Setup + Auto-Blinds Preview

**Label:** AFK

## User can DO / SEE

A user can open the app and enter the starting heads-up cash-game setup:

- Hero position: `BTN/SB` or `BB`
- Hero stack in bb
- Villain stack in bb
- Villain profile
- Hero hole cards

The app shows the derived starting hand state:

- SB/BB auto-posted as `0.5bb / 1bb`
- Starting pot = `1.5bb`
- Hero remaining stack
- Villain remaining stack
- First actor preflop
- Current street = `preflop`
- Legal first actions

Example visible output:

```text
Blinds posted automatically
Pot: 1.5bb
Hero stack: 99.5bb
Villain stack: 99bb
First actor: Hero
Legal actions: Fold, Call, Raise
```

## Layers Touched

### Data model

- Add minimal `pokerbot/hand_state.py` with:
  - `HandSetup`
  - `PlayerState`
  - `DerivedHandState`
  - setup validation
  - blind posting
  - first actor derivation
  - initial legal actions

### Backend

- Validate stack sizes, position, villain profile, and hero hole cards.
- Normalize `BTN` and `SB` as heads-up small-blind/button.
- Auto-post blinds.
- Derive initial pot/stacks/current actor.

### API

Add a preview endpoint used by the UI as the user edits setup:

```http
POST /api/full_hand/preview
```

Initial request:

```json
{
  "setup": {
    "hero_position": "BTN",
    "hero_stack_bb": 100,
    "villain_stack_bb": 100,
    "villain_profile": "Unknown",
    "hero_hole_cards": ["Ah", "Kd"]
  },
  "board": {"flop": [], "turn": [], "river": []},
  "actions": []
}
```

Initial response:

```json
{
  "success": true,
  "hand_state": {
    "street": "preflop",
    "pot_bb": 1.5,
    "hero_stack_bb": 99.5,
    "villain_stack_bb": 99.0,
    "current_actor": "hero",
    "last_aggressor": null,
    "bet_to_call_bb": 0.5,
    "legal_actions": ["fold", "call", "raise"],
    "analyze_allowed": true,
    "disabled_reason": null
  }
}
```

### Frontend

- Replace the snapshot `Game State` form with a new `Setup` panel.
- Keep the existing dark theme and card picker style.
- Limit visible position choices to heads-up positions.
- Add villain profile dropdown.
- Show auto-blinds preview / starting hand state.
- The old `/api/analyze` may remain in code but should not be the visible main flow.

### Tests

- Unit tests for setup validation and blind posting.
- Route tests for `/api/full_hand/preview` with no actions.
- App route test confirms new setup UI renders.

## Explicitly NOT Included Yet

- No user-entered betting actions.
- No action timeline.
- No board-by-street action flow.
- No Range LLM.
- No Decision LLM.
- No equity/math from full-hand state.
- No final Analyze pipeline.

## Blocked By

None.

---

# Phase 2 — Legal Preflop Action Builder

**Label:** AFK

## User can DO / SEE

A user can build a legal preflop heads-up action sequence and see pot/stacks update after each action.

Example flow:

```text
Hero BTN/SB 100bb, Villain BB 100bb
Blinds auto-posted: pot 1.5bb
Hero raises to 2.5bb using raise-to helper
Villain calls
App shows:
  Pot: 5bb
  Hero stack: 97.5bb
  Villain stack: 97.5bb
  Preflop betting closed
  Awaiting flop cards
```

The UI prevents illegal preflop actions and shows disabled reasons.

Examples:

- User cannot call when no bet is faced.
- User cannot check preflop while facing the blind/bet.
- User cannot raise too small.
- User cannot act out of turn.
- User cannot add actions after a fold.

The user sees an action timeline:

```text
Preflop
Hero posts SB 0.5bb (auto)
Villain posts BB 1bb (auto)
Hero raises, adds 2.0bb (to 2.5bb)
Villain calls, adds 1.5bb
```

## Layers Touched

### Data model

- Add `HandAction` model.
- Support actors:
  - `hero`
  - `villain`
- Support preflop actions:
  - `fold`
  - `call`
  - `raise`
- Add incremental `amount_added` handling.
- Add optional `input_mode` and `input_amount` for raise-to helper audit.
- Add min-raise tracking.
- Add hand-ended state.
- Add disabled reason / validation result fields.

### Backend

- Replay preflop actions after blind posting.
- Track pot, stacks, current street contributions, and current bet.
- Compute call amount automatically.
- Track current actor.
- Track last aggressor.
- Detect preflop betting closure.
- Enforce strict preflop validation:
  - correct actor acts in turn
  - call only when facing a bet
  - raise only when legal
  - min raise rules
  - no over-stack actions
  - fold ends hand
  - no actions after hand end

### API

- Extend `/api/full_hand/preview` to accept preflop actions.
- Return:
  - updated hand state
  - legal actions
  - disabled reason
  - min raise info
  - timeline-ready action summaries if useful

### Frontend

- Add preflop action builder.
- Add legal action buttons:
  - fold
  - call
  - raise
- Add amount input in bb.
- Add raise-to helper that converts total size to incremental `amount_added`.
- Gate action buttons based on legal actions.
- Show disabled reason.
- Add visible action timeline.

### Tests

- Preflop raise/call pot and stacks.
- Call amount calculation.
- Hero BTN/SB and Hero BB actor order.
- Illegal call when no bet exists.
- Illegal check if exposed internally.
- Illegal raise too small.
- Illegal wrong actor.
- No actions after fold.
- API route tests for valid and invalid preflop sequences.

## Explicitly NOT Included Yet

- No flop/turn/river actions.
- No postflop check/bet logic.
- No all-in support unless trivial from stack validation.
- No Analyze LLM pipeline.
- No range estimation.
- No computed equity.
- No final decision.

## Blocked By

- Phase 1

---

# Phase 3 — Complete Legal Hand Builder Through River

**Label:** AFK

## User can DO / SEE

A user can build a complete legal heads-up hand from preflop through river.

Example full flow:

```text
Preflop:
Hero raises to 2.5bb
Villain calls

Flop: Ks 9h 4c
Villain checks
Hero bets 2bb
Villain calls

Turn: 2h
Villain checks
Hero checks

River: Jd
Villain bets 6bb
Hero faces decision
```

The app shows:

- board cards by street
- full action timeline grouped by street
- pot and stacks across all streets
- legal actions on each street
- street advancement messages:
  - awaiting flop
  - awaiting turn
  - awaiting river
  - hand complete
- all-in locked state when no further decision exists

## Layers Touched

### Data model

- Add `BoardState` grouped by:
  - flop
  - turn
  - river
- Support all streets:
  - `preflop`
  - `flop`
  - `turn`
  - `river`
- Support postflop actions:
  - `check`
  - `fold`
  - `call`
  - `bet`
  - `raise`
- Add all-in flag behavior.
- Add all-in locked state.
- Add street lifecycle state:
  - active
  - closed
  - awaiting board
  - hand complete

### Backend

- Validate board requirements:
  - flop exactly 3 cards
  - turn exactly 1 new card
  - river exactly 1 new card
- Reject actions before required board cards exist.
- Reset street contributions when advancing streets.
- Support postflop check/check closure.
- Support postflop bet/call closure.
- Support postflop raises and min-raise validation.
- Support all-in flag on call/bet/raise.
- Detect all-in lock.
- Detect river betting completion.
- Validate no duplicate cards across hero and board.

### API

- `/api/full_hand/preview` supports full timeline across all streets.
- Response includes:
  - current street
  - board state
  - awaiting board flag
  - hand ended flag
  - all-in locked flag
  - legal actions
  - disabled reason
  - pot/stacks/bet-to-call/min-raise

### Frontend

- Board picker supports flop, turn, river entry in sequence.
- Board picker appears only when board cards are needed.
- Postflop action buttons appear based on legal actions.
- Add bet and check actions.
- Add postflop raise support.
- Add all-in toggle.
- Timeline displays complete hand grouped by street.
- Disable actions and Analyze when hand ended or all-in locked.

### Tests

- Flop required before flop action.
- Turn required before turn action.
- River required before river action.
- Check/check closes postflop street.
- Bet/call closes postflop street.
- Raise/call closes betting round.
- Illegal postflop raise too small.
- All-in call locks hand.
- Analyze rejected after all-in lock.
- River betting closed marks hand complete.
- Full legal hand replay from preflop to river decision point.

## Explicitly NOT Included Yet

- No final Analyze endpoint returning analysis.
- No baseline range display.
- No Range LLM.
- No equity/math.
- No Decision LLM.

## Blocked By

- Phase 2

---

# Phase 4 — First Real Analyze: Range Analysis with Baseline Fallback

**Label:** HITL

## User can DO / SEE

A user can build a legal hand to a Hero decision point and click **Analyze** manually.

The app returns the first real poker analysis section: villain range analysis.

The user sees:

- Hand State
  - current street
  - pot
  - bet to call
  - effective stack
  - SPR
  - current actor
  - last aggressor
- Built-in baseline range context used by the range system
- Range LLM output:
  - estimated villain range
  - confidence
  - overall tendency
  - value/draw/bluff categories
  - coarse weights
  - reasoning
- Fallback warning if the LLM fails or returns invalid output

If the Range LLM fails, the user still gets a meaningful fallback range instead of an error-only result.

## Layers Touched

### Data model

- Add `RangeCategory`.
- Add `RangeAnalysis`.
- Add baseline range selection result.
- Finalize analysis eligibility fields:
  - `analyze_allowed`
  - `disabled_reason`

### Backend

- Add built-in heads-up preflop baseline ranges:
  - BTN/SB open range
  - BB defend vs BTN/SB open
  - BB 3-bet range
  - BTN/SB call vs BB 3-bet
  - BTN/SB 4-bet range
  - BB call vs 4-bet
- Add helper to select relevant baseline based on preflop line.
- Add `pokerbot/range_advisor.py`.
- Build Range LLM prompt with:
  - full timeline
  - board
  - hero cards
  - positions
  - villain profile
  - derived hand state
  - baseline range
  - dead cards
  - supported range syntax
  - strict JSON instruction
- Parse and validate Range LLM JSON.
- Validate `estimated_range` with `range_parser.py`.
- Implement fallback on:
  - timeout
  - API error
  - invalid JSON
  - unparseable range
- Do not make a third repair LLM call.

### API

Add/finalize:

```http
POST /api/analyze_full_hand
```

Response includes:

```json
{
  "success": true,
  "hand_state": {...},
  "baseline_range": {
    "name": "BB defend vs BTN/SB open",
    "range": "..."
  },
  "range_analysis": {
    "estimated_range": "...",
    "confidence": "MEDIUM",
    "overall_tendency": "value-heavy",
    "categories": {...},
    "reasoning": "...",
    "fallback_used": false
  },
  "metrics": null,
  "decision": null
}
```

Backend rejects Analyze if:

- Hero is not current actor
- awaiting board cards
- hand ended
- all-in locked
- invalid timeline

### Frontend

- Add manual Analyze button.
- Gate Analyze button using current state.
- Show disabled reason when unavailable.
- On click, call `/api/analyze_full_hand`.
- Display Hand State result section.
- Display Baseline Range / Range Analysis section.
- Show loading state for range analysis.
- Show fallback warning visibly.

### Tests

- Analyze allowed at Hero decision point.
- Analyze rejected when villain is to act.
- Analyze rejected while awaiting board.
- Analyze rejected after fold.
- Analyze rejected after all-in lock.
- All baseline presets parse.
- Baseline selection for common preflop lines.
- Mock valid Range LLM response.
- Mock timeout fallback.
- Mock invalid JSON fallback.
- Mock unparseable range fallback.
- API returns range analysis.

## Explicitly NOT Included Yet

- No equity calculation.
- No pot odds / EV / MDF math section.
- No final Decision LLM recommendation.
- Category weights are display only.

## Blocked By

- Phase 3

## HITL Review Needed

- Check whether the Range LLM prompt returns parseable ranges often enough.
- Check whether displayed categories are understandable to a poker player.
- Check fallback wording does not imply false confidence.
- Check Analyze gating feels natural.

---

# Phase 5 — Analyze Adds Equity and Poker Math

**Label:** AFK

## User can DO / SEE

After clicking Analyze, the user now sees real poker math computed from the Range LLM’s `estimated_range` or fallback range.

The results include:

- equity vs estimated range
- pot odds
- EV call
- MDF
- outs
- SPR

Example:

```text
Math
Equity vs Estimated Range: 38.2%
Pot Odds: 25.0%
EV Call: +3.1bb
SPR: 5.9
MDF: 75.0%
Outs: 6
```

This is now useful even before the final Decision LLM is added: the player can compare equity to pot odds and inspect EV.

## Layers Touched

### Data model

- Add full-hand metrics serialization.
- Include metrics in `/api/analyze_full_hand` response.

### Backend

- Parse `range_analysis.estimated_range` with dead cards removed.
- Use existing `equity.py` to compute equity.
- Use existing `math_engine.py` or a wrapper to compute metrics from derived hand state.
- Use derived pot, bet to call, stacks, and street as source of truth.
- Ignore category weights for v1 equity.
- Ensure fallback range also produces parseable equity input.

### API

- `/api/analyze_full_hand` returns populated `metrics`.
- `decision` may still be null.

### Frontend

- Add Math section to full-hand results.
- Reuse existing metric-card styling where possible.
- Show clear labels that equity is against the estimated/fallback range.

### Tests

- Metrics use derived pot and bet-to-call.
- Equity uses `estimated_range`.
- Category weights ignored in v1.
- Full-hand API returns metrics with mocked Range LLM.
- Fallback range still allows metrics calculation.

## Explicitly NOT Included Yet

- No final Decision LLM recommendation.
- No weighted equity.
- No deterministic final fold/call/raise suggestion.

## Blocked By

- Phase 4

---

# Phase 6 — Complete End-to-End Decision Advisor

**Label:** HITL

## User can DO / SEE

A user can build a hand, click Analyze, and receive the complete end-to-end result:

1. Hand State
2. Range Analysis
3. Math
4. Final Decision

The final decision includes:

- `FOLD`, `CALL`, or `RAISE`
- confidence
- reasoning
- sensitivity note
- raise-to size and amount-to-add if raising

Example:

```text
Decision: CALL
Confidence: MEDIUM
Reasoning: Your equity exceeds pot odds, but villain's line is value-heavy...
Sensitivity: If villain's range is only sets/two-pair, this becomes a fold.
```

If the final Decision LLM times out, the user still sees hand state, range analysis, and math, with decision marked as `ERROR`.

## Layers Touched

### Data model

- Add full-hand `Decision` fields:
  - `action`
  - `raise_to_bb`
  - `amount_to_add_bb`
  - `confidence`
  - `reasoning`
  - `sensitivity_note`
  - `raw_response`

### Backend

- Update `advisor.py` or add a full-hand decision prompt path.
- Prompt includes:
  - full timeline
  - hand state
  - legal actions
  - range analysis JSON
  - fallback warning if used
  - metrics
- Instruct final LLM:
  - recommend exactly one action
  - base main decision on computed range/equity
  - may sensitivity-check range assumptions
  - may not silently replace the source-of-truth range
  - if raising, provide both raise-to and amount-to-add
- Parse final LLM output.
- Validate final action is legal where applicable.
- Handle timeout/API error as decision `ERROR` while preserving hand state/range/metrics.

### API

- `/api/analyze_full_hand` returns populated `decision`.

### Frontend

- Add Final Decision results section.
- Use existing badge styling for action.
- Display raise-to and amount-to-add when present.
- Display sensitivity note.
- Display decision timeout/error gracefully.

### Tests

- Mock fold/call/raise final responses.
- Parse raise response with both sizes.
- Decision timeout returns `ERROR` but preserves hand state/range/metrics.
- Full pipeline route test with mocked Range LLM and Decision LLM.

## Explicitly NOT Included Yet

- No weighted equity.
- No multiplayer.
- No tournament mode.
- No raw hand import.
- No review mode.

## Blocked By

- Phase 5

## HITL Review Needed

- Manually inspect quality of final decisions.
- Check whether sensitivity notes are useful but not too verbose.
- Check whether final model follows the “do not override range” instruction.
- Tune prompt/model/timeout if needed.

---

# Phase 7 — Full-Hand UI Replacement and UX Polish

**Label:** HITL

## User can DO / SEE

The old snapshot workflow is no longer the primary visible app. The user sees a polished full-hand workflow from page load:

- setup panel
- card picker
- action builder
- timeline
- gated Analyze button
- complete structured results

The app feels like a coherent full-hand advisor rather than a prototype layered on top of the old snapshot UI.

A real poker player can open the app and complete the intended v1 workflow without developer guidance.

## Layers Touched

### Data model

- No major new model required unless polish reveals gaps.

### Backend

- Keep old `/api/analyze` only for compatibility/tests if desired.
- Ensure `/api/analyze_full_hand` is the primary route used by frontend.
- Harden backend error messages discovered during manual UI review.

### API

- Confirm final response schema is stable.
- Add any missing UI-facing fields needed for polished rendering.

### Frontend

- Remove/hide old snapshot fields:
  - manual pot
  - manual bet to call
  - manual current stack inputs
  - manual villain range from main flow
- Improve setup flow.
- Improve board-entry prompts.
- Improve timeline readability.
- Improve disabled states and error messages.
- Improve loading states:
  - range analysis
  - equity/math
  - final decision
- Improve responsive behavior.
- Preserve dark aesthetic.
- Add clear/reset behavior for full-hand state.

### Tests

- Update app route tests for new UI text.
- Ensure old tests are updated intentionally.
- Add regression tests for `/` serving full-hand UI.
- Add mocked full-pipeline UI/API route tests.

## Explicitly NOT Included Yet

- No new poker logic beyond completed full-hand flow.
- No multiplayer.
- No tournament mode.
- No raw hand-history import.
- No weighted equity.

## Blocked By

- Phase 6

## HITL Review Needed

- Manual browser review.
- UX flow review.
- Visual polish review.
- Confirm that a real user can build and analyze a hand without developer knowledge.

## Documentation and Hardening Checklist

Complete as part of this phase, not as a separate vertical slice:

- Update `README.md`.
- Document heads-up cash-only scope.
- Document big-blind units.
- Document action amount semantics.
- Document raise-to helper.
- Document two-call LLM pipeline.
- Document fallback behavior.
- Add example hand walkthrough.
- Add full mocked integration tests.
- Add optional real LLM integration tests marked with `integration`.
- Tune prompts.
- Tune model choices.
- Tune timeouts.
- Tune equity simulation counts.
- Confirm offline test suite passes.
- Confirm documented demo hands work manually.

---

# Summary Table

| Phase | Label | Demoable User Outcome | Blocked By |
|---|---|---|---|
| 1 | AFK | Enter setup/cards and see auto-blinds, pot, stacks, first actor, and legal first actions | None |
| 2 | AFK | Build a strictly legal preflop action sequence with timeline, raise-to helper, pot/stacks, and validation | 1 |
| 3 | AFK | Build a complete legal hand from preflop through river with board prompts, postflop actions, raises, all-ins, and street advancement | 2 |
| 4 | HITL | Click Analyze at a Hero decision point and see hand state plus Range LLM analysis with built-in baseline fallback | 3 |
| 5 | AFK | Analyze shows equity and poker math computed from the estimated/fallback range | 4 |
| 6 | HITL | Analyze shows complete final LLM decision with reasoning, confidence, sensitivity, and raise sizing | 5 |
| 7 | HITL | Full snapshot UI is replaced by a polished full-hand advisor, with docs/tests/hardening completed | 6 |
