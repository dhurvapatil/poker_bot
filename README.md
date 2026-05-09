# 🃏 PokerBot Full-Hand Advisor

An advanced, agentic Texas Hold'em poker assistant that lets you build and analyze complete hand timelines from preflop through river. PokerBot takes your full hand scenario (hole cards, position, stack sizes, action history, board by street) and computes all complex poker mathematics instantly. It then feeds these precise metrics into an AI model (via OpenRouter) to give you a definitive **FOLD, CALL, or RAISE** decision with step-by-step strategic reasoning.

## ✨ Features

* **Interactive Web UI:** A sleek, dark-themed single-page application with a visual 52-card picker.
* **Complete Hand Timeline Builder:** Build entire hands from preflop → flop → turn → river with full action history. Analyze at any decision point.
* **Street-by-Street Board Selection:** Select flop (3 cards), turn (1 card), and river (1 card) separately as the hand develops.
* **Heads-Up Position Support:** Choose BTN/SB or BB as your position; blinds are posted automatically.
* **Villain Profile System:** Select opponent types (Nit, Tight Passive, Loose Aggressive, Maniac, etc.) to get tailored range estimates.
* **Action Timeline:** Add fold, check, call, bet, and raise actions for each player at each street. The system validates all actions are legal.
* **Monte Carlo Equity Calculator:** Uses the lightning-fast `treys` library to run thousands of simulations and determine your exact win probability against the estimated villain range.
* **Advanced Math Engine:** Automatically calculates:
  * **Pot Odds** (%)
  * **SPR** (Stack-to-Pot Ratio)
  * **MDF** (Minimum Defense Frequency)
  * **Outs** (Detects flush draws, open-ended straight draws, gutshots, overcards, and made-hand improvements)
  * **EV** (Expected Value of calling in chips)
* **LLM Integration:** Connects to OpenRouter (defaults to `moonshotai/kimi-k2-thinking`) to analyze the math and provide human-like poker strategy.
* **Extensive Range Parser:** Supports standard poker syntax for villain ranges (e.g., `TT+, AKs, ATo+, 88-55`).

---

## 🚀 Installation & Setup

1. **Install Dependencies**
   Ensure you have Python 3.10+ installed, then run:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure your API Key**
   The bot uses OpenRouter to access advanced LLMs. 
   * Copy the `.env.example` file to `.env`:
     ```bash
     cp .env.example .env
     ```
   * Open `.env` and paste your OpenRouter API key. Get one at [https://openrouter.ai/keys](https://openrouter.ai/keys).

---

## 🎮 Running the Application

Start the Flask web server:

```bash
flask --app pokerbot.app run --debug --port 5000
```
*(Or simply run `python -m pokerbot.app` if you configured the execution block).*

Then, open your web browser and navigate to:
**http://localhost:5000**

### How to use the UI:

#### Step 1: Setup
1. **Select Hero Cards:** Click to select exactly 2 Hole Cards using the card picker.
2. **Choose Position:** Select BTN/SB (Button/Small Blind) or BB (Big Blind).
3. **Choose Villain Profile:** Select your opponent's tendency (Unknown, Nit, Tight Passive, Loose Aggressive, Maniac, etc.).
4. **Set Stack Sizes:** Enter your stack and villain's stack in big blinds.
5. **Preview:** Click "Preview Starting State" to see the auto-posted blinds and initial game state.

#### Step 2: Build the Hand Timeline
1. **Preflop Actions:** Use the action buttons (Fold, Check, Call, Bet, Raise) to build the preflop action. The timeline updates automatically.
2. **Add Board Cards:** Once preflop is complete, select flop, turn, and river cards using the board card picker.
3. **Postflop Actions:** Continue adding actions at each street (flop, turn, river) using the action builder.
4. **View Timeline:** The action timeline shows the complete hand history.

#### Step 3: Analyze
1. **Reach a Decision Point:** Build the hand until it's your turn to act (Hero is to act).
2. **Analyze:** Click "Analyze Full Hand" to run the Monte Carlo simulation and consult the LLM.
3. **Review Results:** See the range analysis, poker math (equity, pot odds, SPR, MDF, outs, EV), and get your final FOLD/CALL/RAISE decision with reasoning.

---

## 🧪 Running the Tests

The project includes a comprehensive test suite verifying the math engine, range parsing, hand state derivation, and web routing.

To run the offline unit tests (runs instantly, no API key required):
```bash
python -m pytest tests/ -v -m "not integration"
```

To run the end-to-end integration tests (requires your `.env` API key, actually talks to the LLM):
```bash
python -m pytest tests/test_integration.py -v
```

---

## 📂 Project Structure

```text
pokerbot/
├── pokerbot/
│   ├── app.py              # Flask Web Server & API routes (analyze, full_hand preview/analyze)
│   ├── advisor.py          # OpenRouter LLM prompting & parsing
│   ├── equity.py           # Monte Carlo simulation (treys)
│   ├── math_engine.py      # Outs, Pot Odds, SPR, MDF, EV math
│   ├── hand_state.py       # Full-hand timeline state derivation & validation
│   ├── range_parser.py     # Converts "AKs, TT+" into card combos
│   ├── range_advisor.py    # Villain range estimation based on profile
│   ├── preflop_ranges.py   # Baseline preflop ranges for full-hand analysis
│   ├── input_parser.py     # Formats and validates web inputs
│   └── constants.py        # Card, position, and street definitions
├── static/
│   ├── css/style.css       # UI Styling
│   └── js/app.js           # Frontend logic, card picker, action builder
├── templates/
│   └── index.html          # Main application layout
├── tests/                  # Pytest suite (120+ tests)
├── requirements.txt        # Python dependencies
└── plan.md                 # Original architecture spec
```