/**
 * PokerMate Dashboard — Landing page controller
 * Handles stats, history, new match config, profile, and navigation
 */
(function() {
  const App = window.App = window.App || {};

  // ── Quotes ──
  const QUOTES = [
    { text: '每一手牌都是一次学习。今天的你会比昨天更强。', author: '— 学习统计基于你的训练数据' },
    { text: '扑克不是关于赢每一手牌，而是关于做出每一个正确的决定。', author: '— Annie Duke' },
    { text: '耐心是扑克中最被低估的技能。等待正确的时机。', author: '— Doyle Brunson' },
    { text: '位置就是力量。利用位置优势来最大化你的赢率。', author: '— Phil Ivey' },
    { text: '不要因为一手牌输了就觉得自己打错了。过程比结果更重要。', author: '— Daniel Negreanu' },
  ];

  // ── Safe DOM helper ──
  function $(id) { return document.getElementById(id); }
  function safeText(id, text) { const el = $(id); if (el) el.textContent = text; }

  // ── Init ──
  App.init = function() {
    try {
    const profile = (() => { try { return JSON.parse(localStorage.getItem('poker_user_profile') || '{}'); } catch(e) { return {}; } })();
    const history = (() => { try { return JSON.parse(localStorage.getItem('poker_hand_history') || '[]'); } catch(e) { return []; } })();

    // Greeting
    safeText('user-name', profile.nickname || '牌手');
    safeText('avatar-initial', (profile.nickname || 'P')[0]);

    // Date
    const now = new Date();
    const days = ['日','一','二','三','四','五','六'];
    $('date-display').textContent =
      `${now.getFullYear()}年${now.getMonth()+1}月${now.getDate()}日 · 星期${days[now.getDay()]}`;

    // Quote
    const q = QUOTES[Math.floor(Math.random() * QUOTES.length)];
    $('quote-text').textContent = q.text;
    document.querySelector('.quote-author').textContent = q.author;

    // Stats
    App.renderStats(history, profile);

    // Streak
    App.renderStreak(history, profile);

    // History list
    App.renderHistoryList(history);

    // Skill bars
    App.renderSkillBars(history);

    // Quick resume button
    const lastState = localStorage.getItem('poker_last_game_state');
    if (lastState) {
      const btn = $('btn-resume');
      if (btn) btn.hidden = false;
    }
    } catch(e) {
      console.warn('Dashboard init error:', e);
    }
  };

  // ── Stats Calculation ──
  App.renderStats = function(history, profile) {
    const totalHands = history.length;
    $('stat-hands').textContent = totalHands;

    // Average score from review data
    let totalScore = 0, scoreCount = 0;
    history.forEach(h => {
      if (h.review && typeof h.review.totalScore === 'number') {
        totalScore += h.review.totalScore;
        scoreCount++;
      }
    });
    $('stat-score').textContent = scoreCount > 0
      ? (totalScore / scoreCount).toFixed(0)
      : '--';

    // Today's hands
    const today = new Date().toISOString().slice(0, 10);
    const todayHands = history.filter(h => h.date && h.date.slice(0, 10) === today).length;
    $('stat-today-hands').textContent = `今日 +${todayHands}`;

    // Score change (last 7 days vs previous 7 days)
    const now = new Date();
    const recent7 = history.filter(h => {
      if (!h.review || typeof h.review.totalScore !== 'number') return false;
      const d = new Date(h.date);
      return (now - d) / 86400000 <= 7;
    });
    if (recent7.length > 0) {
      const avg = recent7.reduce((s,h) => s + h.review.totalScore, 0) / recent7.length;
      $('stat-score-change').textContent = `${avg.toFixed(0)} 近7天`;
    }

    // Training focus
    const dimCounts = { range:0, position:0, odds:0, aggression:0, mental:0 };
    const dimNames = { range:'范围选择', position:'位置打法', odds:'赔率数学', aggression:'侵略性', mental:'心理博弈' };
    history.forEach(h => {
      if (h.review && h.review.dimensions) {
        Object.keys(dimCounts).forEach(k => {
          if (h.review.dimensions[k] !== undefined) dimCounts[k]++;
        });
      }
    });
    let weakest = 'range', weakestVal = Infinity;
    Object.keys(dimCounts).forEach(k => {
      // Find dimension with lowest average across reviews
      let sum = 0, n = 0;
      history.forEach(h => {
        if (h.review && h.review.dimensions && h.review.dimensions[k] !== undefined) {
          sum += h.review.dimensions[k]; n++;
        }
      });
      const avg = n > 0 ? sum / n : 0;
      if (avg < weakestVal) { weakestVal = avg; weakest = k; }
    });
    $('stat-focus').textContent = dimNames[weakest];
    $('stat-focus-detail').textContent = '建议优先提升';

    // Streak
    const streak = App.calcStreak(history, profile);
    $('stat-streak').textContent = `${streak.current}天`;
    $('stat-best-streak').textContent = `最佳 ${streak.best}天`;
  };

  // ── Streak Calculation ──
  App.calcStreak = function(history, profile) {
    const daysWithHands = new Set();
    history.forEach(h => {
      if (h.date) daysWithHands.add(h.date.slice(0,10));
    });

    let current = 0;
    const today = new Date();
    // Count consecutive days backward from today
    for (let i = 0; i < 365; i++) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().slice(0,10);
      if (daysWithHands.has(key)) {
        current++;
      } else if (i > 0) {
        break;
      }
    }

    // Best streak
    let best = profile.bestStreak || 0;
    const sorted = Array.from(daysWithHands).sort();
    let run = 0;
    for (let i = 0; i < sorted.length; i++) {
      if (i === 0) { run = 1; continue; }
      const prev = new Date(sorted[i-1]);
      const curr = new Date(sorted[i]);
      const diff = (curr - prev) / 86400000;
      if (diff === 1) {
        run++;
      } else {
        if (run > best) best = run;
        run = 1;
      }
    }
    if (run > best) best = run;

    // Save best streak
    if (best > (profile.bestStreak || 0)) {
      profile.bestStreak = best;
      localStorage.setItem('poker_user_profile', JSON.stringify(profile));
    }

    return { current, best };
  };

  // ── Weekly Streak Bar ──
  App.renderStreak = function(history, profile) {
    const container = $('streak-bar');
    const daysWithHands = new Set();
    history.forEach(h => {
      if (h.date) daysWithHands.add(h.date.slice(0,10));
    });

    const today = new Date();
    let html = '';
    const dayLabels = ['一','二','三','四','五','六','日'];

    for (let i = 6; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().slice(0,10);
      const done = daysWithHands.has(key);
      const isToday = i === 0;
      html += `<div style="text-align:center;flex-shrink:0">
        <div class="streak-dot ${done ? 'done' : ''} ${isToday ? 'today' : ''}">${done ? '✓' : dayLabels[d.getDay() === 0 ? 6 : d.getDay() - 1]}</div>
        <div class="streak-label">${isToday ? '今天' : dayLabels[d.getDay() === 0 ? 6 : d.getDay() - 1]}</div>
      </div>`;
    }

    container.innerHTML = html;
  };

  // ── History List ──
  App.renderHistoryList = function(history) {
    const container = $('history-list');
    $('history-count').textContent = history.length;

    if (history.length === 0) {
      container.innerHTML = `<div class="empty-state">
        <div class="empty-icon">🂠</div>
        <div>还没有牌局记录</div>
        <div style="font-size:0.78rem;margin-top:4px">完成一局比赛后会自动出现在这里</div>
      </div>`;
      return;
    }

    const recent = history.slice(0, 10);
    container.innerHTML = recent.map((h, i) => {
      const date = new Date(h.date);
      const dateStr = `${date.getMonth()+1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2,'0')}`;
      const playerCount = h.players ? h.players.length : 0;
      const humanWon = h.winners && h.winners.some(w => {
        const p = h.players.find(pl => pl.id === w || pl.name === w);
        return p && p.isHuman;
      });
      const score = h.review ? h.review.totalScore : null;
      const scoreClass = score >= 78 ? 'good' : score >= 62 ? 'ok' : '';

      return `<div class="history-item" onclick="App.openHandDetail(${i})">
        <div class="hi-icon ${humanWon ? 'win' : 'lose'}">${humanWon ? '🏆' : '📋'}</div>
        <div class="hi-info">
          <div class="hi-title">${playerCount}人桌 · 第${h.handNumber || '?'}手</div>
          <div class="hi-meta">${dateStr}</div>
        </div>
        ${score !== null ? `<div class="hi-score ${scoreClass}">${score.toFixed(0)}</div>` : ''}
      </div>`;
    }).join('');
  };

  // ── Skill Bars ──
  App.renderSkillBars = function(history) {
    const container = $('skill-bars');
    const dims = [
      { key: 'range', name: '范围选择', color: '#0071e3' },
      { key: 'position', name: '位置打法', color: '#34c759' },
      { key: 'odds', name: '赔率数学', color: '#af52de' },
      { key: 'aggression', name: '侵略性', color: '#ff9500' },
      { key: 'mental', name: '心理博弈', color: '#5ac8fa' },
    ];

    container.innerHTML = dims.map(d => {
      let sum = 0, n = 0;
      history.forEach(h => {
        if (h.review && h.review.dimensions && h.review.dimensions[d.key] !== undefined) {
          sum += h.review.dimensions[d.key]; n++;
        }
      });
      const avg = n > 0 ? Math.round(sum / n) : 0;
      return `<div class="skill-row">
        <span class="skill-name">${d.name}</span>
        <div class="skill-track">
          <div class="skill-fill" style="width:${Math.max(avg, 5)}%;background:${d.color}"></div>
        </div>
        <span style="font-size:0.75rem;color:var(--text-secondary);width:28px;text-align:right">${avg}</span>
      </div>`;
    }).join('');
  };

  // ── Open Hand Detail ──
  App.openHandDetail = function(index) {
    localStorage.setItem('poker_view_hand_index', index);
    window.location.href = 'game.html?view=history&idx=' + index;
  };

  // ── New Match Modal ──
  App.openNewMatch = function() {
    const overlay = $('modal-overlay');
    if (overlay) overlay.hidden = false;
  };

  App.closeModal = function(event) {
    const overlay = $('modal-overlay');
    if (!overlay) return;
    if (event && event.target !== overlay) return;
    overlay.hidden = true;
  };

  // ── Toggle Switch ──
  App.toggleSwitch = function(id) {
    const el = $(id);
    if (el) el.classList.toggle('on');
  };

  // ── Start Match ──
  App.startMatch = function() {
    try {
    const diff = $('cfg-difficulty');
    const opp = $('cfg-opponents');
    const stk = $('cfg-stack');
    const god = $('tog-god');
    const coach = $('tog-coach');
    const review = $('tog-auto-review');
    const rec = $('tog-record');
    if (!diff || !opp || !stk || !god || !coach || !review || !rec) {
      console.warn('startMatch: missing config elements');
      return;
    }
    const params = new URLSearchParams({
      difficulty: diff.value,
      opponents: opp.value,
      stack: stk.value,
      god: god.classList.contains('on') ? '1' : '0',
      coach: coach.classList.contains('on') ? '1' : '0',
      autoReview: review.classList.contains('on') ? '1' : '0',
      record: rec.classList.contains('on') ? '1' : '0',
    });
    window.location.href = 'game.html?' + params.toString();
    } catch(e) { console.warn('startMatch error:', e); }
  };

  // ── Quick Resume ──
  App.quickResume = function() {
    window.location.href = 'game.html?resume=1';
  };

  // ── Profile Modal ──
  App.editProfile = function() {
    try {
    const profile = JSON.parse(localStorage.getItem('poker_user_profile') || '{}');
    const input = $('profile-nickname');
    const modal = $('profile-modal');
    if (input) input.value = profile.nickname || '';
    if (modal) modal.hidden = false;
    } catch(e) { console.warn('editProfile error:', e); }
  };

  App.closeProfileModal = function(event) {
    const modal = $('profile-modal');
    if (!modal) return;
    if (event && event.target !== modal) return;
    modal.hidden = true;
  };

  App.saveProfile = function() {
    try {
    const input = $('profile-nickname');
    if (!input) return;
    const nickname = input.value.trim() || '牌手';
    const profile = JSON.parse(localStorage.getItem('poker_user_profile') || '{}');
    profile.nickname = nickname;
    localStorage.setItem('poker_user_profile', JSON.stringify(profile));

    const nameEl = $('user-name');
    const avatarEl = $('avatar-initial');
    const modal = $('profile-modal');
    if (nameEl) nameEl.textContent = nickname;
    if (avatarEl) avatarEl.textContent = nickname[0];
    if (modal) modal.hidden = true;
    } catch(e) { console.warn('saveProfile error:', e); }
  };

  // ── Boot ──
  document.addEventListener('DOMContentLoaded', function() {
    // Check if redirected from game page with hand data to view
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('from') === 'game') {
      // Game just finished, refresh stats
    }
    App.init();
  });

})();
