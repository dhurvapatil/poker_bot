# Implementation Issues — Full-Hand PokerBot Advisor

This file breaks `PRD.md` into implementation-ready issues. Issues are ordered by dependency and grouped into milestones.

---

## Milestone 1 — Hand State Engine

### Issue 1: Add `pokerbot/hand_state.py` data models

**Goal**
Create the foundational full-hand data model for heads-up cash games in big blinds.

**Tasks**
- Add `pokerbot/hand_state.py`.
- Define dataclasses or typed structures for:
  - `HandSetup`
  - `PlayerState`
  - `HandAction`
  - `BoardState`
  - `DerivedHandState`
  - optional `HandReplayResult`
- Support actors:
  - `hero`
  - `villain`
- Support positions:
  - `BTN` / `SB`
  - `BB`
- Support action types:
  - `fold`
  - `check`
  - `call`
  - `bet`
  - `raise`
- Represent all action amounts as incremental `amount_added` in bb.
- Include optional fields:
  - `all_in`
  - `input_mode`
  - `input_amount`

**Acceptance Criteria**
- Data models can represent setup, board, actions, and derived state.
- All stack/bet amounts are big-blind floats.
- No tournament/ante/multiplayer fields are required for v1.

---

### Issue 2: Implement setup validation and automatic blind posting

**Goal**
Validate heads-up setup and auto-post blinds before replaying actions.

**Tasks**
- Validate Hero stack > 0.
- Validate Villain stack > 0.
- Validate Hero position is `BTN`, `SB`, or `BB`.
- Normalize `BTN` and `SB` as the same heads-up small-blind/button seat.
- Validate villain profile is one of:
  - `Unknown`
  - `Nit`
  - `Tight Passive`
  - `Tight Aggressive`
  - `Loose Passive / Calling Station`
  - `Loose Aggressive`
  - `Maniac`
  - `Solid Reg`
  - `Weak Recreational`
- Auto-post blinds:
  - SB = `0.5bb`
  - BB = `1bb`
- If Hero is BTN/SB:
  - Hero posts `0.5bb`
  - Villain posts `1bb`
  - Hero acts first preflop
- If Hero is BB:
  - Villain posts `0.5bb`
  - Hero posts `1bb`
  - Villain acts first preflop

**Acceptance Criteria**
- Correct stacks and pot after blind posting.
- Correct preflop actor for both Hero BTN/SB and Hero BB.
- Invalid stacks/positions/profiles raise clear validation errors.

**Tests**
- `test_auto_post_blinds_hero_btn`
- `test_auto_post_blinds_hero_bb`
- `test_invalid_stack_rejected`
- `test_invalid_position_rejected`
- `test_invalid_villain_profile_rejected`

---

### Issue 3: Implement action replay with pot, stack, and contribution tracking

**Goal**
Replay the full action timeline and derive pot/stacks/contributions.

**Tasks**
- Track total pot in bb.
- Track each player’s remaining stack.
- Track each player’s current street contribution.
- Track current bet amount on each street.
- Track last aggressor.
- Apply `amount_added` for `bet` and `raise`.
- Compute `call` amount automatically from current street contributions.
- For `call`, allow omitted `amount_added`; engine derives it.
- For `check` and `fold`, no amount should be added.
- Prevent action amount from exceeding remaining stack unless represented as all-in exactly.

**Acceptance Criteria**
- Legal actions update pot and stacks correctly.
- Calls add exactly the amount needed to match the current bet.
- Street contributions are tracked separately from total pot.

**Tests**
- `test_preflop_raise_call_pot_and_stacks`
- `test_postflop_bet_call_pot_and_stacks`
- `test_call_amount_calculated_from_contributions`
- `test_action_amount_cannot_exceed_stack`
- `test_last_aggressor_updates_on_bet_raise`

---

### Issue 4: Implement strict legal-action validation

**Goal**
Reject impossible betting sequences during backend replay.

**Tasks**
- Enforce correct actor turn order.
- `check` legal only when not facing a bet.
- `call` legal only when facing a bet.
- `bet` legal only when no bet exists on the street.
- `raise` legal only when facing an existing bet/raise.
- Validate minimum raise size unless all-in exception applies.
- Reject zero/negative `amount_added` for bet/raise.
- Reject amount-added actions for check/fold.
- End hand immediately on fold.
- Prevent further actions after hand ended.

**Acceptance Criteria**
- Invalid timelines produce clear errors.
- Backend never trusts frontend gating.

**Tests**
- `test_illegal_call_when_no_bet`
- `test_illegal_check_facing_bet`
- `test_illegal_bet_facing_bet`
- `test_illegal_raise_without_bet`
- `test_illegal_raise_too_small`
- `test_illegal_wrong_actor`
- `test_no_actions_after_fold`

---

### Issue 5: Implement street advancement and board-state validation

**Goal**
Auto-advance betting state while requiring valid board cards before next-street actions.

**Tasks**
- Support streets:
  - `preflop`
  - `flop`
  - `turn`
  - `river`
- Board requirements:
  - preflop: 0 cards
  - flop: exactly 3 cards
  - turn: exactly 1 new card after flop
  - river: exactly 1 new card after turn
- Detect street closure:
  - preflop raise/call closes once both players have matched action
  - postflop check/check closes street
  - postflop bet/call closes street
  - raise/call closes street if no further action remains
- When street closes, set state to awaiting next board card unless river complete.
- Reset street contributions when moving to a new street.

**Acceptance Criteria**
- Engine advances to awaiting flop/turn/river correctly.
- Engine rejects actions on a street before required board cards are present.
- River betting completion marks hand complete.

**Tests**
- `test_preflop_closed_awaits_flop`
- `test_flop_required_before_flop_action`
- `test_check_check_closes_flop`
- `test_bet_call_closes_flop`
- `test_turn_required_before_turn_action`
- `test_river_betting_complete_marks_hand_complete`

---

### Issue 6: Implement all-in lock and analyze eligibility

**Goal**
Detect when no further decision exists and determine if manual analysis is allowed.

**Tasks**
- Detect all-in locked state when both active players are all-in or no further betting can occur.
- Disable/reject analysis when all-in locked.
- Disable/reject analysis after fold.
- Disable/reject analysis after hand complete.
- Analyze allowed only when:
  - Hero has a legal decision,
  - current actor is Hero,
  - board state is valid,
  - hand not ended,
  - hand not all-in locked.
- Provide `disabled_reason` when analysis is not allowed.

**Acceptance Criteria**
- Derived state includes `analyze_allowed` and `disabled_reason`.
- Backend rejects analyze requests when not allowed.

**Tests**
- `test_analyze_allowed_when_hero_to_act`
- `test_analyze_rejected_when_villain_to_act`
- `test_analyze_rejected_awaiting_board`
- `test_analyze_rejected_after_fold`
- `test_analyze_rejected_all_in_locked`

---

## Milestone 2 — Full-Hand API Without LLM

### Issue 7: Add `/api/analyze_full_hand` route with replay validation only

**Goal**
Add the new API endpoint and return derived hand state before integrating LLMs.

**Tasks**
- Add `POST /api/analyze_full_hand` in `pokerbot/app.py`.
- Accept request shape:
  - `setup`
  - `board`
  - `actions`
- Parse hero hole cards and board cards.
- Validate duplicate/dead-card overlap.
- Replay hand with `hand_state.py`.
- Validate `analyze_allowed`.
- Return `hand_state` JSON.
- Return structured errors for invalid timelines.

**Acceptance Criteria**
- Valid analyze-ready hand returns `success: true` and derived hand state.
- Invalid hand returns `success: false` and a clear error.
- LLMs are not called in this issue.

**Tests**
- `test_analyze_full_hand_valid_preflop_state_only`
- `test_analyze_full_hand_valid_flop_state_only`
- `test_analyze_full_hand_invalid_action_returns_400`
- `test_analyze_full_hand_not_hero_turn_returns_400`
- `test_analyze_full_hand_duplicate_cards_returns_400`

---

## Milestone 3 — Preflop Baselines

### Issue 8: Add simple heads-up preflop range presets

**Goal**
Provide baseline ranges for Range LLM context and fallback behavior.

**Tasks**
- Add preflop preset constants, likely in `pokerbot/constants.py` or new `pokerbot/preflop_ranges.py`.
- Include broad presets:
  - BTN/SB open range
  - BB defend vs BTN/SB open
  - BB 3-bet range
  - BTN/SB call vs BB 3-bet
  - BTN/SB 4-bet range
  - BB call vs 4-bet
- Add helper to select relevant baseline based on preflop line.
- Ensure all preset ranges parse with existing `range_parser.py`.

**Acceptance Criteria**
- Every preset range is parser-compatible.
- Fallback range selector returns a reasonable broad range.

**Tests**
- `test_all_preflop_presets_parse`
- `test_select_btn_open_baseline`
- `test_select_bb_defend_baseline`
- `test_select_fallback_baseline_for_unknown_line`

---

## Milestone 4 — Range Advisor

### Issue 9: Add `pokerbot/range_advisor.py` with `RangeAnalysis` model

**Goal**
Create structured range-analysis output and validation utilities.

**Tasks**
- Add `RangeCategory` dataclass.
- Add `RangeAnalysis` dataclass with:
  - `estimated_range`
  - `confidence`
  - `overall_tendency`
  - `categories`
  - `reasoning`
  - `fallback_used`
  - `raw_response`
- Add validation for:
  - confidence: `LOW|MEDIUM|HIGH`
  - tendency: `value-heavy|balanced|draw-heavy|bluff-heavy|uncertain`
  - weights: `HIGH|MEDIUM|LOW|NONE`
- Validate `estimated_range` using `range_parser.py` and dead cards.

**Acceptance Criteria**
- Valid JSON converts into `RangeAnalysis`.
- Invalid schema can be detected.

**Tests**
- `test_parse_valid_range_analysis_json`
- `test_invalid_confidence_rejected_or_fallback`
- `test_invalid_tendency_rejected_or_fallback`
- `test_invalid_weight_rejected_or_normalized`
- `test_estimated_range_must_parse`

---

### Issue 10: Implement Range LLM prompt and API call

**Goal**
Call a fast LLM to estimate villain's current range from the full hand.

**Tasks**
- Build Range LLM system prompt requiring strict JSON only.
- Include supported range syntax examples.
- Include warning not to output descriptive-only ranges like “sets” unless encoded parseably.
- Include:
  - hero cards
  - board cards
  - positions
  - villain profile
  - full action timeline
  - derived hand state
  - built-in preflop baseline
  - dead cards
- Use fast model settings:
  - timeout `8–10s`
  - max tokens `500–700`
  - temperature `0.2`
- Parse raw LLM content as JSON.

**Acceptance Criteria**
- Prompt contains all required context.
- LLM call returns parsed `RangeAnalysis` when mocked response is valid.

**Tests**
- `test_range_prompt_contains_timeline`
- `test_range_prompt_contains_baseline`
- `test_range_prompt_requires_json`
- `test_range_llm_valid_mock_response`

---

### Issue 11: Implement Range LLM fallback behavior

**Goal**
Continue analysis safely when Range LLM fails.

**Tasks**
- On timeout, return fallback range analysis.
- On HTTP/API error, return fallback range analysis.
- On invalid JSON, return fallback range analysis.
- On unparseable `estimated_range`, return fallback range analysis.
- Fallback must set:
  - `confidence = LOW`
  - `overall_tendency = uncertain`
  - `fallback_used = true`
  - clear reasoning string
- Do not make a repair LLM call.

**Acceptance Criteria**
- Range LLM failures do not fail the entire analysis.
- Fallback output is valid and parseable.

**Tests**
- `test_range_timeout_uses_fallback`
- `test_range_api_error_uses_fallback`
- `test_range_invalid_json_uses_fallback`
- `test_range_unparseable_range_uses_fallback`
- `test_range_fallback_marks_low_confidence`

---

## Milestone 5 — Equity and Metrics Integration

### Issue 12: Compute metrics from derived full-hand state

**Goal**
Use the replayed hand state as the source of truth for poker math.

**Tasks**
- Adapt or wrap existing `math_engine.py` to accept derived:
  - pot bb
  - bet to call bb
  - hero stack bb
  - villain stack bb
  - current street
- Parse `range_analysis.estimated_range` with dead cards removed.
- Compute equity using `equity.py`.
- Compute:
  - pot odds
  - SPR
  - MDF
  - outs
  - EV call
- Ignore category weights for v1 equity.

**Acceptance Criteria**
- Metrics use derived pot/stacks, not user-entered snapshot fields.
- Equity uses only `estimated_range`.
- River uses exhaustive evaluation where existing equity module supports it.

**Tests**
- `test_metrics_use_derived_pot_and_bet_to_call`
- `test_equity_uses_estimated_range`
- `test_category_weights_ignored_for_v1_equity`
- `test_full_hand_metrics_flop_decision`

---

## Milestone 6 — Final Decision Advisor

### Issue 13: Update `advisor.py` for full-hand Decision LLM prompt

**Goal**
Generate final decision using full timeline, range JSON, and computed metrics.

**Tasks**
- Add full-hand decision prompt builder.
- Include:
  - full timeline
  - hero cards
  - board cards
  - positions
  - villain profile
  - derived hand state
  - legal actions
  - full range analysis JSON
  - fallback warning if used
  - equity/math metrics
- Instruct LLM:
  - recommend exactly one action
  - base main action on computed range/equity
  - may sensitivity-check but cannot replace source-of-truth range
  - if raising, provide both raise-to and amount-to-add
- Use output format:
  - `REASONING`
  - `SENSITIVITY_NOTE`
  - `DECISION`
  - `RAISE_TO_BB`
  - `AMOUNT_TO_ADD_BB`
  - `CONFIDENCE`

**Acceptance Criteria**
- Prompt includes all required context.
- Mocked LLM responses parse correctly.

**Tests**
- `test_full_hand_decision_prompt_contains_timeline`
- `test_full_hand_decision_prompt_contains_range_json`
- `test_full_hand_decision_prompt_contains_metrics`
- `test_parse_full_hand_fold_response`
- `test_parse_full_hand_call_response`
- `test_parse_full_hand_raise_response_with_sizes`

---

### Issue 14: Implement Decision LLM timeout/error handling

**Goal**
Return math/range/hand state even if final advisor fails.

**Tasks**
- On Decision LLM timeout, return decision:
  - `action = ERROR`
  - `reasoning = Final advisor timed out`
  - `confidence = N/A`
- On API error, return decision `ERROR` with clear message.
- Do not invent deterministic final action.

**Acceptance Criteria**
- Decision LLM failure does not erase hand state, range analysis, or metrics.

**Tests**
- `test_decision_timeout_returns_error_decision`
- `test_decision_api_error_returns_error_decision`
- `test_decision_error_preserves_metrics_and_range`

---

## Milestone 7 — Full Pipeline API

### Issue 15: Orchestrate `/api/analyze_full_hand` full two-call pipeline

**Goal**
Connect hand-state replay, range LLM, math, and final Decision LLM.

**Tasks**
- In `/api/analyze_full_hand`:
  1. Parse request.
  2. Validate cards/setup/actions.
  3. Replay hand state.
  4. Validate `analyze_allowed`.
  5. Select built-in preflop baseline.
  6. Call Range LLM or fallback.
  7. Parse estimated range.
  8. Compute equity and metrics.
  9. Call Decision LLM.
  10. Return structured response.
- Response sections:
  - `success`
  - `hand_state`
  - `range_analysis`
  - `metrics`
  - `decision`

**Acceptance Criteria**
- Valid decision point returns complete response.
- Range fallback still allows final decision.
- Decision timeout returns decision error but response success.
- Invalid hand state returns error.

**Tests**
- `test_full_pipeline_valid_preflop_decision_mocked`
- `test_full_pipeline_valid_flop_decision_mocked`
- `test_full_pipeline_range_fallback_still_succeeds`
- `test_full_pipeline_decision_timeout_returns_error_decision`
- `test_full_pipeline_invalid_analyze_state_rejected`

---

## Milestone 8 — Frontend Replacement

### Issue 16: Replace snapshot form with setup panel and full-hand state model

**Goal**
Start frontend migration from snapshot input to full-hand builder while preserving dark aesthetic.

**Tasks**
- Update `templates/index.html` layout.
- Add setup panel fields:
  - Hero position
  - Hero stack bb
  - Villain stack bb
  - Villain profile
  - Hero hole card picker
  - auto-blinds display
- Remove/hide old snapshot fields:
  - manual pot
  - manual bet to call
  - manual stacks as current snapshot
  - manual villain range field from main flow
- Keep card picker visual style.

**Acceptance Criteria**
- User can enter setup data and select hero cards.
- UI still matches current dark PokerBot aesthetic.

---

### Issue 17: Add frontend street/action builder with local state

**Goal**
Allow user to manually build actions street by street in the browser.

**Tasks**
- Add frontend state object containing:
  - setup
  - board
  - actions
  - current derived frontend state
- Add current street indicator.
- Add board card picker only when board cards are needed.
- Add action timeline display.
- Add action buttons:
  - check
  - call
  - fold
  - bet
  - raise
- Add amount input in bb.
- Add all-in toggle.

**Acceptance Criteria**
- User can build a visible action timeline.
- Timeline stores actions in API-compatible shape.

---

### Issue 18: Add frontend legal-action gating and raise-to helper

**Goal**
Prevent impossible timelines in the UI.

**Tasks**
- Implement frontend state replay or lightweight legal-action derivation.
- Enable only legal actions.
- Show disabled reasons where useful.
- Add raise-to helper that converts total size to incremental `amount_added`.
- Ensure frontend actions use `amount_added` as source of truth.
- Include optional `input_mode` and `input_amount`.

**Acceptance Criteria**
- User cannot click impossible action buttons in normal UI flow.
- Raise-to helper produces correct incremental amount.
- Backend remains final validator.

---

### Issue 19: Add manual gated Analyze button and API submission

**Goal**
Submit complete hand to backend only when analysis is allowed.

**Tasks**
- Add Analyze button.
- Gate button when:
  - not Hero turn
  - awaiting board
  - invalid board/cards
  - hand ended
  - all-in locked
- Show disabled reason.
- On click, POST to `/api/analyze_full_hand`.
- Show loading state.
- Display backend validation errors.

**Acceptance Criteria**
- No auto-analysis occurs.
- Analyze sends setup, board, and actions only on click.
- Errors are readable.

---

### Issue 20: Add structured full-hand results panel

**Goal**
Display complete full-hand analysis output.

**Tasks**
- Add Hand State section:
  - street
  - pot bb
  - bet to call bb
  - effective stack bb
  - SPR
  - current actor
  - last aggressor
  - hero/villain stack
- Add Range Analysis section:
  - estimated range
  - confidence
  - overall tendency
  - value/draw/bluff categories
  - weights
  - reasoning
  - fallback warning
- Add Math section:
  - equity
  - pot odds
  - EV call
  - MDF
  - outs
  - SPR
- Add Final Decision section:
  - decision badge
  - confidence
  - reasoning
  - sensitivity note
  - raise-to and amount-to-add if applicable

**Acceptance Criteria**
- Results are clearly separated into four sections.
- Fallback warnings are visible.
- Decision badge uses existing color language where possible.

---

## Milestone 9 — Documentation and Polish

### Issue 21: Update README for full-hand workflow

**Goal**
Document the new user flow and API.

**Tasks**
- Update README feature list.
- Explain full-hand builder.
- Explain heads-up cash-only v1 scope.
- Explain big-blind units.
- Explain two-call LLM pipeline.
- Document `/api/analyze_full_hand` request/response.
- Note that old snapshot flow is deprecated/hidden.

**Acceptance Criteria**
- README accurately describes current product.

---

### Issue 22: Add integration tests for full-hand flow

**Goal**
Verify complete behavior with mocked LLMs and optionally real integration.

**Tasks**
- Add mocked full pipeline tests.
- Add optional integration marker for real LLM calls.
- Ensure existing tests remain green or are intentionally updated.

**Acceptance Criteria**
- Unit and mocked route tests pass offline.
- Integration tests are marked and skipped unless configured.

---

## Recommended Build Order

1. Issue 1 — Data models
2. Issue 2 — Setup validation/blinds
3. Issue 3 — Action replay
4. Issue 4 — Strict validation
5. Issue 5 — Street advancement
6. Issue 6 — Analyze eligibility/all-in lock
7. Issue 7 — API state-only route
8. Issue 8 — Preflop baselines
9. Issue 9 — RangeAnalysis model
10. Issue 10 — Range LLM prompt/call
11. Issue 11 — Range fallback
12. Issue 12 — Metrics integration
13. Issue 13 — Decision advisor prompt/parser
14. Issue 14 — Decision error handling
15. Issue 15 — Full pipeline orchestration
16. Issue 16 — Setup UI
17. Issue 17 — Action builder UI
18. Issue 18 — Frontend gating/raise helper
19. Issue 19 — Analyze submission
20. Issue 20 — Results panel
21. Issue 21 — README
22. Issue 22 — Integration tests
