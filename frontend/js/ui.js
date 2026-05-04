// ============================================================
// ui.js — Render poker table, cards, seats, animations
// ============================================================
window.PokerUI = (() => {
  'use strict';
  const E = window.PokerEngine;

  let godMode = false;

  function getEl(id) { return document.getElementById(id); }

  function renderTable(game) {
    renderCommunityCards(game);
    renderSeats(game);
    renderPot(game);
    renderPhaseDots(game);
    renderGodModeBar();
    renderActionButtons(game);
  }

  function renderCommunityCards(game) {
    const container = getEl('community-cards');
    container.innerHTML = '';
    const cards = game.communityCards;
    for (let i = 0; i < 5; i++) {
      if (i < cards.length) {
        container.appendChild(createCardEl(cards[i], false, i === cards.length - 1));
      } else {
        const placeholder = document.createElement('div');
        placeholder.className = 'card back small';
        placeholder.style.opacity = '0.3';
        container.appendChild(placeholder);
      }
    }
  }

  function createCardEl(card, isHole, animate) {
    const el = document.createElement('div');
    const red = E.isRed(card) ? ' red' : '';
    el.className = `card${red}${animate ? ' dealing' : ''}`;

    const rank = document.createElement('span');
    rank.className = 'rank';
    rank.textContent = E.RANK_NAMES[card.rank];

    const suit = document.createElement('span');
    suit.className = 'suit';
    suit.textContent = E.SUIT_SYMBOLS[card.suit];

    el.appendChild(rank);
    el.appendChild(suit);
    return el;
  }

  function createCardBack() {
    const el = document.createElement('div');
    el.className = 'card back';
    return el;
  }

  function renderSeats(game) {
    const container = getEl('seats-container');
    container.innerHTML = '';

    const n = game.players.length;
    const tableEl = getEl('table-container');
    const tableW = tableEl.clientWidth;
    const tableH = tableEl.clientHeight;
    const cx = tableW / 2;
    const cy = tableH / 2;
    const rx = tableW * 0.38;
    const ry = tableH * 0.38;

    for (let i = 0; i < n; i++) {
      const p = game.players[i];
      if (p.status === 'out') continue;

      const relPos = (i - game.dealerIdx + n) % n;
      const angle = (relPos / n) * Math.PI * 2 - Math.PI / 2;

      const x = cx + Math.cos(angle) * rx - 30;
      const y = cy + Math.sin(angle) * ry - 30;

      const seat = document.createElement('div');
      seat.className = 'player-seat';
      if (i === game.currentIdx && p.status === 'active') seat.classList.add('active-seat');
      if (p.status === 'folded') seat.classList.add('folded');
      if (p.isHuman) seat.classList.add('human-seat');
      seat.style.left = x + 'px';
      seat.style.top = y + 'px';

      // Dealer button
      if (i === game.dealerIdx) {
        const db = document.createElement('div');
        db.className = 'dealer-btn';
        db.textContent = 'D';
        seat.appendChild(db);
      }

      // Player info
      const info = document.createElement('div');
      info.className = 'player-info';
      const posName = window.PokerAI ? window.PokerAI.getPosName(game, i) : '';
      info.innerHTML = `
        <div class="name">${p.isHuman ? '⭐ 你' : p.name} <span style="font-size:0.55rem;color:var(--text-dim)">${posName.toUpperCase()}</span></div>
        <div class="stack">${p.stack} 筹码</div>
        ${p.lastAction ? `<span class="action-badge ${getActionClass(p.lastAction)}">${p.lastAction}</span>` : ''}
      `;
      seat.appendChild(info);

      // Cards
      const cardsDiv = document.createElement('div');
      cardsDiv.className = 'player-cards';
      if (p.holeCards.length > 0) {
        for (const card of p.holeCards) {
          if (godMode || p.isHuman) {
            cardsDiv.appendChild(createCardEl(card, true, false));
          } else {
            cardsDiv.appendChild(createCardBack());
          }
        }
      }
      seat.appendChild(cardsDiv);

      // Equity glow in god mode
      if (godMode && p.holeCards.length > 0 && !p.isHuman && p.status !== 'folded') {
        const str = E.quickEquity(p.holeCards, game.communityCards);
        if (str.strength > 70) {
          cardsDiv.querySelectorAll('.card').forEach(c => c.classList.add('equity-high'));
        }
      }

      container.appendChild(seat);
    }
  }

  function getActionClass(action) {
    if (/Fold/i.test(action)) return 'fold';
    if (/Call/i.test(action)) return 'call';
    if (/Raise|Bet/i.test(action)) return 'raise';
    if (/All-in/i.test(action)) return 'allin';
    if (/Check/i.test(action)) return 'check';
    return '';
  }

  function renderPot(game) {
    const pot = game.players.reduce((s, p) => s + p.currentBet, 0);
    getEl('pot-display').textContent = `底池: ${pot}`;
  }

  function renderPhaseDots(game) {
    const phases = ['preflop', 'flop', 'turn', 'river'];
    const dots = getEl('phase-dots').querySelectorAll('.phase-dot');
    const currentIdx = phases.indexOf(game.phase);
    dots.forEach((dot, i) => {
      dot.className = 'phase-dot';
      if (i < currentIdx) dot.classList.add('done');
      if (i === currentIdx) dot.classList.add('lit');
    });
  }

  function renderGodModeBar() {
    const bar = getEl('god-mode-bar');
    bar.className = godMode ? 'visible' : '';
  }

  function isGodMode() { return godMode; }
  function toggleGodMode() {
    godMode = !godMode;
    const btn = getEl('btn-god');
    btn.className = 'btn' + (godMode ? ' active' : '');
    if (window.App) window.App.refreshUI();
    showToast(godMode ? '上帝模式: 显示所有底牌 & 胜率' : '上帝模式已关闭');
  }

  function renderActionButtons(game) {
    const humanPlayer = game.players.find(p => p.isHuman);
    if (!humanPlayer || humanPlayer.status !== 'active') {
      disableAllButtons();
      return;
    }
    const legal = E.getLegalActions(game, game.players.indexOf(humanPlayer));
    const can = {};
    for (const a of legal) can[a.type] = a;

    const btnFold = getEl('btn-fold');
    const btnCheck = getEl('btn-check');
    const btnCall = getEl('btn-call');
    const btnRaise = getEl('btn-raise');
    const btnAllin = getEl('btn-allin');

    btnFold.disabled = !can.fold;
    btnCheck.disabled = !can.check;
    btnCall.disabled = !can.call;
    btnRaise.disabled = !can.raise && !can.bet;
    btnAllin.disabled = !can.allin;

    if (can.call) btnCall.textContent = `跟注 ${can.call.amount}`;
    else btnCall.textContent = '跟注';

    if (can.raise) {
      const slider = getEl('bet-slider');
      slider.min = can.raise.min || game.minRaise;
      slider.max = Math.min(can.raise.max || humanPlayer.stack, humanPlayer.stack);
      slider.value = Math.min(slider.max, Math.max(slider.min, can.raise.min || game.minRaise));
      updateBetSlider();
    } else if (can.bet) {
      const slider = getEl('bet-slider');
      slider.min = can.bet.min || game.bb;
      slider.max = Math.min(can.bet.max || humanPlayer.stack, humanPlayer.stack);
      slider.value = Math.min(slider.max, slider.min);
      updateBetSlider();
    }
  }

  function disableAllButtons() {
    ['btn-fold','btn-check','btn-call','btn-raise','btn-allin'].forEach(id => {
      const btn = getEl(id);
      if (btn) btn.disabled = true;
    });
  }

  function updateBetSlider() {
    const slider = getEl('bet-slider');
    getEl('bet-amount').textContent = slider.value;
  }

  function showToast(msg, duration = 2000) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const el = document.createElement('div');
    el.className = 'toast';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), duration);
  }

  return {
    renderTable, renderActionButtons, updateBetSlider,
    showToast, toggleGodMode, isGodMode, disableAllButtons,
    createCardEl, createCardBack,
  };
})();
