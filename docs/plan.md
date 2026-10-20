# Poker Bot — Full Project Plan

## 1. Overview

A **Texas Hold'em poker advisor** that:

1. Accepts game-state inputs (hole cards, board, pot, stacks, villain range, etc.).
2. Computes all key poker math metrics (pot odds, SPR, MDF, outs, equity via Monte Carlo simulation, EV of calling).
3. Feeds everything into an LLM (Claude 3 Haiku via OpenRouter) for a final **fold / call / raise** decision with full reasoning.

Everything is Python. Card input is done through a **web-based UI** (Flask) with a visual 52-card picker grid — click to select hole cards and board cards. Numeric fields and villain range are entered via form inputs. Results (metrics + LLM decision) are displayed inline on the same page.

---

## 2. Project Structure

```
pokerbot/
├── plan.md                  # This file
├── requirements.txt         # Dependencies
├── .env.example             # Template for API key
├── .env                     # (git-ignored) actual API key
├── pyproject.toml           # Optional — packaging metadata
│
├── pokerbot/
│   ├── __init__.py
│   ├── constants.py         # Card / rank / suit constants, hand-range definitions
│   ├── input_parser.py      # Parse & validate every user input
│   ├── range_parser.py      # "TT+, AK, AQs" → list of concrete hand combos
│   ├── math_engine.py       # pot_odds, spr, mdf, outs, ev_call calculations
│   ├── equity.py            # Monte Carlo equity vs villain range (uses treys)
│   ├── advisor.py           # Build prompt → call OpenRouter → parse response
│   └── app.py               # Flask web app entry-point
│
├── static/
│   ├── css/
│   │   └── style.css        # Card grid, layout, result panel styling
│   └── js/
│       └── app.js           # Card picker logic, form submission, result rendering
│
├── templates/
│   └── index.html           # Single-page UI template
│
├── tests/
│   ├── __init__.py
│   ├── test_range_parser.py
│   ├── test_math_engine.py
│   ├── test_equity.py
│   ├── test_input_parser.py
│   ├── test_advisor.py      # Mocked LLM tests
│   ├── test_app.py          # Flask route tests
│   └── test_integration.py  # End-to-end (requires API key)
│
└── README.md
```

---

## 3. Dependencies (`requirements.txt`)

```
treys>=0.1.8
requests>=2.31
python-dotenv>=1.0
flask>=3.0
pytest>=8.0
pytest-mock>=3.12
```

- **treys** — fast poker hand evaluation & equity calculation.
- **requests** — HTTP calls to OpenRouter.
- **python-dotenv** — load `OPENROUTER_API_KEY` from `.env`.
- **flask** — web server for the card-picker UI.
- **pytest / pytest-mock** — testing.

---

## 4. Input Specification

| Field | Type | Example | Validation |
|---|---|---|---|
| `hole_cards` | str (2 cards) | `"AhKd"` | Exactly 2 valid cards, no duplicates with board |
| `board` | str (0-5 cards) | `"Ts9h2c"` | 0 cards (preflop), 3 (flop), 4 (turn), 5 (river); no dupes |
| `pot` | float | `120.0` | > 0 |
| `bet_to_call` | float | `40.0` | ≥ 0 (0 = check option) |
| `my_stack` | float | `500.0` | > 0 |
| `opp_stack` | float | `480.0` | > 0 |
| `position` | str | `"BTN"` / `"BB"` | One of: `UTG, UTG1, UTG2, MP, MP1, MP2, HJ, CO, BTN, SB, BB` |
| `street` | str | `"flop"` | One of: `preflop, flop, turn, river` |
| `villain_range` | str | `"TT+, AKs, AKo, AQs"` | Parseable range string (see §5) |

### Card notation

- Rank: `2 3 4 5 6 7 8 9 T J Q K A`
- Suit: `h d c s` (hearts, diamonds, clubs, spades)
- A card = rank + suit, e.g. `Ah`, `Ts`, `2c`

---

## 5. Range Parser (`range_parser.py`)

### Supported syntax

| Pattern | Meaning | Expansion example |
|---|---|---|
| `AA` | Specific pair | AA (6 combos) |
| `TT+` | Pair and above | TT, JJ, QQ, KK, AA |
| `TT-66` | Pair range | 66, 77, 88, 99, TT |
| `AKs` | Suited specific | AhKh, AdKd, AcKc, AsKs |
| `AKo` | Offsuit specific | AhKd, AhKc, … (12 combos) |
| `AK` | Both suited + offsuit | All 16 combos |
| `ATs+` | Suited, T and above with A | ATs, AJs, AQs, AKs |
| `ATo+` | Offsuit, T and above | ATo, AJo, AQo, AKo |
| `AT+` | Both s+o, T and above | AT, AJ, AQ, AK |
| `KTs-K8s` | Suited range | K8s, K9s, KTs |

### Algorithm

1. Split input on `,` and strip whitespace.
2. For each token, detect pattern (pair, pair+, pair-range, suited, offsuit, etc.).
3. Expand to a **set of 2-card tuples** (each card as a treys `Card` int).
4. Remove any combos that conflict with known dead cards (hole_cards + board).

### Output

```python
def parse_range(range_str: str, dead_cards: list[int] = []) -> list[tuple[int, int]]:
    """Return list of (card1, card2) combos as treys Card ints."""
```

---

## 6. Math Engine (`math_engine.py`)

All formulas below use **consistent units** (same currency, e.g. chips or dollars).

### 6.1 Pot Odds Percentage

```
pot_odds_pct = bet_to_call / (pot + bet_to_call) * 100
```

- If `bet_to_call == 0` → `pot_odds_pct = 0` (free check).

**Example:** pot = 120, bet_to_call = 40 → 40 / 160 × 100 = **25.0%**

### 6.2 Stack-to-Pot Ratio (SPR)

```
effective_stack = min(my_stack, opp_stack)
spr = effective_stack / pot
```

- Calculated **before** the current bet is called.
- If `pot == 0` (shouldn't happen) → guard with `spr = float('inf')`.

**Example:** my_stack = 500, opp_stack = 480, pot = 120 → SPR = 480 / 120 = **4.0**

### 6.3 Minimum Defence Frequency (MDF)

```
mdf = pot / (pot + bet_to_call) * 100
```

- If `bet_to_call == 0` → `mdf = 100` (must defend everything when checked to).

**Example:** pot = 120, bet_to_call = 40 → 120 / 160 × 100 = **75.0%**

### 6.4 Outs (estimated)

Count outs only on **flop** and **turn** (on river equity is fully determined, on preflop it's range-vs-range).

Strategy — check for common draws using the board + hole cards:

| Draw | Outs |
|---|---|
| Flush draw (4 to a suit) | 9 |
| Open-ended straight draw | 8 |
| Gutshot straight draw | 4 |
| Two overcards (no pair, both cards > board high) | 6 |
| One overcard | 3 |
| Set → full house / quads (trips on board or set) | 7 |
| Two pair → full house | 4 |
| Pair → trips | 2 |

If multiple draws exist, **combine but cap at plausible max** (don't double-count shared outs — e.g., flush draw + straight draw with one overlapping card = 9 + 8 − 1 = 15, not 17).

For simplicity in v1: count each draw independently, subtract 1 for each shared suit/rank overlap, cap at 21.

```python
def count_outs(hole_cards: list[int], board: list[int]) -> int:
    """Return estimated number of outs."""
```

On **preflop**: return `outs = -1` (not applicable, equity comes from range simulation).
On **river**: return `outs = 0` (no cards to come).

### 6.5 Equity Percentage

Delegated to `equity.py` (see §7). The math engine just receives the float.

### 6.6 EV of Calling

```
ev_call = (equity_pct / 100) * (pot + bet_to_call) - (1 - equity_pct / 100) * bet_to_call
```

Expanded:
```
ev_call = equity_frac * total_pot_after_call  −  (1 − equity_frac) * bet_to_call
       where equity_frac = equity_pct / 100
             total_pot_after_call = pot + bet_to_call
```

**Example:** equity = 55%, pot = 120, bet_to_call = 40:
```
ev_call = 0.55 * 160 − 0.45 * 40 = 88 − 18 = +70.0
```

A positive EV means calling is profitable in isolation.

```python
def calc_ev_call(equity_pct: float, pot: float, bet_to_call: float) -> float:
```

### 6.7 Full Metrics Function

```python
@dataclass
class PokerMetrics:
    pot_odds_pct: float
    spr: float
    mdf: float
    outs: int           # -1 if preflop
    equity_pct: float
    ev_call: float

def compute_metrics(
    hole_cards: list[int],
    board: list[int],
    pot: float,
    bet_to_call: float,
    my_stack: float,
    opp_stack: float,
    villain_range: list[tuple[int, int]],
    street: str
) -> PokerMetrics:
```

---

## 7. Equity Calculator (`equity.py`)

### Approach: Monte Carlo via treys

treys has a built-in `Evaluator`. We do:

1. Take our `hole_cards` (2 treys ints).
2. Take the `board` (0-5 treys ints).
3. Take the `villain_range` — list of (c1, c2) combos (already filtered for dead cards).
4. Run N simulations (default **10 000**):
   - Pick a random villain hand from the range.
   - If any villain card collides with our hand or board, skip.
   - Complete the board to 5 cards with random remaining deck cards.
   - Evaluate both hands with `Evaluator.evaluate()`.
   - Track wins / losses / ties.
5. Return `equity_pct = (wins + ties * 0.5) / total * 100`.

```python
def calculate_equity(
    hole_cards: list[int],
    board: list[int],
    villain_range: list[tuple[int, int]],
    num_simulations: int = 10_000
) -> float:
    """Return equity as a percentage (0–100)."""
```

### Edge cases

- **Empty villain range after filtering** → raise `ValueError("Villain range is empty after removing dead cards")`.
- **River (5-card board)** → no random cards needed, just iterate over villain range and evaluate. No Monte Carlo required — do exhaustive enumeration.
- **Preflop (0-card board)** → Monte Carlo with 5 community cards to deal.

---

## 8. LLM Advisor (`advisor.py`)

### 8.1 OpenRouter API Call

```
POST https://openrouter.ai/api/v1/chat/completions
Headers:
  Authorization: Bearer <OPENROUTER_API_KEY>
  Content-Type: application/json
Body:
  {
    "model": "anthropic/claude-3-haiku",
    "messages": [
      {"role": "system", "content": <SYSTEM_PROMPT>},
      {"role": "user",   "content": <USER_PROMPT>}
    ],
    "temperature": 0.3,
    "max_tokens": 1024
  }
```

### 8.2 System Prompt

```
You are an expert No-Limit Texas Hold'em poker advisor.
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
CONFIDENCE: <LOW|MEDIUM|HIGH>
```

### 8.3 User Prompt (template)

```
=== HAND SITUATION ===
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
Outs: {outs} {"(N/A preflop)" if outs == -1 else ""}
Equity vs Range: {equity_pct:.1f}%
EV of Calling: {ev_call:+.1f} chips

=== TASK ===
Recommend an action: FOLD, CALL, or RAISE. Provide full reasoning.
```

### 8.4 Response Parsing

```python
@dataclass
class Decision:
    reasoning: str
    action: str        # "FOLD" | "CALL" | "RAISE"
    raise_size: str    # e.g. "120" or "2/3 pot" or "N/A"
    confidence: str    # "LOW" | "MEDIUM" | "HIGH"
    raw_response: str  # Full LLM output for debugging
```

Parse the LLM text output with regex:
```python
action_match = re.search(r"DECISION:\s*(FOLD|CALL|RAISE)", text, re.IGNORECASE)
raise_match  = re.search(r"RAISE_SIZE:\s*(.+)", text, re.IGNORECASE)
conf_match   = re.search(r"CONFIDENCE:\s*(LOW|MEDIUM|HIGH)", text, re.IGNORECASE)
reasoning    = text.split("DECISION:")[0].replace("REASONING:", "").strip()
```

If parsing fails, return `Decision(action="ERROR", reasoning=raw_text, ...)`.

---

## 9. Web UI (`app.py` + `templates/` + `static/`)

The entire input flow is a **single-page web app** served by Flask.

### 9.1 Page Layout (`templates/index.html`)

The page is divided into three vertical sections:

```
┌─────────────────────────────────────────────────────────┐
│  🃏  PokerBot Advisor                                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─── CARD PICKER ───────────────────────────────────┐  │
│  │                                                   │  │
│  │  52-card grid (4 rows × 13 cols)                  │  │
│  │  Rows: ♠ ♥ ♦ ♣                                    │  │
│  │  Cols: A K Q J T 9 8 7 6 5 4 3 2                  │  │
│  │                                                   │  │
│  │  Click mode selector:                             │  │
│  │    [● Hole Cards (0/2)]  [○ Board (0/5)]          │  │
│  │                                                   │  │
│  │  Selected cards highlight:                        │  │
│  │    Hole cards → blue border                       │  │
│  │    Board cards → green border                     │  │
│  │    Unavailable (already picked) → greyed out      │  │
│  │                                                   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─── SELECTED CARDS DISPLAY ────────────────────────┐  │
│  │  Hole: [A♥] [K♦]                                  │  │
│  │  Board: [T♠] [9♥] [2♣] [ ] [ ]                    │  │
│  │                      (click card to deselect)      │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─── GAME STATE FORM ───────────────────────────────┐  │
│  │  Street:    [▼ Flop     ]  (auto-set from board)  │  │
│  │  Pot:       [  120      ]                         │  │
│  │  Bet to call: [ 40      ]                         │  │
│  │  My stack:  [  500      ]                         │  │
│  │  Opp stack: [  480      ]                         │  │
│  │  Position:  [▼ BTN      ]                         │  │
│  │  Villain range: [ TT+, AK, AQs           ]       │  │
│  │                                                   │  │
│  │  [ 🔍 Analyze Hand ]                              │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─── RESULTS PANEL ─────────────────────────────────┐  │
│  │  (hidden until Analyze is clicked)                │  │
│  │                                                   │  │
│  │  ── Computed Metrics ──                           │  │
│  │  Pot Odds:  25.0%    SPR:     4.00                │  │
│  │  MDF:       75.0%    Outs:    6                   │  │
│  │  Equity:    38.2%    EV(call): -1.1               │  │
│  │                                                   │  │
│  │  ── LLM Decision ──                               │  │
│  │  ┌──────────────────────────────────┐             │  │
│  │  │  FOLD         Confidence: MED   │             │  │
│  │  └──────────────────────────────────┘             │  │
│  │                                                   │  │
│  │  ── Reasoning ──                                  │  │
│  │  With 38% equity and needing 25% pot odds, a     │  │
│  │  call is marginally profitable. However the SPR   │  │
│  │  of 4.0 means ...                                 │  │
│  │                                                   │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 9.2 Card Picker Behaviour (`static/js/app.js`)

**State management** (all in JS, no page reloads):

```javascript
const state = {
    mode: 'hole',          // 'hole' | 'board'
    holeCards: [],          // max 2 card strings, e.g. ['Ah', 'Kd']
    boardCards: [],         // max 5 card strings
};
```

**Click logic:**

1. User clicks a card cell in the 52-card grid.
2. If the card is already selected (in hole or board) → **deselect** it (remove from its list, un-highlight).
3. If mode is `'hole'` and `holeCards.length < 2` → add to `holeCards`, highlight blue.
4. If mode is `'board'` and `boardCards.length < 5` → add to `boardCards`, highlight green.
5. If the current mode's list is full → do nothing (flash a subtle warning).
6. After any change, update the "Selected Cards Display" strip below the grid.

**Auto-street detection:**

Whenever `boardCards` changes, auto-set the street dropdown:
- 0 cards → `preflop`
- 3 cards → `flop`
- 4 cards → `turn`
- 5 cards → `river`
- 1–2 cards → invalid, show red warning "Board must have 0, 3, 4, or 5 cards"

**Card cell rendering:**

Each cell shows rank + suit symbol in the suit's colour:
- ♠ / ♣ → black text
- ♥ / ♦ → red text
- Cell size: ~50×70px, rounded corners, light border
- Hover: subtle lift shadow
- Selected-hole: solid blue border + light blue bg
- Selected-board: solid green border + light green bg
- Greyed out: 30% opacity, pointer-events: none (when card is in the other list)

### 9.3 Card Grid HTML Structure

The 52-card grid is a CSS grid (or flex table), 4 rows × 13 columns:

```
        A    K    Q    J    T    9    8    7    6    5    4    3    2
  ♠   [As] [Ks] [Qs] [Js] [Ts] [9s] [8s] [7s] [6s] [5s] [4s] [3s] [2s]
  ♥   [Ah] [Kh] [Qh] [Jh] [Th] [9h] [8h] [7h] [6h] [5h] [4h] [3h] [2h]
  ♦   [Ad] [Kd] [Qd] [Jd] [Td] [9d] [8d] [7d] [6d] [5d] [4d] [3d] [2d]
  ♣   [Ac] [Kc] [Qc] [Jc] [Tc] [9c] [8c] [7c] [6c] [5c] [4c] [3c] [2c]
```

Generated via Jinja2 loop or directly in JS.

### 9.4 Flask Routes (`app.py`)

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Serve `index.html` (the full single-page UI) |
| `/api/analyze` | POST | Accept JSON game state, return JSON metrics + decision |

#### `POST /api/analyze`

**Request body:**
```json
{
    "hole_cards": ["Ah", "Kd"],
    "board": ["Ts", "9h", "2c"],
    "pot": 120,
    "bet_to_call": 40,
    "my_stack": 500,
    "opp_stack": 480,
    "position": "BTN",
    "villain_range": "TT+, AK, AQs"
}
```

Note: `street` is **derived server-side** from `len(board)` (0→preflop, 3→flop, 4→turn, 5→river). The client also sends it but the server recomputes for safety.

**Response body:**
```json
{
    "success": true,
    "metrics": {
        "pot_odds_pct": 25.0,
        "spr": 4.0,
        "mdf": 75.0,
        "outs": 6,
        "equity_pct": 38.2,
        "ev_call": -1.1
    },
    "decision": {
        "action": "FOLD",
        "raise_size": "N/A",
        "confidence": "MEDIUM",
        "reasoning": "With 38% equity and needing 25%..."
    }
}
```

**Error response:**
```json
{
    "success": false,
    "error": "Hole cards must be exactly 2 cards"
}
```

### 9.5 Frontend → Backend Flow (`static/js/app.js`)

```
[User clicks Analyze]
        │
        ▼
  Collect state:
    - holeCards[] from picker
    - boardCards[] from picker
    - pot, bet, stacks from form inputs
    - position from dropdown
    - villain_range from text input
        │
        ▼
  Client-side validation:
    - hole must be exactly 2
    - board must be 0, 3, 4, or 5
    - pot > 0, bet ≥ 0, stacks > 0
    - villain_range not empty
        │  (if fail → show red inline error, don't submit)
        ▼
  POST /api/analyze  (JSON body)
    - Show spinner overlay on results panel
        │
        ▼
  On success:
    - Hide spinner
    - Populate metrics section
    - Show decision badge (FOLD=red, CALL=yellow, RAISE=green)
    - Show reasoning text
        │
  On error:
    - Hide spinner
    - Show error message in results panel
```

### 9.6 Styling (`static/css/style.css`)

**Design tokens:**
- Background: `#1a1a2e` (dark navy)
- Card grid bg: `#16213e`
- Card cell bg: `#f0f0f0` (light), hover: `#e0e0e0`
- Suit colours: red `#e74c3c` (♥♦), black `#2c3e50` (♠♣)
- Hole selected: `#3498db` border, `#d6eaf8` bg
- Board selected: `#2ecc71` border, `#d5f5e3` bg
- Decision badge: FOLD `#e74c3c`, CALL `#f39c12`, RAISE `#2ecc71`
- Font: `'Segoe UI', system-ui, sans-serif`
- Results panel: `#0f3460` bg, white text

**Responsive:** single-column on mobile (cards grid scrolls horizontally).

### 9.7 Clear / Reset

A **"Clear All"** button at the top resets:
- All selected cards (hole + board)
- All form fields to defaults
- Hides the results panel

---

## 10. Detailed Test Plan

### 10.1 `test_range_parser.py`

| # | Test Name | Input | Expected Output | What It Validates |
|---|---|---|---|---|
| 1 | `test_single_pair` | `"AA"` | 6 combos (all AA combos) | Basic pair expansion |
| 2 | `test_pair_plus` | `"QQ+"` | QQ + KK + AA = 18 combos | `+` operator on pairs |
| 3 | `test_pair_range` | `"88-55"` | 55,66,77,88 = 24 combos | Dash range on pairs |
| 4 | `test_suited_hand` | `"AKs"` | 4 combos (one per suit) | Suited expansion |
| 5 | `test_offsuit_hand` | `"AKo"` | 12 combos | Offsuit expansion |
| 6 | `test_any_hand` | `"AK"` | 16 combos (4s + 12o) | Combined expansion |
| 7 | `test_suited_plus` | `"ATs+"` | ATs, AJs, AQs, AKs = 16 combos | `+` on suited |
| 8 | `test_offsuit_plus` | `"ATo+"` | ATo, AJo, AQo, AKo = 48 combos | `+` on offsuit |
| 9 | `test_any_plus` | `"AT+"` | AT, AJ, AQ, AK = 64 combos | `+` on any |
| 10 | `test_suited_dash_range` | `"KTs-K8s"` | K8s, K9s, KTs = 12 combos | Dash range suited |
| 11 | `test_complex_range` | `"TT+, AKs, AQo"` | 18 + 4 + 12 = 34 combos | Multi-token, comma-separated |
| 12 | `test_dead_card_removal` | `"AA"`, dead=`[Ah, Ad]` | 3 combos (remove any with Ah or Ad) | Dead-card filtering |
| 13 | `test_empty_after_filter` | `"AhKh"` specific, dead has Ah | 0 combos → `ValueError` | Edge case empty range |
| 14 | `test_duplicate_combos` | `"AA, AA"` | Still 6 combos (deduped) | No double-counting |
| 15 | `test_invalid_token` | `"XY+"` | `ValueError` | Bad input handling |
| 16 | `test_whitespace_handling` | `" TT+ , AK "` | Same as `"TT+, AK"` | Trimming |

### 10.2 `test_math_engine.py`

| # | Test Name | Inputs | Expected | What It Validates |
|---|---|---|---|---|
| 1 | `test_pot_odds_basic` | pot=120, bet=40 | 25.0 | Standard pot odds |
| 2 | `test_pot_odds_zero_bet` | pot=100, bet=0 | 0.0 | Free check |
| 3 | `test_pot_odds_large_bet` | pot=100, bet=100 | 50.0 | Pot-sized bet |
| 4 | `test_pot_odds_small_bet` | pot=200, bet=10 | ~4.76 | Small bet into big pot |
| 5 | `test_spr_basic` | my=500, opp=480, pot=120 | 4.0 | Effective stack = min |
| 6 | `test_spr_short_stack` | my=50, opp=1000, pot=100 | 0.5 | I'm the short stack |
| 7 | `test_spr_equal_stacks` | my=300, opp=300, pot=100 | 3.0 | Equal stacks |
| 8 | `test_mdf_basic` | pot=120, bet=40 | 75.0 | Standard MDF |
| 9 | `test_mdf_zero_bet` | pot=100, bet=0 | 100.0 | Check = defend all |
| 10 | `test_mdf_overbet` | pot=100, bet=200 | ~33.3 | Overbet MDF |
| 11 | `test_ev_call_positive` | equity=55, pot=120, bet=40 | +70.0 | Profitable call |
| 12 | `test_ev_call_negative` | equity=20, pot=120, bet=40 | -0.0 (calc: 0.2×160 - 0.8×40 = 32-32=0) | Breakeven edge |
| 13 | `test_ev_call_zero_bet` | equity=50, pot=100, bet=0 | +50.0 | Free check always +EV |
| 14 | `test_ev_call_dominated` | equity=10, pot=100, bet=50 | 0.1×150 - 0.9×50 = 15-45 = -30.0 | Clear fold EV |

#### Outs tests (within `test_math_engine.py`)

| # | Test Name | Hole | Board | Expected Outs | What It Validates |
|---|---|---|---|---|---|
| 15 | `test_outs_flush_draw` | `Ah5h` | `Kh9h2c` | 9 | 4-to-flush |
| 16 | `test_outs_oesd` | `8h7h` | `6c5dKs` | 8 (+ flush component if applicable) | Open-ended straight draw |
| 17 | `test_outs_gutshot` | `AhTd` | `Kc9h5s` | 4 (QxJx fills, but gutshot to broadway: need J only = 4) | Gutshot |
| 18 | `test_outs_two_overcards` | `AhKd` | `9h7c2s` | 6 | Two overs |
| 19 | `test_outs_preflop` | `AhKd` | `[]` | -1 | N/A on preflop |
| 20 | `test_outs_river` | `AhKd` | `9h7c2s4dTs` | 0 | No outs on river |
| 21 | `test_outs_made_hand` | `AhAd` | `As7c2d` | 7 (set → FH/quads: any A=1, any 7=2 remaining, any 2=2 remaining, + board pair ≈ 7) | Set improvement |
| 22 | `test_outs_combo_draw` | `Jh Th` | `9h 8h 2c` | ~15 (flush 9 + straight 8 − overlap ~2) | Combo draw |

### 10.3 `test_equity.py`

| # | Test Name | Hole | Board | Villain Range | Expected Equity (±5%) | What It Validates |
|---|---|---|---|---|---|
| 1 | `test_equity_aa_vs_kk_preflop` | AA | `[]` | KK (6 combos) | ~81% | Premium vs premium |
| 2 | `test_equity_ak_vs_pairs_flop` | AhKd | Ts9h2c | TT+ | ~15-25% | Behind on flop |
| 3 | `test_equity_set_vs_overpair` | 9s9d | Ts9h2c | TT-TT (just TT) | ~85-95% | Set vs overpair |
| 4 | `test_equity_flush_draw` | Ah5h | Kh9h2c | KK (remaining combos) | ~35% | Drawing hand |
| 5 | `test_equity_river_winner` | AhKd | AsTd5c3h2s | QQ | 100.0% | River, we have top pair, they have underpair |
| 6 | `test_equity_river_loser` | 7h6d | AsTd5c3h2s | AA | 0.0% | River, they have set |
| 7 | `test_equity_coinflip` | AhKd | `[]` | QQ | ~43% | Classic coinflip preflop |
| 8 | `test_equity_wide_range` | AhKd | `[]` | "22+, AT+, KT+" | ~60-70% | Equity vs wide range |
| 9 | `test_equity_empty_range` | AhKd | `[]` | `[]` | `ValueError` | No villain hands |
| 10 | `test_equity_deterministic_seed` | AhKd | `[]` | QQ | Same ±1% on 2 runs w/ same seed | Reproducibility |

**Note:** Equity tests use a tolerance of ±5% because Monte Carlo has variance. Use `num_simulations=50_000` for test accuracy, or set a random seed for determinism.

### 10.4 `test_input_parser.py`

| # | Test Name | Input | Expected | What It Validates |
|---|---|---|---|---|
| 1 | `test_parse_hole_cards_valid` | `"AhKd"` | 2 treys ints | Basic parsing |
| 2 | `test_parse_hole_cards_lowercase` | `"ahkd"` | Same as `"AhKd"` | Case insensitivity |
| 3 | `test_parse_hole_cards_with_space` | `"Ah Kd"` | Same | Whitespace tolerance |
| 4 | `test_parse_hole_cards_invalid_rank` | `"XhKd"` | `ValueError` | Bad rank |
| 5 | `test_parse_hole_cards_invalid_suit` | `"AxKd"` | `ValueError` | Bad suit |
| 6 | `test_parse_hole_cards_one_card` | `"Ah"` | `ValueError` | Too few cards |
| 7 | `test_parse_hole_cards_three_cards` | `"AhKdQs"` | `ValueError` | Too many cards |
| 8 | `test_parse_hole_cards_duplicate` | `"AhAh"` | `ValueError` | Same card twice |
| 9 | `test_parse_board_flop` | `"Ts9h2c"` | 3 treys ints | 3-card board |
| 10 | `test_parse_board_turn` | `"Ts9h2c5d"` | 4 treys ints | 4-card board |
| 11 | `test_parse_board_river` | `"Ts9h2c5d8s"` | 5 treys ints | 5-card board |
| 12 | `test_parse_board_empty` | `""` | `[]` | Preflop |
| 13 | `test_parse_board_invalid_count` | `"Ts9h"` | `ValueError` | 2 cards = invalid |
| 14 | `test_board_hole_overlap` | hole=`"AhKd"`, board=`"Ah9h2c"` | `ValueError` | Card in both |
| 15 | `test_parse_street_valid` | `"flop"`, `"FLOP"`, `"Flop"` | `"flop"` | Case insensitive |
| 16 | `test_parse_street_invalid` | `"flopp"` | `ValueError` | Typo |
| 17 | `test_parse_position_valid` | `"BTN"`, `"btn"` | `"BTN"` | Case insensitive |
| 18 | `test_parse_position_invalid` | `"BUTTON"` | `ValueError` | Not in valid list |
| 19 | `test_street_board_consistency_preflop` | street=`"preflop"`, board=`"Ts9h2c"` | `ValueError` | Board should be empty |
| 20 | `test_street_board_consistency_flop` | street=`"flop"`, board=`"Ts9h2c5d"` | `ValueError` | Flop needs exactly 3 |
| 21 | `test_pot_positive` | `0` or `-5` | `ValueError` | Pot must be > 0 |
| 22 | `test_bet_non_negative` | `-1` | `ValueError` | Bet must be ≥ 0 |
| 23 | `test_stack_positive` | `0` | `ValueError` | Stack must be > 0 |

### 10.5 `test_advisor.py` (Mocked LLM)

These tests **mock** the HTTP call to OpenRouter so they run without an API key.

| # | Test Name | Mock Response | Expected | What It Validates |
|---|---|---|---|---|
| 1 | `test_parse_fold_response` | `"REASONING: Bad odds\nDECISION: FOLD\nRAISE_SIZE: N/A\nCONFIDENCE: HIGH"` | `Decision(action="FOLD", confidence="HIGH")` | Basic parse |
| 2 | `test_parse_call_response` | `"REASONING: Good odds\nDECISION: CALL\nRAISE_SIZE: N/A\nCONFIDENCE: MEDIUM"` | `Decision(action="CALL")` | Call parse |
| 3 | `test_parse_raise_response` | `"REASONING: Strong hand\nDECISION: RAISE\nRAISE_SIZE: 120\nCONFIDENCE: HIGH"` | `Decision(action="RAISE", raise_size="120")` | Raise with size |
| 4 | `test_parse_malformed_response` | `"I think you should fold"` | `Decision(action="ERROR")` | Graceful degradation |
| 5 | `test_prompt_contains_metrics` | N/A (inspect built prompt) | Prompt includes pot_odds, spr, equity, etc. | Prompt construction |
| 6 | `test_api_error_handling` | Mock 500 error | `Decision(action="ERROR", reasoning="API error...")` | HTTP error handling |
| 7 | `test_api_timeout` | Mock timeout | `Decision(action="ERROR")` | Timeout handling |
| 8 | `test_api_key_missing` | No env var set | `ValueError("OPENROUTER_API_KEY not set")` | Config validation |

### 10.6 `test_app.py` (Flask Route Tests)

Uses Flask's built-in test client (`app.test_client()`). LLM calls are **mocked**.

| # | Test Name | Request | Expected | What It Validates |
|---|---|---|---|---|
| 1 | `test_index_page_loads` | `GET /` | 200, HTML contains "PokerBot" | Page serves correctly |
| 2 | `test_analyze_valid_flop` | `POST /api/analyze` with valid flop data | 200, `success: true`, metrics + decision present | Happy path |
| 3 | `test_analyze_valid_preflop` | `POST /api/analyze` with 0 board cards | 200, `outs: -1` | Preflop handling |
| 4 | `test_analyze_valid_river` | `POST /api/analyze` with 5 board cards | 200, `outs: 0` | River handling |
| 5 | `test_analyze_missing_hole_cards` | `POST /api/analyze`, `hole_cards: []` | 400, `success: false`, error message | Validation — missing hole cards |
| 6 | `test_analyze_invalid_board_count` | `POST /api/analyze`, `board: ["Ts", "9h"]` (2 cards) | 400, `success: false` | Validation — bad board count |
| 7 | `test_analyze_duplicate_cards` | hole=`["Ah","Kd"]`, board=`["Ah","9h","2c"]` | 400, error about duplicate | Validation — overlap |
| 8 | `test_analyze_negative_pot` | `pot: -10` | 400, error about pot | Validation — numeric field |
| 9 | `test_analyze_empty_range` | `villain_range: ""` | 400, error about range | Validation — empty range |
| 10 | `test_analyze_invalid_position` | `position: "BUTTON"` | 400, error about position | Validation — bad enum |
| 11 | `test_analyze_returns_json_structure` | Valid request | Response has `metrics` dict with all 6 keys, `decision` dict with 4 keys | Schema completeness |
| 12 | `test_analyze_llm_error_graceful` | Mock LLM to raise exception | 200, `decision.action: "ERROR"` | Graceful LLM failure |

### 10.7 `test_integration.py` (End-to-End)

**Requires `OPENROUTER_API_KEY` in `.env`**. Mark with `@pytest.mark.integration`.

| # | Test Name | Scenario | What It Validates |
|---|---|---|---|
| 1 | `test_full_pipeline_obvious_fold` | Hole: 7h2c, Board: As Ks Qs Js Ts (river), Villain: AA. bet_to_call=100, pot=50 | Full pipeline returns a valid Decision object (action ∈ {FOLD,CALL,RAISE}) — likely FOLD |
| 2 | `test_full_pipeline_obvious_call` | Hole: AhAs, Board: Ac Ad Ks (flop), Villain: KK. bet_to_call=10, pot=500 | Returns valid Decision — likely CALL/RAISE (quad aces) |
| 3 | `test_full_pipeline_preflop` | Hole: AhKd, Board: (none), Villain: "TT+, AQ+". bet_to_call=20, pot=30 | Returns valid Decision |
| 4 | `test_full_via_flask_client` | `POST /api/analyze` with real API key, valid data | 200, valid JSON with all fields, action ∈ {FOLD,CALL,RAISE} | End-to-end through HTTP layer |

---

## 11. Implementation Order

### Phase 1: Core Data Layer
1. `constants.py` — rank/suit constants, RANK_ORDER list for comparisons.
2. `input_parser.py` — parse and validate all inputs.
3. `test_input_parser.py` — run tests, get green.

### Phase 2: Range Parser
4. `range_parser.py` — implement all range patterns.
5. `test_range_parser.py` — run tests, get green.

### Phase 3: Math Engine
6. `math_engine.py` — pot odds, SPR, MDF, outs, EV.
7. `test_math_engine.py` — run tests, get green.

### Phase 4: Equity Calculator
8. `equity.py` — Monte Carlo simulation with treys.
9. `test_equity.py` — run tests (use seed or wide tolerance).

### Phase 5: LLM Advisor
10. `advisor.py` — prompt builder, API call, response parser.
11. `test_advisor.py` — mocked tests, get green.

### Phase 6: Web UI
12. `app.py` — Flask routes (`GET /`, `POST /api/analyze`).
13. `templates/index.html` — single-page layout with card grid, form, results panel.
14. `static/css/style.css` — dark theme, card styling, responsive layout.
15. `static/js/app.js` — card picker state machine, form submission, result rendering.
16. `test_app.py` — Flask test client tests.

### Phase 7: Integration & Polish
17. `test_integration.py` — end-to-end with real API.
18. `README.md` — usage docs, screenshots.

---

## 12. Key Implementation Details

### 12.1 Card Conversion (treys)

```python
from treys import Card

# String to treys int
card = Card.new('Ah')

# Pretty print
Card.print_pretty_cards([Card.new('Ah'), Card.new('Kd')])
```

### 12.2 Hand Evaluation (treys)

```python
from treys import Evaluator

evaluator = Evaluator()
score = evaluator.evaluate(board, hand)  # Lower score = better hand
```

### 12.3 OpenRouter Call Pattern

```python
import requests
import os
from dotenv import load_dotenv

load_dotenv()

def call_llm(system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "anthropic/claude-3-haiku",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
```

### 12.4 Environment Setup

```bash
# .env.example
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx
```

---

## 13. Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Set up API key
cp .env.example .env
# Edit .env and paste your OpenRouter API key

# Run all unit tests (no API key needed)
pytest tests/ -v -m "not integration"

# Run integration tests (needs API key)
pytest tests/ -v -m integration

# Start the web UI
python -m pokerbot.app
# → opens at http://localhost:5000

# Or with debug mode
flask --app pokerbot.app run --debug --port 5000
```

---

## 14. Error Handling Strategy

| Error | Where | Handling |
|---|---|---|
| Invalid card string | `input_parser.py` | Raise `ValueError` with clear message |
| Duplicate cards | `input_parser.py` | Raise `ValueError` |
| Street/board mismatch | `input_parser.py` | Raise `ValueError` |
| Empty villain range | `range_parser.py` / `equity.py` | Raise `ValueError` |
| Invalid range syntax | `range_parser.py` | Raise `ValueError` with the bad token |
| OpenRouter API error | `advisor.py` | Return `Decision(action="ERROR")`, log error |
| API timeout (30s) | `advisor.py` | Return `Decision(action="ERROR")` |
| Missing API key | `advisor.py` | Raise `ValueError` at startup |
| treys evaluation error | `equity.py` | Log and skip that simulation iteration |

---

## 15. Future Enhancements (Out of Scope for v1)

- Multi-way pots (>1 opponent).
- Raise sizing optimizer (GTO-based).
- Hand history import (PokerStars / GGPoker format).
- Persistent session with hand-by-hand tracking.
- ICM calculations for tournament play.
- Implied odds & reverse implied odds in EV calc.
- Different LLM model selection via dropdown in UI.
- Caching equity results for identical scenarios.
- WebSocket for streaming LLM reasoning in real-time.
- Visual range matrix grid (13×13 with colour-coded combos) for villain range input.
- Drag-to-select card runs on the grid.
- Save / load hand histories in the browser (localStorage).
