// PokerBot Frontend Logic

const state = {
    mode: 'hole', // 'hole' | 'board'
    holeCards: [],
    boardCards: []
};

// Poker rules
const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
const SUITS = ['s', 'h', 'd', 'c'];
const SUIT_SYMBOLS = { 's': '♠', 'h': '♥', 'd': '♦', 'c': '♣' };

// DOM Elements
const elGrid = document.getElementById('card-grid');
const elHoleCount = document.getElementById('count-hole');
const elBoardCount = document.getElementById('count-board');
const elHoleSlots = document.getElementById('slots-hole');
const elBoardSlots = document.getElementById('slots-board');
const elStreet = document.getElementById('street');
const form = document.getElementById('game-form');

// Initialization
function init() {
    renderGrid();
    setupModeToggles();
    setupForm();
    document.getElementById('clear-btn').addEventListener('click', clearAll);
}

// ── Card Picker Logic ────────────────────────────────────────────────

function renderGrid() {
    elGrid.innerHTML = '';
    
    SUITS.forEach(suit => {
        RANKS.forEach(rank => {
            const cardStr = `${rank}${suit}`;
            const btn = document.createElement('div');
            btn.className = 'playing-card';
            btn.dataset.card = cardStr;
            btn.dataset.suit = suit;
            btn.innerHTML = `${rank}<br>${SUIT_SYMBOLS[suit]}`;
            
            // State styling
            if (state.holeCards.includes(cardStr)) {
                btn.classList.add('selected-hole');
            } else if (state.boardCards.includes(cardStr)) {
                btn.classList.add('selected-board');
            } else {
                // If the card isn't picked, but we are in a mode that's full,
                // we technically can't pick it for that mode. But we handle that on click.
                // However, if it's in the *other* list, we disable it.
            }

            btn.addEventListener('click', () => handleCardClick(cardStr));
            elGrid.appendChild(btn);
        });
    });
}

function handleCardClick(cardStr) {
    // 1. If already in hole -> remove
    if (state.holeCards.includes(cardStr)) {
        state.holeCards = state.holeCards.filter(c => c !== cardStr);
        updateUI();
        return;
    }
    // 2. If already in board -> remove
    if (state.boardCards.includes(cardStr)) {
        state.boardCards = state.boardCards.filter(c => c !== cardStr);
        updateUI();
        return;
    }

    // 3. Add to current mode if space available
    if (state.mode === 'hole') {
        if (state.holeCards.length < 2) {
            state.holeCards.push(cardStr);
        }
    } else {
        if (state.boardCards.length < 5) {
            state.boardCards.push(cardStr);
        }
    }
    
    updateUI();
}

function updateUI() {
    // Update Counts
    elHoleCount.textContent = state.holeCards.length;
    elBoardCount.textContent = state.boardCards.length;

    // Auto-set street
    const bc = state.boardCards.length;
    if (bc === 0) elStreet.value = 'preflop';
    else if (bc === 3) elStreet.value = 'flop';
    else if (bc === 4) elStreet.value = 'turn';
    else if (bc === 5) elStreet.value = 'river';
    else elStreet.value = 'Invalid (needs 0,3,4,5)';

    // Re-render grid to update colors/disabled states
    renderGrid();

    // Render Slots
    renderSlots(elHoleSlots, state.holeCards, 'hole');
    renderSlots(elBoardSlots, state.boardCards, 'board');
}

function renderSlots(container, cards, typeClass) {
    container.innerHTML = '';
    if (cards.length === 0) {
        container.innerHTML = '<span style="color:#64748b;font-size:14px;padding:4px">None</span>';
        return;
    }
    
    cards.forEach(cardStr => {
        const rank = cardStr[0];
        const suit = cardStr[1];
        const el = document.createElement('div');
        el.className = `mini-card ${typeClass}`;
        el.dataset.suit = suit;
        el.innerHTML = `${rank}${SUIT_SYMBOLS[suit]}`;
        // Click slot to deselect
        el.addEventListener('click', () => handleCardClick(cardStr));
        container.appendChild(el);
    });
}

function setupModeToggles() {
    document.querySelectorAll('input[name="pick-mode"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            state.mode = e.target.value;
            document.querySelectorAll('.mode-toggle').forEach(l => l.classList.remove('active'));
            e.target.closest('.mode-toggle').classList.add('active');
        });
    });
}

function clearAll() {
    state.holeCards = [];
    state.boardCards = [];
    state.mode = 'hole';
    
    // Reset toggle UI
    document.getElementById('mode-hole').querySelector('input').checked = true;
    document.querySelectorAll('.mode-toggle').forEach(l => l.classList.remove('active'));
    document.getElementById('mode-hole').classList.add('active');
    
    // Reset form
    form.reset();
    
    // Hide results
    document.getElementById('results-section').classList.add('hidden');
    
    updateUI();
}

// ── Form Submission & API ────────────────────────────────────────────

function setupForm() {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Client validation
        if (state.holeCards.length !== 2) {
            showError("Please select exactly 2 hole cards.");
            return;
        }
        const bc = state.boardCards.length;
        if (bc !== 0 && bc !== 3 && bc !== 4 && bc !== 5) {
            showError("Board must have 0, 3, 4, or 5 cards.");
            return;
        }

        const payload = {
            hole_cards: state.holeCards,
            board: state.boardCards,
            pot: parseFloat(document.getElementById('pot').value),
            bet_to_call: parseFloat(document.getElementById('bet_to_call').value),
            my_stack: parseFloat(document.getElementById('my_stack').value),
            opp_stack: parseFloat(document.getElementById('opp_stack').value),
            position: document.getElementById('position').value,
            villain_range: document.getElementById('villain_range').value
        };

        // Show loading
        const resultsSec = document.getElementById('results-section');
        const spinner = document.getElementById('spinner');
        const content = document.getElementById('results-content');
        const errorBox = document.getElementById('error-message');
        
        resultsSec.classList.remove('hidden');
        spinner.classList.remove('hidden');
        content.classList.add('hidden');
        errorBox.classList.add('hidden');

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            
            if (!data.success) {
                showError(data.error);
                return;
            }

            // Populate Metrics
            document.getElementById('val-pot-odds').textContent = data.metrics.pot_odds_pct + '%';
            document.getElementById('val-spr').textContent = data.metrics.spr === null ? '∞' : data.metrics.spr;
            document.getElementById('val-mdf').textContent = data.metrics.mdf + '%';
            document.getElementById('val-outs').textContent = data.metrics.outs === -1 ? 'N/A' : data.metrics.outs;
            document.getElementById('val-equity').textContent = data.metrics.equity_pct + '%';
            
            const ev = data.metrics.ev_call;
            const evEl = document.getElementById('val-ev');
            evEl.textContent = (ev > 0 ? '+' : '') + ev;
            evEl.style.color = ev > 0 ? 'var(--btn-success)' : (ev < 0 ? 'var(--btn-danger)' : 'inherit');

            // Populate Decision
            const actionEl = document.getElementById('val-action');
            actionEl.textContent = data.decision.action;
            
            // Badge color
            actionEl.style.background = 'var(--border)'; // default
            if (data.decision.action === 'FOLD') actionEl.style.background = 'var(--btn-danger)';
            if (data.decision.action === 'CALL') actionEl.style.background = 'var(--btn-warning)';
            if (data.decision.action === 'RAISE') actionEl.style.background = 'var(--btn-success)';

            document.getElementById('val-size').textContent = data.decision.raise_size;
            document.getElementById('val-conf').textContent = data.decision.confidence;
            document.getElementById('val-reasoning').textContent = data.decision.reasoning;

            // Show results
            spinner.classList.add('hidden');
            content.classList.remove('hidden');

        } catch (err) {
            showError("Network error. Is the server running?");
        }
    });
}

function showError(msg) {
    document.getElementById('results-section').classList.remove('hidden');
    document.getElementById('spinner').classList.add('hidden');
    document.getElementById('results-content').classList.add('hidden');
    
    const err = document.getElementById('error-message');
    err.textContent = msg;
    err.classList.remove('hidden');
}

// Start
init();
