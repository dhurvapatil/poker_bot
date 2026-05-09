// PokerBot Full-Hand Phase 1 Frontend Logic

const state = {
    mode: 'hole',
    holeCards: [],
    boardCards: [],
    actions: [],
    lastHandState: null
};

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
const SUITS = ['s', 'h', 'd', 'c'];
const SUIT_SYMBOLS = { s: '♠', h: '♥', d: '♦', c: '♣' };

const elGrid = document.getElementById('card-grid');
const elHoleCount = document.getElementById('count-hole');
const elBoardCount = document.getElementById('count-board');
const elHoleSlots = document.getElementById('slots-hole');
const elBoardSlots = document.getElementById('slots-board');
const form = document.getElementById('game-form');

function init() {
    renderGrid();
    setupModeToggles();
    setupForm();
    document.getElementById('clear-btn').addEventListener('click', clearAll);
    setupActionBuilder();
    document.getElementById('analyze-full-hand-btn').addEventListener('click', analyzeFullHand);
    updateUI();
}

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

            if (state.holeCards.includes(cardStr)) {
                btn.classList.add('selected-hole');
            } else if (state.boardCards.includes(cardStr)) {
                btn.classList.add('selected-board');
            }

            btn.addEventListener('click', () => handleCardClick(cardStr));
            elGrid.appendChild(btn);
        });
    });
}

function handleCardClick(cardStr) {
    if (state.holeCards.includes(cardStr)) {
        state.holeCards = state.holeCards.filter(c => c !== cardStr);
    } else if (state.boardCards.includes(cardStr)) {
        state.boardCards = state.boardCards.filter(c => c !== cardStr);
    } else if (state.mode === 'board') {
        if (state.boardCards.length < 5) state.boardCards.push(cardStr);
    } else if (state.holeCards.length < 2) {
        state.holeCards.push(cardStr);
    }
    updateUI();
}

function updateUI() {
    elHoleCount.textContent = state.holeCards.length;
    if (elBoardCount) elBoardCount.textContent = state.boardCards.length;
    renderGrid();
    renderSlots(elHoleSlots, state.holeCards, 'hole');
    if (elBoardSlots) renderSlots(elBoardSlots, state.boardCards, 'board');
    updateBoardStreetDisplays();
}

function updateBoardStreetDisplays() {
    const flop = state.boardCards.slice(0, 3).join(' ') || 'Select 3 board cards';
    const turn = state.boardCards.slice(3, 4).join(' ') || 'Select 1 turn card';
    const river = state.boardCards.slice(4, 5).join(' ') || 'Select 1 river card';
    document.getElementById('flop-display').textContent = flop;
    document.getElementById('turn-display').textContent = turn;
    document.getElementById('river-display').textContent = river;
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
    state.actions = [];
    state.lastHandState = null;
    form.reset();
    hideError();
    clearPreview();
    updateUI();
}

function setupForm() {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await previewStartingState();
    });
}

function buildFullHandPayload() {
    return {
        setup: {
            hero_position: document.getElementById('position').value,
            hero_stack_bb: parseFloat(document.getElementById('hero_stack_bb').value),
            villain_stack_bb: parseFloat(document.getElementById('villain_stack_bb').value),
            villain_profile: document.getElementById('villain_profile').value,
            hero_hole_cards: state.holeCards
        },
        board: {
            flop: state.boardCards.slice(0, 3),
            turn: state.boardCards.slice(3, 4),
            river: state.boardCards.slice(4, 5)
        },
        actions: state.actions
    };
}

async function previewStartingState() {
    if (state.holeCards.length !== 2) {
        showError('Please select exactly 2 hero hole cards.');
        return;
    }

    const payload = buildFullHandPayload();

    try {
        const response = await fetch('/api/full_hand/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!data.success) {
            showError(data.error);
            return;
        }
        hideError();
        renderPreview(data.hand_state);
        renderTimeline();
        updateActionButtons(data.hand_state);
    } catch (err) {
        showError('Network error. Is the server running?');
    }
}

function setupActionBuilder() {
    document.getElementById('action-fold').addEventListener('click', () => addAction('fold'));
    document.getElementById('action-check').addEventListener('click', () => addAction('check'));
    document.getElementById('action-call').addEventListener('click', () => addAction('call'));
    document.getElementById('action-bet').addEventListener('click', () => addAction('bet'));
    document.getElementById('action-raise').addEventListener('click', () => addAction('raise'));
    updateActionButtons(null);
}

async function addAction(type) {
    if (!state.lastHandState || !state.lastHandState.legal_actions.includes(type)) return;
    const actor = state.lastHandState.current_actor;
    const action = { actor, type };
    if (state.lastHandState.street !== 'preflop') action.street = state.lastHandState.street;
    if (type === 'raise') {
        const raiseTo = parseFloat(document.getElementById('raise_to_bb').value);
        const heroPosition = document.getElementById('position').value;
        const contribution = state.lastHandState.street === 'preflop'
            ? (actor === 'hero'
                ? (heroPosition === 'BB' ? 1.0 : 0.5)
                : (heroPosition === 'BB' ? 0.5 : 1.0))
            : 0.0;
        action.amount_added = raiseTo - contribution;
        action.input_mode = 'raise_to';
        action.input_amount = raiseTo;
    }
    if (type === 'bet') {
        action.amount_added = parseFloat(document.getElementById('raise_to_bb').value);
    }
    if (document.getElementById('all_in_toggle').checked) action.all_in = true;
    state.actions.push(action);
    await previewStartingState();
}

async function analyzeFullHand() {
    if (state.holeCards.length !== 2) {
        showError('Please select exactly 2 hero hole cards.');
        return;
    }
    try {
        const response = await fetch('/api/analyze_full_hand', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(buildFullHandPayload())
        });
        const data = await response.json();
        if (!data.success) {
            showError(data.error);
            return;
        }
        hideError();
        document.getElementById('range-analysis-output').textContent = `${data.range_analysis.estimated_range} (${data.range_analysis.confidence})`;
        document.getElementById('math-output').textContent = `Equity ${data.metrics.equity_pct}%, Pot odds ${data.metrics.pot_odds_pct}%, EV call ${data.metrics.ev_call}bb`;
        document.getElementById('decision-output').textContent = `${data.decision.action}: ${data.decision.reasoning}`;
    } catch (err) {
        showError('Network error. Is the server running?');
    }
}

function renderPreview(handState) {
    state.lastHandState = handState;
    document.getElementById('val-pot').textContent = `${handState.pot_bb}bb`;
    document.getElementById('val-hero-stack').textContent = `${handState.hero_stack_bb}bb`;
    document.getElementById('val-villain-stack').textContent = `${handState.villain_stack_bb}bb`;
    document.getElementById('val-current-actor').textContent = handState.current_actor === 'hero' ? 'Hero' : 'Villain';
    document.getElementById('val-street').textContent = handState.street;
    document.getElementById('val-legal-actions').textContent = handState.legal_actions.join(', ');
}

function renderTimeline() {
    const timeline = document.getElementById('action-timeline');
    if (!state.actions.length) {
        timeline.innerHTML = '<span style="color:#64748b;font-size:14px;padding:4px">No actions yet</span>';
        return;
    }
    timeline.innerHTML = '<strong>Preflop</strong>' + state.actions.map(action => {
        const actor = action.actor === 'hero' ? 'Hero' : 'Villain';
        const street = action.street ? `${action.street}: ` : 'preflop: ';
        if (action.type === 'raise') return `<div>${street}${actor} raises to ${action.input_amount}bb</div>`;
        if (action.type === 'bet') return `<div>${street}${actor} bets ${action.amount_added}bb</div>`;
        return `<div>${street}${actor} ${action.type}s</div>`;
    }).join('');
}

function updateActionButtons(handState) {
    ['fold', 'check', 'call', 'bet', 'raise'].forEach(type => {
        const button = document.getElementById(`action-${type}`);
        button.disabled = !handState || !handState.legal_actions.includes(type);
    });
    const status = document.getElementById('builder-status');
    status.textContent = handState ? (handState.disabled_reason || `${handState.current_actor === 'hero' ? 'Hero' : 'Villain'} to act`) : 'Preview setup to begin building preflop actions.';
}

function clearPreview() {
    ['val-pot', 'val-hero-stack', 'val-villain-stack', 'val-current-actor', 'val-legal-actions'].forEach(id => {
        document.getElementById(id).textContent = '-';
    });
    document.getElementById('val-street').textContent = 'preflop';
    renderTimeline();
    updateActionButtons(null);
}

function showError(msg) {
    const err = document.getElementById('error-message');
    err.textContent = msg;
    err.classList.remove('hidden');
}

function hideError() {
    const err = document.getElementById('error-message');
    err.textContent = '';
    err.classList.add('hidden');
}

init();
