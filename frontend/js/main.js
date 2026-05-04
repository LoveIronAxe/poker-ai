// ============================================================
// main.js — App controller, game loop, rewind, settings, storage
// ============================================================
window.App = (() => {
  'use strict';
  const E = window.PokerEngine;
  const AI = window.PokerAI;
  const UI = window.PokerUI;
  const Timeline = window.PokerTimeline;
  const Review = window.PokerReview;

  // ── State ──
  let game = null;
  let humanIdx = 0;
  let aiDifficulty = AI.DIFFICULTY.MEDIUM;
  let reviewVisible = false;
  let settingsVisible = false;
  let autoPlayTimer = null;

  // ── Init ──
  function init() {
    const params = new URLSearchParams(window.location.search);

    // Read config from URL params (set by dashboard) or use defaults
    aiDifficulty = parseInt(params.get('difficulty')) || 2;
    const numPlayers = parseInt(params.get('opponents')) || 6;
    const stackSize = parseInt(params.get('stack')) || 1000;
    const godMode = params.get('god') === '1';
    const coachMode = params.get('coach') === '1';
    const autoReview = params.get('autoReview') === '1';

    // Keep auto-review setting across newHand calls
    if (autoReview) reviewVisible = true;

    // Load saved profile
    loadSettings();

    // Create game with configured settings
    const stacks = Array(numPlayers).fill(stackSize);
    game = E.createGame(numPlayers, 1, 2, stacks);
    game.players[0].isHuman = true;
    game.players[0].name = (E.getUserProfile().nickname) || '你';
    const aiNames = ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'India'];
    for (let i = 1; i < numPlayers; i++) {
      game.players[i].name = aiNames[i - 1] || `AI-${i}`;
    }

    // Apply god mode if configured
    if (godMode) {
      UI.toggleGodMode();
    }

    // Show coach badge if active
    if (coachMode && document.getElementById('god-mode-bar')) {
      document.getElementById('god-mode-bar').textContent = '🎓 AI 教练模式 — 实时提示 & 胜率分析';
      document.getElementById('god-mode-bar').style.display = 'block';
    }

    newHand();
  }

  function newHand() {
    if (autoPlayTimer) { clearTimeout(autoPlayTimer); autoPlayTimer = null; }
    const started = E.startNewHand(game);
    if (!started) {
      UI.showToast('游戏结束！重新开始');
      const n = game.numPlayers;
      const stacks = Array(n).fill(1000);
      game = E.createGame(n, 1, 2, stacks);
      game.players[0].isHuman = true;
      game.players[0].name = (E.getUserProfile().nickname) || '你';
      for (let i = 1; i < n; i++) {
        game.players[i].name = ['Alpha','Bravo','Charlie','Delta','Echo','Foxtrot','Golf','Hotel','India'][i-1] || `AI-${i}`;
      }
      E.startNewHand(game);
    }
    document.getElementById('review-panel').classList.remove('visible');
    humanIdx = game.players.findIndex(p => p.isHuman);
    refreshUI();
    if (game.players[game.currentIdx] && !game.players[game.currentIdx].isHuman) {
      scheduleAITurn();
    }
  }

  // ── Player Action ──
  function playerAction(type) {
    if (!game || game.phase === 'idle' || game.phase === 'showdown') return;
    const human = game.players.find(p => p.isHuman);
    if (!human || human.status !== 'active') return;
    if (game.currentIdx !== game.players.indexOf(human)) return;

    const legal = E.getLegalActions(game, game.players.indexOf(human));
    const action = legal.find(a => a.type === type);
    if (!action) { UI.showToast('无效操作'); return; }

    if (type === 'raise') {
      const slider = document.getElementById('bet-slider');
      action.amount = parseInt(slider.value) || action.min;
    }
    if (type === 'bet') {
      const slider = document.getElementById('bet-slider');
      action.amount = parseInt(slider.value) || action.min;
    }

    const result = E.applyAction(game, game.players.indexOf(human), action);
    refreshUI();
    handleActionResult(result);
  }

  function updateBetSlider() {
    UI.updateBetSlider();
  }

  // ── AI Turn ──
  function scheduleAITurn() {
    if (autoPlayTimer) clearTimeout(autoPlayTimer);
    autoPlayTimer = setTimeout(executeAITurn, 400 + Math.random() * 400);
  }

  function executeAITurn() {
    if (!game || game.phase === 'idle' || game.phase === 'showdown') return;
    const current = game.players[game.currentIdx];
    if (!current || current.status !== 'active' || current.isHuman) return;

    try {
      const action = AI.decide(game, game.currentIdx, aiDifficulty);
      let resolvedAction = action;

      // Match to legal actions
      const legal = E.getLegalActions(game, game.currentIdx);
      if (!legal || !legal.length) {
        // No legal actions — skip to next player
        const result = E.applyAction(game, game.currentIdx, { type: 'fold', amount: 0 });
        refreshUI();
        handleActionResult(result.result || result);
        return;
      }
      const match = legal.find(a => a.type === action.type);
      if (!match) {
        resolvedAction = legal[0]; // fallback
      } else if (action.type === 'raise' || action.type === 'bet') {
        resolvedAction = match;
        if (action.amount) {
          resolvedAction.amount = Math.max(match.min || 0, Math.min(action.amount, match.max || Infinity));
        }
      } else {
        resolvedAction = match;
      }

      if (!resolvedAction) { resolvedAction = legal[0]; }

      const result = E.applyAction(game, game.currentIdx, resolvedAction);
      refreshUI();

      if (result === 'hand_over' || game.phase === 'idle') {
        onHandComplete();
      } else if (game.players[game.currentIdx] && !game.players[game.currentIdx].isHuman) {
        scheduleAITurn();
      }
    } catch (e) {
      console.error('AI turn error:', e);
      // Try to recover: skip to next active player or advance phase
      const legal = E.getLegalActions(game, game.currentIdx);
      if (legal && legal.length > 0) {
        E.applyAction(game, game.currentIdx, legal[0]);
      }
      refreshUI();
    }
  }

  function handleActionResult(result) {
    if (result === 'hand_over' || game.phase === 'idle') {
      onHandComplete();
    } else if (game.phase !== 'showdown') {
      if (game.players[game.currentIdx] && !game.players[game.currentIdx].isHuman) {
        scheduleAITurn();
      }
    }
  }

  function onHandComplete() {
    // Always generate review and attach to history
    const review = Review.reviewHand(game, humanIdx);
    E.attachReviewToHistory(review);

    if (reviewVisible) {
      Review.renderReview(review);
      Review.drawRadar('radar-canvas', review.dimensions);
    }
    Timeline.render(game);
    UI.showToast('本局结束 — 点击复盘查看分析', 3000);
  }

  // ── Rewind System ──
  function rewindTo(snapIdx) {
    if (!game || snapIdx < 0 || snapIdx >= game.history.length) return;
    if (autoPlayTimer) { clearTimeout(autoPlayTimer); autoPlayTimer = null; }

    E.restoreSnapshot(game, snapIdx);

    // Set all non-folded, non-out players to active or waiting
    for (const p of game.players) {
      if (p.status === 'out') continue;
      if (p.status === 'folded') continue;
      // Reset status based on phase
      if (game.phase === 'preflop' && p.roundBet > 0 && p.roundBet === game.currentBet) {
        p.status = 'active'; // Has matched current bet
      } else {
        p.status = 'active';
      }
    }

    refreshUI();
    UI.showToast(`已回溯到第 ${snapIdx + 1}/${game.history.length} 步 — 可以从此继续`, 2500);

    // Continue from this point if it's AI's turn
    if (game.players[game.currentIdx] && !game.players[game.currentIdx].isHuman &&
        game.players[game.currentIdx].status === 'active' &&
        game.phase !== 'idle') {
      scheduleAITurn();
    }
  }

  // ── God Mode ──
  function toggleGodMode() {
    UI.toggleGodMode();
    refreshUI();
  }

  // ── Review ──
  function toggleReview() {
    reviewVisible = !reviewVisible;
    const panel = document.getElementById('review-panel');
    const btn = document.getElementById('btn-review-toggle');

    if (reviewVisible) {
      panel.classList.add('visible');
      btn.classList.add('active');
      if (game && game.phase === 'idle') {
        const review = Review.reviewHand(game, humanIdx);
        Review.renderReview(review);
        Review.drawRadar('radar-canvas', review.dimensions);
      }
    } else {
      panel.classList.remove('visible');
      btn.classList.remove('active');
    }
  }

  // ── Settings ──
  function toggleSettings() {
    settingsVisible = !settingsVisible;
    const panel = document.getElementById('settings-panel');
    if (!panel) {
      createSettingsPanel();
    } else {
      panel.classList.toggle('visible');
    }
  }

  function createSettingsPanel() {
    const app = document.getElementById('app');
    const panel = document.createElement('div');
    panel.id = 'settings-panel';
    panel.className = settingsVisible ? 'visible' : '';

    const profile = E.getUserProfile();
    const apiConfig = E.getAPIConfig();

    panel.innerHTML = `
      <h3 style="color:var(--neon-cyan);margin-bottom:12px">⚙️ 设置</h3>

      <div class="settings-group">
        <label>玩家昵称</label>
        <input id="setting-nickname" value="${profile.nickname || ''}" placeholder="输入昵称">
      </div>

      <div class="settings-group">
        <label>AI 难度</label>
        <select id="setting-difficulty">
          <option value="1" ${aiDifficulty === 1 ? 'selected' : ''}>初级 — 基础策略</option>
          <option value="2" ${aiDifficulty === 2 ? 'selected' : ''}>中级 — 位置+赔率</option>
          <option value="3" ${aiDifficulty === 3 ? 'selected' : ''}>高级 — GTO近似</option>
        </select>
      </div>

      <div class="settings-group">
        <label>AI API Endpoint (可选，用于远程AI)</label>
        <input id="setting-api-url" value="${apiConfig.url || ''}" placeholder="https://api.example.com/poker">
      </div>

      <div class="settings-group">
        <label>API Key</label>
        <input id="setting-api-key" type="password" value="${apiConfig.key || ''}" placeholder="sk-...">
      </div>

      <div style="display:flex;gap:8px;margin-top:12px">
        <button class="btn primary" onclick="App.saveSettings()">💾 保存设置</button>
        <button class="btn" onclick="App.toggleSettings()">关闭</button>
      </div>

      <div style="margin-top:12px;font-size:0.7rem;color:var(--text-dim)">
        牌局历史和设置自动保存在浏览器本地存储中
      </div>
    `;

    // Insert after header
    const header = document.querySelector('.header');
    header.after(panel);
  }

  function saveSettings() {
    const nickname = document.getElementById('setting-nickname')?.value || '';
    const difficulty = parseInt(document.getElementById('setting-difficulty')?.value || '2');
    const apiUrl = document.getElementById('setting-api-url')?.value || '';
    const apiKey = document.getElementById('setting-api-key')?.value || '';

    aiDifficulty = difficulty;

    // Merge profile instead of overwriting
    const existing = E.getUserProfile();
    existing.nickname = nickname;
    existing.lastUpdated = new Date().toISOString();
    E.saveUserProfile(existing);
    E.saveAPIConfig({ url: apiUrl, key: apiKey });

    if (nickname && humanIdx >= 0) {
      game.players[humanIdx].name = nickname;
    }

    // Auto-close settings panel
    settingsVisible = false;
    const panel = document.getElementById('settings-panel');
    if (panel) panel.classList.remove('visible');

    UI.showToast('设置已保存', 2000);
    refreshUI();
  }

  function loadSettings() {
    const profile = E.getUserProfile();
    const apiConfig = E.getAPIConfig();
    if (apiConfig.url || apiConfig.key) {
      // API config loaded (used by remote AI calls if implemented)
    }
    return { profile, apiConfig };
  }

  // ── History Viewer ──
  function showHistory() {
    const history = E.getHandHistory();
    let panel = document.getElementById('history-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'history-panel';
      document.getElementById('app').appendChild(panel);
    }
    panel.classList.add('visible');

    if (history.length === 0) {
      panel.innerHTML = '<div style="padding:16px;color:var(--text-dim)">暂无牌局历史</div>';
      return;
    }

    panel.innerHTML = `<h3 style="color:var(--neon-cyan);margin-bottom:8px">📜 牌局历史 (${history.length}局)</h3>`;
    for (const h of history.slice(0, 20)) {
      const date = new Date(h.date).toLocaleDateString('zh-CN');
      const time = new Date(h.date).toLocaleTimeString('zh-CN', { hour:'2-digit', minute:'2-digit' });
      const humanPlayer = h.players.find(p => p.isHuman);
      const won = h.winners && humanPlayer && h.winners.includes(h.players.indexOf(humanPlayer));
      panel.innerHTML += `
        <div class="history-item" style="${won ? 'border-left:3px solid var(--neon-green)' : ''}">
          <span>#${h.handNumber} <span style="color:var(--text-dim);font-size:0.65rem">${date} ${time}</span></span>
          <span style="color:${won ? 'var(--neon-green)' : 'var(--text-dim)'}">底池: ${h.pot} ${won ? '🏆 赢了!' : ''}</span>
        </div>
      `;
    }
  }

  // ── UI Refresh ──
  function refreshUI() {
    if (!game) return;
    UI.renderTable(game);
    Timeline.render(game);
    if (reviewVisible && game.phase === 'idle') {
      const review = Review.reviewHand(game, humanIdx);
      Review.renderReview(review);
      Review.drawRadar('radar-canvas', review.dimensions);
    }
  }

  // ── Exports ──
  return {
    init, newHand, playerAction, updateBetSlider,
    rewindTo, toggleGodMode, toggleReview, toggleSettings,
    saveSettings, showHistory, refreshUI,
  };
})();

// ── Boot ──
document.addEventListener('DOMContentLoaded', () => {
  window.App.init();
});
