# PRD — Full-Hand PokerBot Advisor

## 1. Product Overview

### Product name

PokerBot Full-Hand Advisor

### Current product state

PokerBot currently operates as a **single-snapshot Texas Hold'em advisor**. The user enters the current hand state manually:

- Hero hole cards
- Current board
- Pot size
- Bet to call
- Hero stack
- Opponent stack
- Position
- Villain range

The system then computes poker metrics and sends the snapshot to an LLM for a final `FOLD`, `CALL`, or `RAISE` recommendation.

### New product direction

Upgrade PokerBot into a **heads-up cash-game full-hand advisor** that understands the entire action sequence from preflop to the current decision point.

Instead of manually entering the current pot and bet state, the user will build the hand street by street. The app will derive pot, stacks, betting state, SPR, bet to call, current actor, and action legality from the timeline.

At the decision point, the app will use a two-step LLM pipeline:

```text
Full Hand Timeline
→ Strict State Engine
→ Built-in Preflop Baseline
→ Range LLM JSON
→ Range Validation/Fallback
→ Equity + Math
→ Decision LLM
→ Structured Results
```

---

## 2. Goals

### Primary goals

1. Replace snapshot analysis with full-hand timeline analysis.
2. Support heads-up cash games in big blinds.
3. Automatically derive pot, stacks, SPR, bet to call, and legal actions from the timeline.
4. Strictly validate action sequences in frontend and backend.
5. Use a Range LLM to estimate villain's current range from the full hand history.
6. Compute equity and poker math against the validated estimated range.
7. Use a Decision LLM to recommend exactly one action: `FOLD`, `CALL`, or `RAISE`.
8. Keep the UI aesthetically similar to the current dark card-picker interface.
9. Keep the system extensible for future multiplayer support.

### Secondary goals

1. Preserve existing poker math, equity, range parsing, and advisor modules as reusable building blocks.
2. Add a clean internal hand-state model that can later support multiplayer.
3. Avoid fake precision from LLM-generated exact numeric range weights.
4. Keep analysis latency near or below a ~20 second target for the two-call LLM pipeline.

---

## 3. Non-Goals / Out of Scope for v1

The following are explicitly out of scope for v1:

- Multiplayer hand analysis.
- Tournament mode.
- Antes.
- ICM or payout-pressure calculations.
- Raw hand-history import/parsing from poker sites.
- Session persistence.
- Known villain card/showdown review mode.
- Free-text villain notes.
- Weighted equity using LLM category weights.
- Equity-only reports after all-in lock.
- LLM calls after every action.
- Third LLM repair call for invalid range output.
- Detailed preflop range matrices by exact open size.

---

## 4. Target User

The target user is a poker player who wants decision support while reviewing or manually reconstructing heads-up No-Limit Hold'em cash-game hands.

The user wants the bot to understand not only the current board and pot, but also the betting line that led to the current decision.

---

## 5. Key User Stories

### US-1: Build a full heads-up hand

As a user, I want to enter my position, stack, villain stack, hero cards, board cards, and every action street by street so the bot understands how the hand developed.

### US-2: Derive pot and stacks automatically

As a user, I do not want to manually calculate pot, bet to call, or remaining stacks. I want the app to compute them from blinds and actions.

### US-3: Prevent illegal action entry

As a user, I want the UI to only allow legal actions so I do not accidentally create impossible hand histories.

### US-4: Analyze only when Hero has a decision

As a user, I want to click Analyze manually only when it is Hero's turn and there is a real decision to make.

### US-5: Understand villain range

As a user, I want the bot to estimate villain's current range based on the full betting line, villain profile, board, positions, and bet sizes.

### US-6: Receive a final poker recommendation

As a user, I want a final `FOLD`, `CALL`, or `RAISE` recommendation based on estimated range, equity, pot odds, EV, SPR, and the full action history.

### US-7: See reasoning and sensitivity

As a user, I want to see the range reasoning, math, final reasoning, and how sensitive the decision is to the range assumption.

---

## 6. Functional Requirements

## 6.1 Game Type and Units

### Requirements

- The product shall support heads-up cash games only in v1.
- All stack and bet values shall be entered and displayed in big blinds.
- The system shall not support antes in v1.
- The system shall not support tournament ICM in v1.

### Default blind structure

```text
Small blind = 0.5bb
Big blind = 1bb
```

---

## 6.2 Setup Panel

The setup panel shall collect:

- Hero position:
  - `BTN` / `SB`
  - `BB`
- Hero stack in bb.
- Villain stack in bb.
- Villain profile.
- Hero hole cards.

### Villain profiles

The villain profile dropdown shall include:

```text
Unknown
Nit
Tight Passive
Tight Aggressive
Loose Passive / Calling Station
Loose Aggressive
Maniac
Solid Reg
Weak Recreational
```

`Unknown` shall be the default profile.

### Validation

- Hero stack must be greater than 0.
- Villain stack must be greater than 0.
- Hero must select exactly 2 unique hole cards.
- Hero cards must not overlap with board cards.

---

## 6.3 Automatic Blind Posting

The backend state engine shall automatically post blinds.

### If Hero is BTN/SB

```text
Hero posts 0.5bb
Villain posts 1bb
Hero acts first preflop
```

### If Hero is BB

```text
Villain posts 0.5bb
Hero posts 1bb
Villain acts first preflop
```

Blind posts shall not be included as user-entered actions in the API request.

---

## 6.4 Action Model

### Supported action types

The system shall support the following action types:

```text
fold
check
call
bet
raise
```

### All-in flag

All-in shall be represented as an optional flag on a normal action:

```json
{
  "type": "raise",
  "amount_added": 73.5,
  "all_in": true
}
```

This flag may apply to:

- call
- bet
- raise

### Action amount source of truth

The internal source of truth shall be:

```json
"amount_added": <incremental bb added to the pot by this action>
```

The product shall not use “raise-to total” as the internal source of truth.

### Raise-to helper

The UI shall provide a helper for natural poker entry:

```text
Raise to 10bb
```

The UI shall convert this into `amount_added` based on the actor's current street contribution.

Optional audit fields may be included:

```json
{
  "input_mode": "raise_to",
  "input_amount": 10.0
}
```

The backend may validate these fields if present, but `amount_added` remains authoritative.

---

## 6.5 Hand Timeline

The UI shall allow the user to build a street-by-street timeline.

### Streets

Supported streets:

```text
preflop
flop
turn
river
```

### Board entry requirements

- Preflop: no board cards.
- Flop: exactly 3 board cards.
- Turn: exactly 1 new turn card after flop.
- River: exactly 1 new river card after turn.

The API request may group board cards by street:

```json
{
  "board": {
    "flop": ["Ks", "9h", "4c"],
    "turn": ["2h"],
    "river": []
  }
}
```

---

## 6.6 Street Advancement

The system shall auto-advance betting state when a betting round closes.

Flow:

```text
Preflop betting closed
→ await flop cards

Flop cards entered
→ flop actions enabled

Flop betting closed
→ await turn card

Turn card entered
→ turn actions enabled

Turn betting closed
→ await river card

River card entered
→ river actions enabled

River betting closed
→ hand complete
```

The system shall not auto-analyze. Analyze remains manual.

---

## 6.7 Strict Action Validation

### Frontend validation

The frontend shall show or enable only legal actions for the current state.

### Backend validation

The backend shall replay the full action sequence and validate it regardless of frontend gating.

### The hand-state engine shall validate:

- Correct actor acts in turn.
- Check is legal only when not facing a bet.
- Call is legal only when facing a bet.
- Bet is legal only when no bet exists on the current street.
- Raise is legal only when facing an existing bet or raise.
- Raise amount meets minimum raise requirements unless all-in exceptions apply.
- Action amount does not exceed actor's remaining stack.
- Fold ends the hand.
- All-in lock prevents further decision analysis.
- Street closes correctly after checks or calls.
- Board requirements are satisfied before next-street actions.

### Examples of invalid sequences

```text
Hero checks → Villain calls
```

Invalid because no bet exists.

```text
Hero bets 10 → Villain checks
```

Invalid because Villain faces a bet.

```text
Hero raises → Villain raises too small
```

Invalid unless it is a permitted all-in exception.

---

## 6.8 Derived Hand State

The backend shall derive the following from setup, blinds, board, and actions:

- Current street.
- Pot in bb.
- Hero remaining stack in bb.
- Villain remaining stack in bb.
- Effective stack in bb.
- SPR.
- Current actor.
- Last aggressor.
- Current street contributions.
- Current bet.
- Bet to call.
- Legal actions.
- Minimum raise.
- Whether awaiting board cards.
- Whether hand ended by fold.
- Whether hand is all-in locked.
- Whether river betting is complete.
- Whether Analyze is allowed.
- If Analyze is not allowed, disabled reason.

---

## 6.9 Analyze Button

The UI shall include a manual Analyze button.

The Analyze button shall be enabled only when:

- Hero has exactly 2 hole cards.
- The board state is valid for the current street.
- It is Hero's turn to act.
- The hand has not ended by fold.
- The hand is not all-in locked.
- A real legal decision exists.

If disabled, the UI shall show a reason, such as:

```text
Waiting for villain action
Enter flop cards
Hand already ended
No decision available: all players are all-in
Invalid board state
```

The backend shall also enforce these rules and reject invalid Analyze requests.

---

## 6.10 All-In / No Further Decisions

If all remaining players are all-in before the river, v1 shall stop decision analysis.

The Analyze button shall be disabled.

The backend shall reject analyze requests in an all-in locked state.

Equity-only all-in reporting is out of scope for v1.

---

## 6.11 Range Analysis LLM

At the decision point, the backend shall call a Range LLM before computing equity.

### Purpose

The Range LLM shall:

- Interpret villain's line.
- Use villain profile.
- Use board texture.
- Use positions and bet sizes.
- Use built-in preflop baseline context.
- Estimate villain's current range.
- Categorize the range.
- Return strict JSON.

### Model strategy

Use a fast/cheap model.

Recommended settings:

```text
timeout: 8–10 seconds
max_tokens: 500–700
temperature: 0.2
response style: strict JSON only
```

### Required Range LLM JSON schema

```json
{
  "estimated_range": "TT+, AQs+, KQs, QJs, JTs",
  "confidence": "LOW|MEDIUM|HIGH",
  "overall_tendency": "value-heavy|balanced|draw-heavy|bluff-heavy|uncertain",
  "categories": {
    "value": {
      "range": "99,44,22,K9s",
      "weight": "HIGH|MEDIUM|LOW|NONE",
      "reasoning": "Why these hands are likely"
    },
    "draws": {
      "range": "QhJh,JhTh,AhQh",
      "weight": "HIGH|MEDIUM|LOW|NONE",
      "reasoning": "Why draws are present"
    },
    "bluffs": {
      "range": "AQo,AJo",
      "weight": "HIGH|MEDIUM|LOW|NONE",
      "reasoning": "Why bluffs are present"
    }
  },
  "reasoning": "Short explanation of how villain's line shaped the range",
  "fallback_used": false
}
```

### Required categories

The primary categories are:

- value
- draws
- bluffs

Optional future/display categories may include:

- medium_strength
- traps

### Weight behavior

Weights shall be coarse labels only:

```text
HIGH
MEDIUM
LOW
NONE
```

The system shall not ask the LLM for precise decimal combo frequencies in v1.

---

## 6.12 Range Validation and Fallback

The backend shall validate Range LLM output.

### Validation rules

The backend shall verify:

- Output is valid JSON.
- `estimated_range` exists.
- `estimated_range` parses successfully using the range parser.
- `confidence` is one of `LOW`, `MEDIUM`, `HIGH`.
- `overall_tendency` is one of:
  - `value-heavy`
  - `balanced`
  - `draw-heavy`
  - `bluff-heavy`
  - `uncertain`
- Category weights, if present, are one of:
  - `HIGH`
  - `MEDIUM`
  - `LOW`
  - `NONE`

Invalid category ranges shall not necessarily fail the whole analysis if `estimated_range` is valid.

### Invalid or timeout behavior

If the Range LLM:

- times out,
- returns invalid JSON,
- omits required fields,
- returns an unparseable `estimated_range`,

then the backend shall not make a repair LLM call in v1.

Instead, it shall use a fallback range and continue.

Fallback structure:

```json
{
  "estimated_range": "<broad fallback range>",
  "confidence": "LOW",
  "overall_tendency": "uncertain",
  "categories": {},
  "reasoning": "Range LLM failed or returned invalid output; using broad preflop-derived fallback.",
  "fallback_used": true
}
```

---

## 6.13 Built-In Preflop Ranges

The system shall include simple heads-up preflop baseline ranges.

Recommended presets:

```text
BTN/SB open range
BB defend vs BTN/SB open
BB 3-bet range
BTN/SB call vs BB 3-bet
BTN/SB 4-bet range
BB call vs 4-bet
```

These ranges shall be used:

- as baseline context for the Range LLM,
- as fallback if the Range LLM fails,
- as broad initial villain range assumptions.

Detailed size-specific matrices are out of scope for v1.

---

## 6.14 Equity and Math

After range analysis, the backend shall compute equity and poker metrics.

### Equity source range

v1 shall compute equity using only:

```text
range_analysis.estimated_range
```

Category weights shall be ignored for equity in v1.

### Metrics to compute

The backend shall compute:

- equity percentage vs estimated villain range,
- pot odds percentage,
- SPR,
- MDF,
- outs,
- EV of call.

### Simulation counts

Recommended adaptive simulation counts:

```text
preflop: 8,000–10,000
flop: 10,000
turn: 12,000
river: exhaustive evaluation
```

If latency is problematic, reduce default simulations to ~5,000 and add high-accuracy mode later.

---

## 6.15 Decision LLM

After equity and math calculation, the backend shall call a Decision LLM.

### Purpose

The Decision LLM shall produce one final recommendation:

```text
FOLD
CALL
RAISE
```

### Model strategy

Use a stronger reasoning model than the Range LLM.

Recommended settings:

```text
timeout: 12–15 seconds
max_tokens: 900–1200
temperature: 0.3
```

### Context sent to Decision LLM

The prompt shall include:

- full hand timeline,
- current street,
- hero cards,
- board cards,
- positions,
- villain profile,
- derived hand state,
- legal actions,
- full range analysis JSON,
- fallback warning if used,
- equity,
- pot odds,
- EV call,
- MDF,
- SPR,
- outs.

### Range disagreement rule

The Decision LLM may critique or sensitivity-check the range assumptions, but the main recommendation must be based on the provided computed range/equity.

Allowed:

```text
Using the estimated range, this is a call. If villain is significantly tighter, folding becomes better.
```

Not allowed:

```text
I ignore the provided range and assume villain only has sets.
```

### Output format

Recommended output format:

```text
REASONING:
<step-by-step reasoning>

SENSITIVITY_NOTE:
<how decision changes if range assumptions are wrong, or N/A>

DECISION: <FOLD|CALL|RAISE>
RAISE_TO_BB: <number or N/A>
AMOUNT_TO_ADD_BB: <number or N/A>
CONFIDENCE: <LOW|MEDIUM|HIGH>
```

### Raise sizing

If action is `RAISE`, the final result shall display both:

- total raise-to size,
- incremental amount to add.

Example:

```text
RAISE
Raise to: 18bb total
Amount to add: 12bb
```

---

## 6.16 Decision LLM Timeout

If the Decision LLM times out, the backend shall still return:

- hand state,
- range analysis,
- math metrics.

The decision object shall indicate an error:

```json
{
  "action": "ERROR",
  "reasoning": "Final advisor timed out",
  "confidence": "N/A",
  "raise_size": "N/A"
}
```

The system shall not silently invent a deterministic final poker action.

---

## 7. User Experience Requirements

## 7.1 UI Style

The new UI shall replace the old snapshot form but preserve the existing aesthetic:

- dark theme,
- polished card picker,
- modern panels,
- clear decision badge,
- readable results,
- visually consistent with current PokerBot styling.

---

## 7.2 Layout

The UI should contain four main sections.

### 1. Setup Panel

Contains:

- Hero position selector.
- Hero stack bb input.
- Villain stack bb input.
- Villain profile dropdown.
- Hero hole card picker.
- Auto-blinds display.

### 2. Board / Action Panel

Contains:

- Current street indicator.
- Board card picker when needed.
- Legal action buttons only.
- Amount input in bb.
- Raise-to helper.
- Timeline list.

### 3. Analyze Panel

Contains:

- Manual Analyze button.
- Disabled reason when unavailable.

### 4. Results Panel

Contains:

- Hand State.
- Range Analysis.
- Math.
- Final Decision.

---

## 7.3 Results Display

### Hand State section

Show:

- current street,
- pot in bb,
- bet to call in bb,
- effective stack in bb,
- SPR,
- current actor,
- last aggressor,
- hero remaining stack,
- villain remaining stack.

### Range Analysis section

Show:

- estimated villain range,
- confidence,
- overall tendency,
- value/draw/bluff categories,
- category weights,
- range reasoning,
- fallback warning if used.

### Math section

Show:

- equity vs estimated range,
- pot odds,
- EV call,
- MDF,
- outs,
- SPR.

### Final Decision section

Show:

- action badge: `FOLD`, `CALL`, or `RAISE`,
- confidence,
- reasoning,
- raise-to amount if applicable,
- amount-to-add if applicable,
- sensitivity note.

---

## 8. API Specification

## 8.1 New Endpoint

```http
POST /api/analyze_full_hand
```

### Request body

```json
{
  "setup": {
    "hero_position": "BTN",
    "hero_stack_bb": 100,
    "villain_stack_bb": 100,
    "villain_profile": "Unknown",
    "hero_hole_cards": ["Ah", "Kd"]
  },
  "board": {
    "flop": ["Ks", "9h", "4c"],
    "turn": ["2h"],
    "river": []
  },
  "actions": [
    {
      "street": "preflop",
      "actor": "hero",
      "type": "raise",
      "amount_added": 2.0,
      "input_mode": "raise_to",
      "input_amount": 2.5
    },
    {
      "street": "preflop",
      "actor": "villain",
      "type": "call"
    },
    {
      "street": "flop",
      "actor": "villain",
      "type": "check"
    },
    {
      "street": "flop",
      "actor": "hero",
      "type": "bet",
      "amount_added": 2.0
    },
    {
      "street": "flop",
      "actor": "villain",
      "type": "raise",
      "amount_added": 6.0,
      "all_in": false
    }
  ]
}
```

### Success response

```json
{
  "success": true,
  "hand_state": {
    "street": "flop",
    "pot_bb": 15.5,
    "bet_to_call_bb": 6.0,
    "effective_stack_bb": 91.5,
    "spr": 5.9,
    "current_actor": "hero",
    "last_aggressor": "villain",
    "hero_stack_bb": 91.5,
    "villain_stack_bb": 91.5,
    "legal_actions": ["fold", "call", "raise"],
    "analyze_allowed": true,
    "disabled_reason": null
  },
  "range_analysis": {
    "estimated_range": "...",
    "confidence": "MEDIUM",
    "overall_tendency": "value-heavy",
    "categories": {},
    "reasoning": "...",
    "fallback_used": false
  },
  "metrics": {
    "pot_odds_pct": 25.0,
    "spr": 5.9,
    "mdf": 75.0,
    "outs": 6,
    "equity_pct": 38.2,
    "ev_call": -1.1
  },
  "decision": {
    "action": "FOLD",
    "raise_to_bb": null,
    "amount_to_add_bb": null,
    "confidence": "MEDIUM",
    "reasoning": "...",
    "sensitivity_note": "..."
  }
}
```

### Error response

```json
{
  "success": false,
  "error": "Analyze is only allowed when Hero is to act"
}
```

---

## 9. Data Model Requirements

## 9.1 Setup

```json
{
  "hero_position": "BTN|BB",
  "hero_stack_bb": 100,
  "villain_stack_bb": 100,
  "villain_profile": "Unknown",
  "hero_hole_cards": ["Ah", "Kd"]
}
```

## 9.2 Action

```json
{
  "street": "preflop|flop|turn|river",
  "actor": "hero|villain",
  "type": "fold|check|call|bet|raise",
  "amount_added": 2.0,
  "all_in": false,
  "input_mode": "amount_added|raise_to",
  "input_amount": 2.5
}
```

Fields `amount_added`, `all_in`, `input_mode`, and `input_amount` are action-dependent.

## 9.3 Derived Hand State

```json
{
  "street": "flop",
  "pot_bb": 15.5,
  "hero_stack_bb": 91.5,
  "villain_stack_bb": 91.5,
  "effective_stack_bb": 91.5,
  "spr": 5.9,
  "current_actor": "hero",
  "last_aggressor": "villain",
  "bet_to_call_bb": 6.0,
  "current_bet_bb": 8.0,
  "min_raise_to_bb": 14.0,
  "legal_actions": ["fold", "call", "raise"],
  "awaiting_board": false,
  "hand_ended": false,
  "all_in_locked": false,
  "analyze_allowed": true,
  "disabled_reason": null
}
```

---

## 10. Architecture / Module Plan

## 10.1 Add `pokerbot/hand_state.py`

Responsibilities:

- setup validation,
- card validation integration,
- auto-post blinds,
- replay action timeline,
- track pot,
- track stacks,
- track street contributions,
- calculate current bet,
- calculate call amount,
- calculate minimum raise,
- determine current actor,
- determine legal actions,
- close betting streets,
- detect awaiting board states,
- detect fold/end state,
- detect all-in lock,
- derive hand state object,
- validate analyze eligibility.

## 10.2 Add `pokerbot/range_advisor.py`

Responsibilities:

- define `RangeAnalysis` dataclass,
- build Range LLM prompt,
- call fast model,
- parse strict JSON,
- validate schema,
- validate estimated range using `range_parser.py`,
- provide fallback range on invalid output/timeout,
- return structured range analysis.

## 10.3 Update `pokerbot/advisor.py`

Responsibilities:

- build full-hand Decision LLM prompt,
- include timeline, hand state, range analysis, metrics,
- call final reasoning model,
- parse final decision,
- support raise-to and amount-to-add outputs,
- handle timeout/error gracefully.

## 10.4 Reuse existing modules

Existing modules should remain useful:

- `input_parser.py`
- `range_parser.py`
- `math_engine.py`
- `equity.py`
- `advisor.py`, after modification

## 10.5 Update `pokerbot/app.py`

Add:

```text
POST /api/analyze_full_hand
```

The old snapshot endpoint may remain temporarily for tests or backwards compatibility but should no longer be the primary UI flow.

---

## 11. Frontend State Management

The frontend shall store setup, board, and actions locally until Analyze is clicked.

Flow:

```text
User builds hand in browser
→ frontend updates local state and legal actions
→ user clicks Analyze
→ frontend sends full hand object to backend
→ backend replays and validates statelessly
→ backend returns result
```

Backend sessions are out of scope for v1.

---

## 12. Performance Requirements

### Target

The full two-LLM analysis should aim to complete in approximately 20 seconds or less.

### Range LLM

```text
timeout: 8–10 seconds
max_tokens: 500–700
temperature: 0.2
```

### Decision LLM

```text
timeout: 12–15 seconds
max_tokens: 900–1200
temperature: 0.3
```

### Equity

Equity calculation should remain fast enough to fit between the two LLM calls without making total latency unacceptable.

---

## 13. Error Handling Requirements

### Backend errors

Return structured JSON errors:

```json
{
  "success": false,
  "error": "Clear human-readable error message"
}
```

### Range LLM errors

Do not fail the full analysis unless all fallback mechanisms fail.

Use fallback range and continue.

### Decision LLM errors

Return successful hand state/range/math data, but decision action should be `ERROR`.

### Invalid action timeline

Reject with 400-style error response.

### Analyze not allowed

Reject with an explicit reason.

---

## 14. Acceptance Criteria

### Core hand-state acceptance criteria

- Given Hero BTN/SB with 100bb and Villain BB with 100bb, backend auto-posts 0.5bb/1bb and sets Hero as first preflop actor.
- Given Hero BB, backend auto-posts Villain SB 0.5bb and Hero BB 1bb and sets Villain as first preflop actor.
- Given a legal raise/call sequence, backend derives correct pot and stacks.
- Given a legal bet/call sequence postflop, backend closes the street and awaits next board card.
- Given illegal actions, backend rejects the request.
- Analyze is allowed only when Hero is the current actor and a decision exists.

### Range pipeline acceptance criteria

- Valid Range LLM JSON is parsed and returned.
- Invalid Range LLM JSON triggers fallback.
- Unparseable `estimated_range` triggers fallback.
- Range LLM timeout triggers fallback.
- Fallback marks `fallback_used = true` and `confidence = LOW`.

### Decision pipeline acceptance criteria

- Final Decision LLM receives full timeline, range analysis, and metrics.
- Final response parses `FOLD`, `CALL`, or `RAISE`.
- Raise response includes both `raise_to_bb` and `amount_to_add_bb` if applicable.
- Decision LLM timeout returns decision `ERROR` but preserves hand state, range, and metrics.

### UI acceptance criteria

- Existing snapshot form is replaced by full hand builder.
- Visual style remains consistent with current app.
- Legal action buttons are gated.
- Analyze button is manual and gated.
- Disabled Analyze button shows reason.
- Results display Hand State, Range Analysis, Math, and Final Decision sections.

---

## 15. Test Plan

## 15.1 `test_hand_state.py`

Tests should cover:

- auto-post blinds when Hero is BTN/SB,
- auto-post blinds when Hero is BB,
- correct first actor preflop,
- raise with incremental amount,
- raise-to helper conversion where applicable,
- call amount calculation,
- pot calculation,
- stack calculation,
- street contribution tracking,
- check/check closes postflop street,
- bet/call closes postflop street,
- raise/call closes betting round,
- illegal call when no bet exists,
- illegal check facing bet,
- illegal bet facing bet,
- illegal raise too small,
- illegal action by wrong actor,
- all-in lock detection,
- fold hand-ended detection,
- river betting closed hand complete,
- analyze allowed only when Hero is to act.

## 15.2 `test_range_advisor.py`

Tests should cover:

- valid JSON parse,
- invalid JSON fallback,
- invalid range fallback,
- missing required fields fallback,
- invalid confidence normalization/fallback,
- timeout fallback,
- category parsing,
- fallback_used flag.

## 15.3 `test_analyze_full_hand_api.py`

Tests should cover:

- valid preflop decision point,
- valid flop decision point,
- valid turn decision point,
- valid river decision point,
- invalid action sequence returns error,
- analyze when villain is to act returns error,
- analyze while awaiting board cards returns error,
- analyze after all-in returns error,
- range LLM fallback still returns success,
- decision LLM timeout returns success with decision `ERROR`.

## 15.4 Existing tests

Existing tests for these modules should remain green or be updated intentionally:

- `test_input_parser.py`
- `test_range_parser.py`
- `test_math_engine.py`
- `test_equity.py`
- `test_advisor.py`
- `test_app.py`

---

## 16. Implementation Phases

### Phase 1 — Hand State Engine

1. Create `pokerbot/hand_state.py`.
2. Implement setup model and validation.
3. Implement blind auto-posting.
4. Implement action replay.
5. Implement pot/stack/contribution tracking.
6. Implement legal action validation.
7. Implement street advancement.
8. Implement analyze eligibility.
9. Add comprehensive tests.

### Phase 2 — Full-Hand API Without LLM

1. Add `/api/analyze_full_hand`.
2. Accept setup, board, and actions.
3. Replay and validate timeline.
4. Return derived hand state.
5. Add route tests.

### Phase 3 — Preflop Baselines

1. Add simple heads-up preflop presets.
2. Select relevant baseline based on action line.
3. Expose baseline to Range LLM prompt and fallback logic.

### Phase 4 — Range Advisor

1. Create `pokerbot/range_advisor.py`.
2. Build strict JSON prompt.
3. Call fast Range LLM.
4. Parse and validate output.
5. Add fallback behavior.
6. Add unit tests.

### Phase 5 — Equity and Metrics Integration

1. Parse `range_analysis.estimated_range`.
2. Compute equity.
3. Compute pot odds, SPR, MDF, outs, EV call using derived hand state.
4. Add tests for full pipeline math.

### Phase 6 — Final Decision Advisor

1. Update `advisor.py` for full-hand prompt.
2. Include full range analysis JSON.
3. Include computed metrics.
4. Parse final decision format.
5. Handle timeout/error.
6. Add tests.

### Phase 7 — Frontend Replacement

1. Replace snapshot UI with setup/action builder.
2. Preserve dark aesthetic and card picker style.
3. Add local frontend state.
4. Add strict legal-action gating.
5. Add raise-to helper.
6. Add manual gated Analyze button.
7. Add structured results display.

### Phase 8 — Integration and Polish

1. Add end-to-end tests.
2. Tune prompts.
3. Tune timeouts.
4. Tune simulation counts.
5. Update README.

---

## 17. Future Enhancements

Potential future features:

- Multiplayer support.
- Tournament mode.
- Antes.
- ICM calculations.
- Raw hand-history import.
- Free-text villain notes.
- Saved villain profiles.
- Weighted equity using category weights.
- Equity-only all-in reports.
- Review mode with known villain cards.
- Session persistence.
- Hand history export.
- Range matrix visualization.
- Model selection dropdown.
- Streaming LLM reasoning.
- High-accuracy equity mode.
- Detailed preflop range matrices by sizing.

---

## 18. Final Product Definition

PokerBot Full-Hand Advisor is a heads-up cash-game decision assistant that lets users manually reconstruct an entire hand in big blinds. The system uses a strict timeline engine to derive pot, stacks, street state, legal actions, and decision eligibility. At the decision point, it uses a fast Range LLM to estimate villain's current range, validates that range with code, falls back safely if needed, computes poker math and equity, and then uses a stronger Decision LLM to recommend exactly one action with structured reasoning.

The product prioritizes correctness, speed, explainability, and future expandability over unsupported complexity.
