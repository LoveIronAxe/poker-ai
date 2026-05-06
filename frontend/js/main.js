// ============================================================
// main.js — App controller, game loop, settings, storage
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
  let autoPlayTimer = null;
  let coachMode = false;
  let fastForwardNotice = false;

  // ── AI Name Pool ──
  const AI_NAME_POOL = [
    '鲨鱼', '老鹰', '黑猫', '银狐', '猎豹', '毒蛇', '乌鸦', '山猫',
    '红桃K', '方块Q', '草花J', '黒桃A',
    '大盲王', '小盲圣', '枪口侠', '庄位帝',
    '诈唬大师', '跟注站', '紧凶王', '松凶怪',
    '算牌器', '德州迷', '河牌鱼', '翻牌精',
    'All-in狂', '慢打王', '偷盲贼', '价值怪',
    '暴风雨', '幸运星', '暗夜', '极光', '龙卷风',
    '冷面', '铁壁', '幻影', '剃刀', '黑曜石',
    '蓝月', '赤潮', '雷霆', '闪电', '冰川',
    '太极', '无极', '求败', '独孤', '不败',
    '老千', '赌神', '雀圣', '赌侠',
  ];

  function pickAINames(count) {
    const shuffled = [...AI_NAME_POOL].sort(() => Math.random() - 0.5);
    return shuffled.slice(0, count);
  }

  function humanIsActive() {
    const human = game.players[humanIdx];
    return human && human.status === 'active';
  }

  function init() {
    const params = new URLSearchParams(window.location.search);

    aiDifficulty = parseInt(params.get('difficulty')) || 2;
    const numPlayers = parseInt(params.get('opponents')) || 6;
    const stackSize = parseInt(params.get('stack')) || 1000;
    const godMode = params.get('god') !== '0';
    const coach = params.get('coach') === '1';
    const autoReview = params.get('autoReview') === '1';

    coachMode = coach;
    loadSettings();

    // Create game
    const stacks = Array(numPlayers).fill(stackSize);
    game = E.createGame(numPlayers, 1, 2, stacks);
    game.players[0].isHuman = true;
    const profile = E.getUserProfile();
    game.players[0].name = profile.nickname || 'Hero';
    const names = pickAINames(numPlayers - 1);
    for (let i = 1; i < numPlayers; i++) {
      game.players[i].name = names[i - 1] || `牌手${i}`;
    }

    if (godMode) {
      UI.setGodMode(true);
      const btn = document.getElementById('btn-god');
      if (btn) btn.classList.add('active');
    }

    if (coachMode) {
      const bar = document.getElementById('god-mode-bar');
      if (bar) {
        bar.textContent = '🎓 AI 教练 — 实时提示 & 胜率分析';
        bar.className = 'info-bar coach visible';
      }
    }

    newHand();
  }

  function newHand() {
    if (autoPlayTimer) { clearTimeout(autoPlayTimer); autoPlayTimer = null; }
    fastForwardNotice = false;

    const reviewOverlay = document.getElementById('review-overlay');
    if (reviewOverlay) reviewOverlay.hidden = true;

    const started = E.startNewHand(game);
    if (!started) {
      UI.showToast('游戏结束！重新开始');
      const n = game.numPlayers;
      const stacks = Array(n).fill(1000);
      game = E.createGame(n, 1, 2, stacks);
      game.players[0].isHuman = true;
      const profile = E.getUserProfile();
      game.players[0].name = profile.nickname || 'Hero';
      const names = pickAINames(n - 1);
      for (let i = 1; i < n; i++) {
        game.players[i].name = names[i - 1] || `牌手${i}`;
      }
      E.startNewHand(game);
    }

    humanIdx = game.players.findIndex(p => p.isHuman);
    refreshUI();

    // Auto-play AI turns
    if (game.players[game.currentIdx] && !game.players[game.currentIdx].isHuman
        && game.phase !== 'idle') {
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

    if (type === 'allin') {
      action.amount = human.stack;
    }

    const result = E.applyAction(game, game.players.indexOf(human), action);
    refreshUI();
    handleActionResult(result);
  }

  // ── Bet Action (2x, 3x, 4x) ──
  function betAction(multiplier) {
    if (!game || game.phase === 'idle' || game.phase === 'showdown') return;
    const human = game.players.find(p => p.isHuman);
    if (!human || human.status !== 'active') return;
    if (game.currentIdx !== game.players.indexOf(human)) return;

    const legal = E.getLegalActions(game, game.players.indexOf(human));
    const toCall = game.currentBet - human.roundBet;
    const canBet = legal.find(a => a.type === 'bet');
    const canRaise = legal.find(a => a.type === 'raise');

    if (toCall === 0) {
      if (!canBet) { UI.showToast('当前无法下注'); return; }
      const pot = game.players.reduce((s, p) => s + p.currentBet, 0);
      let amount = Math.floor(pot * multiplier);
      amount = Math.max(canBet.min || game.bb, Math.min(amount, canBet.max || human.stack));
      const action = { type: 'bet', amount };
      const result = E.applyAction(game, game.players.indexOf(human), action);
      refreshUI();
      handleActionResult(result);
    } else {
      if (!canRaise) {
        playerAction(toCall >= human.stack ? 'allin' : 'call');
        return;
      }
      const pot = game.players.reduce((s, p) => s + p.currentBet, 0);
      let amount = Math.floor(pot * multiplier);
      const minRaise = canRaise.min || (game.currentBet + game.lastRaise - human.roundBet);
      amount = Math.max(minRaise, Math.min(amount, canRaise.max || human.stack));
      const action = { type: 'raise', amount };
      const result = E.applyAction(game, game.players.indexOf(human), action);
      refreshUI();
      handleActionResult(result);
    }
  }

  // ── Custom Bet Modal ──
  function openCustomBet() {
    if (!game || game.phase === 'idle' || game.phase === 'showdown') return;
    const human = game.players.find(p => p.isHuman);
    if (!human || human.status !== 'active') return;
    if (game.currentIdx !== game.players.indexOf(human)) return;

    const overlay = document.getElementById('custom-bet-overlay');
    const input = document.getElementById('custom-bet-amount');
    if (!overlay || !input) return;

    const legal = E.getLegalActions(game, game.players.indexOf(human));
    const canBet = legal.find(a => a.type === 'bet');
    const canRaise = legal.find(a => a.type === 'raise');
    const toCall = game.currentBet - human.roundBet;
    let defaultVal = game.minRaise;
    if (canRaise) defaultVal = canRaise.min || game.minRaise;
    else if (canBet) defaultVal = canBet.min || game.bb;
    else defaultVal = toCall > 0 ? toCall : game.bb;

    input.value = defaultVal;
    input.min = 1;
    input.max = human.stack;
    overlay.hidden = false;
  }

  function closeCustomBet(event) {
    if (event && event.target !== document.getElementById('custom-bet-overlay')) return;
    const overlay = document.getElementById('custom-bet-overlay');
    if (overlay) overlay.hidden = true;
  }

  function confirmCustomBet() {
    const input = document.getElementById('custom-bet-amount');
    if (!input) return;
    const amount = parseInt(input.value) || 0;
    closeCustomBet();

    if (!game || game.phase === 'idle' || game.phase === 'showdown') return;
    const human = game.players.find(p => p.isHuman);
    if (!human || human.status !== 'active') return;
    if (game.currentIdx !== game.players.indexOf(human)) return;

    const legal = E.getLegalActions(game, game.players.indexOf(human));
    const toCall = game.currentBet - human.roundBet;

    let action;
    if (toCall === 0) {
      const canBet = legal.find(a => a.type === 'bet');
      if (!canBet) { UI.showToast('当前无法下注'); return; }
      action = { type: 'bet', amount: Math.max(canBet.min || 0, Math.min(amount, canBet.max || human.stack)) };
    } else {
      const canRaise = legal.find(a => a.type === 'raise');
      if (canRaise) {
        const minRaise = canRaise.min || (game.currentBet + game.lastRaise - human.roundBet);
        action = { type: 'raise', amount: Math.max(minRaise, Math.min(amount, canRaise.max || human.stack)) };
      } else {
        playerAction(amount >= human.stack ? 'allin' : 'call');
        return;
      }
    }

    const result = E.applyAction(game, game.players.indexOf(human), action);
    refreshUI();
    handleActionResult(result);
  }

  // ── AI Turn ──
  function scheduleAITurn() {
    if (autoPlayTimer) clearTimeout(autoPlayTimer);
    // Fast-forward when human is not active (folded or all-in)
    const delay = humanIsActive() ? (500 + Math.random() * 300) : (150 + Math.random() * 150);
    autoPlayTimer = setTimeout(executeAITurn, delay);
  }

  function executeAITurn() {
    if (!game || game.phase === 'idle' || game.phase === 'showdown') return;
    const current = game.players[game.currentIdx];
    if (!current || current.status !== 'active' || current.isHuman) {
      if (current && !current.isHuman && current.status !== 'active') {
        const next = E.nextCanAct(game, game.currentIdx);
        if (next >= 0) {
          game.currentIdx = next;
          scheduleAITurn();
        }
      }
      return;
    }

    try {
      let resolvedAction = null;
      const action = AI.decide(game, game.currentIdx, aiDifficulty);
      const legal = E.getLegalActions(game, game.currentIdx);

      if (!legal || !legal.length) {
        resolvedAction = { type: 'fold', amount: 0 };
      } else {
        const match = legal.find(a => a.type === action.type);
        if (!match) {
          resolvedAction = legal[0];
        } else if (action.type === 'raise' || action.type === 'bet') {
          resolvedAction = match;
          if (action.amount) {
            resolvedAction.amount = Math.max(match.min || 0, Math.min(action.amount, match.max || Infinity));
          }
        } else {
          resolvedAction = match;
        }
      }

      if (!resolvedAction) resolvedAction = legal[0];

      const result = E.applyAction(game, game.currentIdx, resolvedAction);
      refreshUI();

      if (result === 'hand_over' || game.phase === 'idle') {
        onHandComplete();
      } else if (game.players[game.currentIdx] && !game.players[game.currentIdx].isHuman) {
        scheduleAITurn();
      }
    } catch (e) {
      console.error('AI turn error:', e);
      const legal = E.getLegalActions(game, game.currentIdx);
      if (legal && legal.length > 0) {
        const result = E.applyAction(game, game.currentIdx, legal[0]);
        if (result === 'hand_over' || game.phase === 'idle') {
          onHandComplete();
        } else if (game.players[game.currentIdx] && !game.players[game.currentIdx].isHuman) {
          scheduleAITurn();
        }
      }
      refreshUI();
    }
  }

  function handleActionResult(result) {
    if (result === 'hand_over' || game.phase === 'idle') {
      onHandComplete();
    } else if (game.phase !== 'showdown') {
      // Notify user if they've folded but game continues
      if (!humanIsActive() && !fastForwardNotice) {
        fastForwardNotice = true;
        UI.showToast('你已弃牌 — AI 自动对局中...', 2000);
      }
      if (game.players[game.currentIdx] && !game.players[game.currentIdx].isHuman) {
        scheduleAITurn();
      }
    }
  }

  function onHandComplete() {
    const review = Review.reviewHand(game, humanIdx);
    E.attachReviewToHistory(review);
    showReviewOverlay(review);
    Timeline.render(game);
    const btnReview = document.getElementById('btn-review-toggle');
    if (btnReview) btnReview.style.display = '';
    UI.showToast('本局结束 — 查看复盘分析', 2500);

    if (coachMode) {
      const grade = review.grade;
      const msg = grade === 'S' || grade === 'A' ? '表现出色！' :
                  grade === 'B' ? '不错，查看复盘了解改进点。' : '有改进空间，查看复盘面板。';
      UI.showToast('评分 ' + review.totalScore + ' (' + grade + ') — ' + msg, 3000);
    }
  }

  function showReviewOverlay(review) {
    const overlay = document.getElementById('review-overlay');
    if (!overlay) return;
    overlay.hidden = false;
    Review.renderReview(review);
    setTimeout(() => {
      Review.drawRadar('radar-canvas', review.dimensions);
    }, 100);
  }

  function closeReview() {
    const overlay = document.getElementById('review-overlay');
    if (overlay) overlay.hidden = true;
  }

  // ── Rewind System ──
  function rewindTo(snapIdx) {
    if (!game || snapIdx < 0 || snapIdx >= game.history.length) return;
    if (autoPlayTimer) { clearTimeout(autoPlayTimer); autoPlayTimer = null; }

    E.restoreSnapshot(game, snapIdx);

    for (const p of game.players) {
      if (p.status === 'out' || p.status === 'folded') continue;
      p.status = 'active';
    }

    fastForwardNotice = false;
    refreshUI();
    UI.showToast(`已回溯到第 ${snapIdx + 1}/${game.history.length} 步`, 2000);

    if (game.players[game.currentIdx] && !game.players[game.currentIdx].isHuman &&
        game.players[game.currentIdx].status === 'active' &&
        game.phase !== 'idle') {
      scheduleAITurn();
    }
  }

  // ── God Mode ──
  function toggleGodMode() {
    UI.toggleGodMode();
    const btn = document.getElementById('btn-god');
    if (btn) btn.classList.toggle('active', UI.isGodMode());
    refreshUI();
  }

  // ── Review ──
  function toggleReview() {
    const overlay = document.getElementById('review-overlay');
    if (!overlay) return;
    if (!overlay.hidden) {
      overlay.hidden = true;
      return;
    }
    if (game && game.phase === 'idle') {
      const review = Review.reviewHand(game, humanIdx);
      showReviewOverlay(review);
    } else {
      const timelineSection = document.getElementById('timeline-section');
      if (timelineSection) timelineSection.style.display = 'block';
    }
  }

  // ── Settings ──
  function toggleSettings() {
    const overlay = document.getElementById('settings-overlay');
    if (!overlay) return;
    const profile = E.getUserProfile();
    const apiConfig = E.getAPIConfig();
    const el = (id) => document.getElementById(id);
    if (el('setting-nickname')) el('setting-nickname').value = profile.nickname || '';
    if (el('setting-difficulty')) el('setting-difficulty').value = aiDifficulty;
    if (el('setting-api-url')) el('setting-api-url').value = apiConfig.url || '';
    if (el('setting-api-key')) el('setting-api-key').value = apiConfig.key || '';
    if (el('setting-model')) el('setting-model').value = apiConfig.model || '';
    if (el('setting-review-prompt')) el('setting-review-prompt').value = apiConfig.reviewPrompt || '';
    overlay.hidden = false;
  }

  function closeSettings(event) {
    const overlay = document.getElementById('settings-overlay');
    if (!overlay) return;
    if (!event || event.target === overlay) {
      overlay.hidden = true;
    }
  }

  function saveSettings() {
    const el = (id) => document.getElementById(id);
    const nickname = (el('setting-nickname')?.value || '').trim() || 'Hero';
    aiDifficulty = parseInt(el('setting-difficulty')?.value || '2');

    const apiConfig = {
      url: el('setting-api-url')?.value || '',
      key: el('setting-api-key')?.value || '',
      model: el('setting-model')?.value || '',
      reviewPrompt: el('setting-review-prompt')?.value || '',
    };

    const existing = E.getUserProfile();
    existing.nickname = nickname;
    existing.lastUpdated = new Date().toISOString();
    E.saveUserProfile(existing);
    E.saveAPIConfig(apiConfig);

    if (nickname && humanIdx >= 0 && game) {
      game.players[humanIdx].name = nickname;
    }

    const overlay = document.getElementById('settings-overlay');
    if (overlay) overlay.hidden = true;
    UI.showToast('设置已保存', 2000);
    refreshUI();
  }

  function loadSettings() {
    const profile = E.getUserProfile();
    const apiConfig = E.getAPIConfig();
    return { profile, apiConfig };
  }

  // ── AI Review Generation ──
  async function generateAIReview() {
    const apiConfig = E.getAPIConfig();
    if (!apiConfig.key) {
      UI.showToast('请先在设置中配置 API Key', 2500);
      toggleSettings();
      return;
    }

    const resultDiv = document.getElementById('ai-review-result');
    if (resultDiv) {
      resultDiv.style.display = 'block';
      resultDiv.textContent = '🤔 AI 正在分析你的牌局...';
    }

    try {
      const review = Review.reviewHand(game, humanIdx);
      const handSummary = buildHandSummary(review);
      const prompt = (apiConfig.reviewPrompt || defaultReviewPrompt()).replace('{{HAND_DATA}}', handSummary);

      const response = await fetch(apiConfig.url || 'https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + apiConfig.key,
        },
        body: JSON.stringify({
          model: apiConfig.model || 'gpt-4o',
          messages: [
            { role: 'system', content: '你是一位世界级德州扑克教练。请用中文回答。简洁有力。' },
            { role: 'user', content: prompt }
          ],
          max_tokens: 1500,
          temperature: 0.7,
        }),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`API 错误 ${response.status}: ${errText.slice(0, 200)}`);
      }

      const data = await response.json();
      const content = data.choices?.[0]?.message?.content || JSON.stringify(data);

      if (resultDiv) {
        resultDiv.textContent = content;
        resultDiv.style.display = 'block';
      }
    } catch (err) {
      if (resultDiv) {
        resultDiv.textContent = '❌ AI 分析失败: ' + err.message;
        resultDiv.style.display = 'block';
      }
      console.error('AI review error:', err);
    }
  }

  function buildHandSummary(review) {
    const human = game.players[humanIdx];
    const holeCards = human.holeCards.map(c => E.cardStr(c)).join(' ');
    const communityCards = game.communityCards.map(c => E.cardStr(c)).join(' ') || '无';
    const phase = game.phase;
    const handResult = human.stack > 1000 ? '赢了' : (human.stack < 1000 ? '输了' : '持平');

    return `牌局总结:
- 底牌: ${holeCards}
- 公共牌: ${communityCards}
- 最终阶段: ${phase}
- 结果: ${handResult}
- 总评分: ${review.totalScore}/100 (${review.grade})
- 各维度评分: ${JSON.stringify(review.dimensions)}
- 操作历史: ${game.events.map(e => {
  if (e.type === 'action') {
    const p = game.players[e.playerIdx];
    return `${p.name}: ${e.action.type} ${e.action.amount || ''}`;
  }
  return e.desc || e.type;
}).join(' → ')}`;
  }

  function defaultReviewPrompt() {
    return `你是一位世界级德州扑克教练。请分析以下牌局数据并给出改进建议。

牌局数据: {{HAND_DATA}}

请从以下维度分析:
1. 关键决策点 — 最重要的2-3个决策时刻
2. 范围分析 — 起手牌是否合理，每条街的范围调整
3. 下注尺度 — 下注大小是否合理
4. 改进建议 — 具体可操作的建议

用中文回答，简洁有力。`;
  }

  // ── UI Refresh ──
  function refreshUI() {
    if (!game) return;
    UI.renderTable(game);
    if (game.phase === 'idle') {
      Timeline.render(game);
    }
  }

  // ── Exports ──
  return {
    init, newHand, playerAction, betAction,
    openCustomBet, closeCustomBet, confirmCustomBet,
    rewindTo, toggleGodMode, toggleReview, toggleSettings,
    saveSettings, closeSettings, closeReview, generateAIReview,
    refreshUI,
  };
})();

// ── Boot ──
document.addEventListener('DOMContentLoaded', () => {
  window.App.init();
});
