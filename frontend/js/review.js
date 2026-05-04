// ============================================================
// review.js — 5D review scoring, radar chart, error detection
// ============================================================
window.PokerReview = (() => {
  'use strict';
  const E = window.PokerEngine;

  const DIMENSIONS = [
    { key: 'range', name: '范围选择', color: '#f59e0b', weight: 1.0 },
    { key: 'position', name: '位置利用', color: '#22c55e', weight: 0.9 },
    { key: 'odds', name: '赔率数学', color: '#06b6d4', weight: 0.9 },
    { key: 'aggression', name: '侵略平衡', color: '#f97316', weight: 0.8 },
    { key: 'mental', name: '心理博弈', color: '#a855f7', weight: 0.7 },
  ];

  function reviewHand(game, humanIdx) {
    const dims = {};
    for (const d of DIMENSIONS) {
      dims[d.key] = { name: d.name, score: 70, color: d.color, errors: [], details: [] };
    }

    const player = game.players[humanIdx];
    if (!player || player.status === 'out') {
      return buildEmptyReview();
    }

    // Range score
    scoreRange(game, humanIdx, dims);
    // Position score
    scorePosition(game, humanIdx, dims);
    // Odds score
    scoreOdds(game, humanIdx, dims);
    // Aggression score
    scoreAggression(game, humanIdx, dims);
    // Mental score
    scoreMental(game, humanIdx, dims);

    // Weighted total
    let totalWeight = 0, totalScore = 0;
    for (const d of DIMENSIONS) {
      totalWeight += d.weight;
      totalScore += dims[d.key].score * d.weight;
    }
    const finalScore = totalWeight > 0 ? totalScore / totalWeight : 50;

    // Collect critical errors
    const criticalErrors = [];
    for (const d of DIMENSIONS) {
      for (const err of dims[d.key].errors) {
        err.dimension = d.key;
        err.dimensionName = d.name;
        if (err.severity === 'critical' || err.severity === 'major') {
          criticalErrors.push(err);
        }
      }
    }
    criticalErrors.sort((a, b) => Math.abs(b.evLoss || 0) - Math.abs(a.evLoss || 0));

    // Training focus
    const errorCounts = {};
    for (const e of criticalErrors) {
      const tag = e.tag || '综合';
      errorCounts[tag] = (errorCounts[tag] || 0) + 1;
    }
    const training = Object.entries(errorCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([t]) => t);

    const grade = scoreToGrade(finalScore);

    return {
      totalScore: Math.round(finalScore * 10) / 10,
      grade: grade.label,
      gradeClass: grade.cssClass,
      dimensions: dims,
      criticalErrors,
      training,
      summary: generateSummary(finalScore, grade, dims, criticalErrors, training),
    };
  }

  function scoreRange(game, humanIdx, dims) {
    const player = game.players[humanIdx];
    const posName = window.PokerAI.getPosName(game, humanIdx);
    const str = E.quickEquity(player.holeCards, []);

    let score = 80;
    const errors = [];

    if (['utg', 'mp'].includes(posName) && str.category === 'weak') {
      const actions = game.events.filter(e => e.type === 'action' && e.playerIdx === humanIdx);
      const raised = actions.some(e => e.action.type === 'raise' || e.action.type === 'bet');
      if (raised) {
        score -= 30;
        errors.push({
          type: 'loose_ep', severity: 'critical', evLoss: -8,
          message: `前位${posName.toUpperCase()}用弱牌开池加注`,
          fix: `${posName.toUpperCase()}应使用更紧范围`,
          tag: 'EP开池范围',
        });
      }
    }

    if (str.category === 'premium') score = Math.min(100, score + 10);
    if (str.category === 'playable') score = Math.min(100, score + 5);

    dims.range.score = Math.max(0, Math.min(100, score));
    dims.range.errors = errors;
    dims.range.details = [`起手牌: ${str.category}`, `位置: ${posName}`];
  }

  function scorePosition(game, humanIdx, dims) {
    const posName = window.PokerAI.getPosName(game, humanIdx);
    let score = 75;
    const errors = [];

    const actions = game.events.filter(e => e.type === 'action' && e.playerIdx === humanIdx);
    const aggCount = actions.filter(e =>
      e.action.type === 'raise' || e.action.type === 'bet').length;

    if (posName === 'btn' && aggCount === 0 && actions.length > 0) {
      score -= 20;
      errors.push({
        type: 'passive_btn', severity: 'major', evLoss: -5,
        message: '庄位未利用位置优势', fix: '庄位是最佳位置，应多下注施压', tag: '庄位侵略性',
      });
    } else if (posName === 'btn' && aggCount > 0) {
      score += 10;
    }

    if (posName === 'sb' && actions.length > 2) {
      score -= 15;
      errors.push({
        type: 'loose_sb', severity: 'major', evLoss: -4,
        message: '小盲位过多参与底池', fix: 'SB应减少平跟，使用3-bet or Fold策略', tag: 'SB防守',
      });
    }

    dims.position.score = Math.max(0, Math.min(100, score));
    dims.position.errors = errors;
    dims.position.details = [`位置: ${posName}`, `行动: ${actions.length}次`];
  }

  function scoreOdds(game, humanIdx, dims) {
    let score = 80;
    const errors = [];
    const actions = game.events.filter(e => e.type === 'action' && e.playerIdx === humanIdx);

    for (const evt of actions) {
      if (evt.action.type === 'call' && evt.phase === 'turn') {
        const player = game.players[humanIdx];
        const result = E.evaluate(player.holeCards, game.communityCards.slice(0, 4));
        if (result.rank <= 2) { // one pair or worse
          score -= 10;
          errors.push({
            type: 'weak_call', severity: 'major', evLoss: -3,
            message: `转牌用${result.name}跟注`,
            fix: '计算底池赔率，弱牌不应跟注大注', tag: '赔率计算',
          });
        }
      }
    }

    dims.odds.score = Math.max(0, Math.min(100, score));
    dims.odds.errors = errors;
  }

  function scoreAggression(game, humanIdx, dims) {
    let score = 75;
    const errors = [];
    const actions = game.events.filter(e => e.type === 'action' && e.playerIdx === humanIdx);
    const total = actions.length;
    if (total === 0) { dims.aggression.score = 70; return; }

    const agg = actions.filter(e =>
      e.action.type === 'raise' || e.action.type === 'bet').length;
    const ratio = agg / total;

    if (ratio < 0.2 && total >= 3) {
      score -= 20;
      errors.push({
        type: 'too_passive', severity: 'major', evLoss: -4,
        message: '过于被动，缺少价值下注', fix: '用强牌建立底池，增加下注频率', tag: '价值下注',
      });
    } else if (ratio > 0.8 && total >= 3) {
      score -= 15;
      errors.push({
        type: 'too_aggro', severity: 'major', evLoss: -3,
        message: '过于激进，可能诈唬过多', fix: '减少诈唬，平衡范围', tag: '诈唬频率',
      });
    } else if (ratio >= 0.3 && ratio <= 0.6) {
      score += 10;
    }

    dims.aggression.score = Math.max(0, Math.min(100, score));
    dims.aggression.errors = errors;
    dims.aggression.details = [`激进率: ${agg}/${total} (${Math.round(ratio*100)}%)`];
  }

  function scoreMental(game, humanIdx, dims) {
    let score = 85;
    const errors = [];
    const player = game.players[humanIdx];
    const actions = game.events.filter(e => e.type === 'action' && e.playerIdx === humanIdx);

    // Detect tilt: consecutive raises
    let streak = 0;
    for (const evt of actions) {
      if (evt.action.type === 'raise') streak++;
      else streak = 0;
      if (streak >= 3) {
        score -= 15;
        errors.push({
          type: 'tilt', severity: 'major', evLoss: -5,
          message: '连续多次加注，可能有tilt倾向', fix: '保持冷静，避免情绪化操作', tag: '情绪控制',
        });
        break;
      }
    }

    if (player.currentBet > player.stack * 2 && player.holeCards.length > 0) {
      const result = E.evaluate(player.holeCards, game.communityCards);
      if (result.rank <= 2) {
        score -= 20;
        errors.push({
          type: 'big_bluff', severity: 'critical', evLoss: -10,
          message: '用极弱牌进行大额下注', fix: '下注尺度应与牌力匹配', tag: '下注尺度',
        });
      }
    }

    dims.mental.score = Math.max(0, Math.min(100, score));
    dims.mental.errors = errors;
  }

  function scoreToGrade(score) {
    if (score >= 90) return { label: 'S', cssClass: 'grade-S' };
    if (score >= 78) return { label: 'A', cssClass: 'grade-A' };
    if (score >= 62) return { label: 'B', cssClass: 'grade-B' };
    if (score >= 48) return { label: 'C', cssClass: 'grade-C' };
    return { label: 'D', cssClass: 'grade-D' };
  }

  function buildEmptyReview() {
    const dims = {};
    for (const d of DIMENSIONS) {
      dims[d.key] = { name: d.name, score: 50, color: d.color, errors: [], details: [] };
    }
    return {
      totalScore: 0, grade: 'N/A', gradeClass: '',
      dimensions: dims, criticalErrors: [], training: [], summary: '未参与此局',
    };
  }

  function generateSummary(score, grade, dims, errors, training) {
    const parts = [];
    parts.push(`综合评分: ${Math.round(score)}分 (${grade.label})`);
    const sorted = DIMENSIONS.map(d => ({ key: d.key, ...dims[d.key] }))
      .sort((a, b) => b.score - a.score);
    if (sorted.length >= 2) {
      parts.push(`最强: ${sorted[0].name}(${Math.round(sorted[0].score)}分)`);
      parts.push(`最弱: ${sorted[sorted.length-1].name}(${Math.round(sorted[sorted.length-1].score)}分)`);
    }
    if (errors.length > 0) parts.push(`发现${errors.length}个可优化决策`);
    if (training.length > 0) parts.push(`训练重点: ${training.join(', ')}`);
    return parts.join(' · ');
  }

  // ── Radar Chart ──
  function drawRadar(canvasId, dims) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const cx = w / 2, cy = h / 2;
    const radius = Math.min(cx, cy) - 20;
    const n = DIMENSIONS.length;
    const angleStep = (Math.PI * 2) / n;

    // Grid
    for (let ring = 1; ring <= 5; ring++) {
      const r = (radius / 5) * ring;
      ctx.beginPath();
      for (let i = 0; i <= n; i++) {
        const a = angleStep * i - Math.PI / 2;
        const x = cx + r * Math.cos(a);
        const y = cy + r * Math.sin(a);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.strokeStyle = 'rgba(255,255,255,0.08)';
      ctx.stroke();
    }

    // Axes
    for (let i = 0; i < n; i++) {
      const a = angleStep * i - Math.PI / 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + radius * Math.cos(a), cy + radius * Math.sin(a));
      ctx.strokeStyle = 'rgba(255,255,255,0.12)';
      ctx.stroke();

      // Labels
      const lx = cx + (radius + 18) * Math.cos(a);
      const ly = cy + (radius + 18) * Math.sin(a);
      ctx.fillStyle = '#999';
      ctx.font = '11px system-ui';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(DIMENSIONS[i].name, lx, ly);
    }

    // Data polygon
    ctx.beginPath();
    for (let i = 0; i <= n; i++) {
      const idx = i % n;
      const a = angleStep * idx - Math.PI / 2;
      const score = dims[DIMENSIONS[idx].key]?.score || 50;
      const r = (score / 100) * radius;
      const x = cx + r * Math.cos(a);
      const y = cy + r * Math.sin(a);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = 'rgba(0,240,255,0.12)';
    ctx.fill();
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Data points
    for (let i = 0; i < n; i++) {
      const a = angleStep * i - Math.PI / 2;
      const score = dims[DIMENSIONS[i].key]?.score || 50;
      const r = (score / 100) * radius;
      ctx.beginPath();
      ctx.arc(cx + r * Math.cos(a), cy + r * Math.sin(a), 4, 0, Math.PI * 2);
      ctx.fillStyle = DIMENSIONS[i].color;
      ctx.fill();
    }
  }

  function renderReview(reviewData) {
    const panel = document.getElementById('review-panel');
    if (!panel) return;
    panel.classList.add('visible');

    document.getElementById('review-total').textContent = reviewData.totalScore || '--';
    const gradeEl = document.getElementById('review-grade');
    gradeEl.textContent = reviewData.grade;
    gradeEl.className = 'review-grade ' + (reviewData.gradeClass || 'grade-B');

    drawRadar('radar-canvas', reviewData.dimensions || {});

    // Dimension bars
    const bars = document.getElementById('dim-bars');
    bars.innerHTML = '';
    for (const d of DIMENSIONS) {
      const dim = reviewData.dimensions[d.key];
      if (!dim) continue;
      const bar = document.createElement('div');
      bar.className = 'dim-bar';
      bar.innerHTML = `
        <span class="dim-label">${d.name}</span>
        <div class="dim-fill"><div class="dim-fill-inner" style="width:${dim.score}%;background:${d.color}"></div></div>
        <span class="dim-score" style="color:${d.color}">${Math.round(dim.score)}</span>
      `;
      bars.appendChild(bar);
    }

    // Error list
    const errorList = document.getElementById('error-list');
    errorList.innerHTML = '<h4 style="margin-bottom:8px;color:var(--text-dim)">🔍 决策分析</h4>';
    if (reviewData.criticalErrors && reviewData.criticalErrors.length > 0) {
      for (const err of reviewData.criticalErrors.slice(0, 5)) {
        const cls = err.severity === 'critical' ? '' : ' warning';
        errorList.innerHTML += `
          <div class="error-item${cls}">
            <div class="error-phase">${err.dimensionName || ''} · ${err.severity === 'critical' ? '严重' : '注意'}</div>
            <div class="error-msg">${err.message}</div>
            ${err.fix ? `<div class="error-fix">💡 ${err.fix}</div>` : ''}
          </div>
        `;
      }
    } else {
      errorList.innerHTML += '<div style="color:var(--text-dim);font-size:0.78rem;padding:8px">暂无检测到明显错误，继续保持！</div>';
    }

    // Training tags
    const tags = document.getElementById('training-tags');
    tags.innerHTML = '<span style="font-size:0.7rem;color:var(--text-dim);margin-right:4px">🎯 训练建议:</span>';
    if (reviewData.training && reviewData.training.length > 0) {
      for (const t of reviewData.training) {
        tags.innerHTML += `<span class="training-tag">${t}</span>`;
      }
    } else {
      tags.innerHTML += '<span style="font-size:0.7rem;color:var(--text-dim)">继续保持当前水平</span>';
    }
  }

  return { reviewHand, drawRadar, renderReview, DIMENSIONS, scoreToGrade };
})();
