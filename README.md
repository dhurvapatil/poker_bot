# 🃏 PokerBot Advisor

An advanced, agentic Texas Hold'em poker assistant. PokerBot takes in your current game state (hole cards, board, stack sizes, and your opponent's perceived range) and computes all complex poker mathematics instantly. It then feeds these precise metrics into an AI model (via OpenRouter) to give you a definitive **FOLD, CALL, or RAISE** decision with step-by-step strategic reasoning.

## ✨ Features

* **Interactive Web UI:** A sleek, dark-themed single-page application with a visual 52-card picker.
* **Monte Carlo Equity Calculator:** Uses the lightning-fast `treys` library to run thousands of simulations and determine your exact win probability against a specific villain range.
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
1. **Select Cards:** Click to select exactly 2 Hole Cards. Toggle the mode to "Board" and select 0, 3, 4, or 5 community cards.
2. **Fill Game State:** Enter the Pot Size, Bet to Call, and Stack Sizes.
3. **Villain Range:** Enter your opponent's perceived range using standard poker notation.
   * *Examples:* `QQ+` (Queens or better), `AKs` (Suited Ace-King), `88-55` (Pocket eights down to fives), `AT+` (Any Ace-Ten or better).
4. **Analyze:** Click "Analyze Hand" to run the Monte Carlo simulation and consult the LLM.

---

## 🧪 Running the Tests

The project includes a massive test suite (120+ tests) verifying the math engine, range parsing, and web routing.

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
│   ├── app.py              # Flask Web Server & API route
│   ├── advisor.py          # OpenRouter LLM prompting & parsing
│   ├── equity.py           # Monte Carlo simulation (treys)
│   ├── math_engine.py      # Outs, Pot Odds, SPR, MDF, EV math
│   ├── range_parser.py     # Converts "AKs, TT+" into card combos
│   ├── input_parser.py     # Formats and validates web inputs
│   └── constants.py        # Card and street definitions
├── static/
│   ├── css/style.css       # UI Styling
│   └── js/app.js           # Frontend logic & card picker
├── templates/
│   └── index.html          # Main application layout
├── tests/                  # Pytest suite
├── requirements.txt        # Python dependencies
└── plan.md                 # Original architecture spec
```