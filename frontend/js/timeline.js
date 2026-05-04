// ============================================================
// timeline.js — 3D timeline + rewind system
// ============================================================
window.PokerTimeline = (() => {
  'use strict';
  const E = window.PokerEngine;

  const PHASE_COLORS = {
    preflop: '#666', flop: '#f90', turn: '#b44dff', river: '#ff3366',
    showdown: '#00ff88', idle: '#444'
  };
  const PHASE_NAMES = { preflop:'翻前', flop:'翻牌', turn:'转牌', river:'河牌', showdown:'摊牌' };
  const ACTION_ICONS = { fold:'✕', check:'✓', call:'→', bet:'$', raise:'↑', allin:'★' };

  function render(game) {
    const container = document.getElementById('timeline');
    if (!container) return;
    container.innerHTML = '';

    const nodes = buildTimelineNodes(game);

    nodes.forEach((node, i) => {
      // Connector
      if (i > 0) {
        const conn = document.createElement('div');
        conn.className = 'timeline-connector';
        container.appendChild(conn);
      }

      const el = document.createElement('div');
      const phaseClass = node.phase ? `phase-${node.phase}` : '';
      const errorClass = node.hasError ? ' has-error' : '';
      el.className = `timeline-node ${phaseClass}${errorClass}`;

      if (node.isCurrent) el.classList.add('selected');

      el.innerHTML = `
        <span class="node-icon">${node.icon}</span>
        <span class="node-label">${node.label}</span>
      `;
      el.title = `${PHASE_NAMES[node.phase] || node.phase}: ${node.desc}`;
      el.onclick = () => {
        if (window.App) window.App.rewindTo(node.snapIdx);
      };

      container.appendChild(el);
    });

    // Auto-scroll to current
    const selected = container.querySelector('.selected');
    if (selected) selected.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }

  function buildTimelineNodes(game) {
    const nodes = [];
    const history = game.history;

    for (let i = 0; i < history.length; i++) {
      const snap = history[i];
      const trigger = snap.trigger;
      let icon = '○', label = '', desc = '';

      if (trigger === 'hand_start') {
        icon = '🂠'; label = '发牌'; desc = '发牌';
      } else if (trigger === 'fold') {
        icon = '✕'; label = '弃牌'; desc = '玩家弃牌';
      } else if (trigger === 'check') {
        icon = '✓'; label = '过牌'; desc = '过牌';
      } else if (trigger === 'call') {
        icon = '→'; label = '跟注'; desc = '跟注';
      } else if (trigger === 'bet') {
        icon = '$'; label = '下注'; desc = '下注';
      } else if (trigger === 'raise') {
        icon = '↑'; label = '加注'; desc = '加注';
      } else if (trigger === 'allin') {
        icon = '★'; label = 'All-in'; desc = '全下';
      } else if (trigger === 'phase_change') {
        icon = '▸'; label = PHASE_NAMES[snap.phase] || snap.phase; desc = '进入' + (PHASE_NAMES[snap.phase] || snap.phase);
      } else {
        icon = '·'; label = trigger; desc = trigger;
      }

      const isCurrent = i === history.length - 1;

      nodes.push({
        snapIdx: i,
        phase: snap.phase,
        icon, label, desc,
        isCurrent,
        hasError: false, // set by review later
      });
    }

    return nodes;
  }

  function highlightErrorNodes(errorSteps) {
    // Mark specific timeline nodes as having errors
    const nodes = document.querySelectorAll('.timeline-node');
    for (const stepIdx of errorSteps) {
      if (nodes[stepIdx]) nodes[stepIdx].classList.add('has-error');
    }
  }

  return { render, buildTimelineNodes, highlightErrorNodes, PHASE_NAMES, PHASE_COLORS };
})();
