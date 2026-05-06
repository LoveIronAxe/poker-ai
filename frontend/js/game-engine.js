// ============================================================
// game-engine.js — Texas Hold'em core engine (JS port)
// ============================================================
window.PokerEngine = (() => {
  'use strict';

  // ── Card utilities ──
  const SUITS = ['s','h','d','c'];
  const SUIT_SYMBOLS = { s:'♠', h:'♥', d:'♦', c:'♣' };
  const RANK_NAMES = { 2:'2',3:'3',4:'4',5:'5',6:'6',7:'7',8:'8',9:'9',10:'T',11:'J',12:'Q',13:'K',14:'A' };

  function cardStr(card) { return RANK_NAMES[card.rank] + SUIT_SYMBOLS[card.suit]; }
  function cardKey(card) { return RANK_NAMES[card.rank] + SUITS[card.suit]; }
  function isRed(card) { return card.suit === 'h' || card.suit === 'd'; }

  function makeDeck() {
    const deck = [];
    for (let r = 2; r <= 14; r++)
      for (const s of SUITS)
        deck.push({ rank: r, suit: s });
    return deck;
  }

  function shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  // ── Hand Evaluation ──
  const HAND_RANKS = {
    HIGH_CARD: 1, ONE_PAIR: 2, TWO_PAIR: 3, TRIPS: 4,
    STRAIGHT: 5, FLUSH: 6, FULL_HOUSE: 7, QUADS: 8,
    STRAIGHT_FLUSH: 9, ROYAL_FLUSH: 10
  };
  const HAND_NAMES_CN = {
    1:'高牌',2:'一对',3:'两对',4:'三条',5:'顺子',
    6:'同花',7:'葫芦',8:'四条',9:'同花顺',10:'皇家同花顺'
  };

  function eval5Cards(cards) {
    const ranks = cards.map(c => c.rank).sort((a,b) => b-a);
    const suits = cards.map(c => c.suit);
    const isFlush = new Set(suits).size === 1;

    // Check straight
    let isStraight = false, straightHigh = 0;
    const uniqueRanks = [...new Set(ranks)].sort((a,b) => b-a);
    if (uniqueRanks.length >= 5) {
      for (let i = 0; i <= uniqueRanks.length - 5; i++) {
        if (uniqueRanks[i] - uniqueRanks[i+4] === 4) {
          isStraight = true; straightHigh = uniqueRanks[i]; break;
        }
      }
    }
    // Wheel
    if (!isStraight && uniqueRanks.includes(14) && uniqueRanks.includes(2) &&
        uniqueRanks.includes(3) && uniqueRanks.includes(4) && uniqueRanks.includes(5)) {
      isStraight = true; straightHigh = 5;
    }

    // Rank counts
    const countMap = {};
    for (const r of ranks) countMap[r] = (countMap[r]||0)+1;
    const groups = Object.entries(countMap).map(([r,c]) => [+r,c]).sort((a,b) => b[1]-a[1] || b[0]-a[0]);

    if (isFlush && isStraight) {
      if (straightHigh === 14) return { rank: HAND_RANKS.ROYAL_FLUSH, kickers: [14], name: '皇家同花顺' };
      return { rank: HAND_RANKS.STRAIGHT_FLUSH, kickers: [straightHigh], name: '同花顺' };
    }
    if (groups[0][1] === 4) {
      const kicker = groups[1] ? groups[1][0] : ranks.find(r => r !== groups[0][0]);
      return { rank: HAND_RANKS.QUADS, kickers: [groups[0][0], kicker], name: '四条' };
    }
    if (groups[0][1] === 3 && groups[1] && groups[1][1] >= 2) {
      return { rank: HAND_RANKS.FULL_HOUSE, kickers: [groups[0][0], groups[1][0]], name: '葫芦' };
    }
    if (isFlush) {
      return { rank: HAND_RANKS.FLUSH, kickers: ranks.slice(0,5), name: '同花' };
    }
    if (isStraight) {
      return { rank: HAND_RANKS.STRAIGHT, kickers: [straightHigh], name: '顺子' };
    }
    if (groups[0][1] === 3) {
      const kickers = groups.slice(1).map(g => g[0]).sort((a,b) => b-a).slice(0,2);
      return { rank: HAND_RANKS.TRIPS, kickers: [groups[0][0], ...kickers], name: '三条' };
    }
    if (groups[0][1] === 2 && groups[1] && groups[1][1] === 2) {
      const kicker = groups.slice(2).map(g => g[0]).sort((a,b) => b-a)[0] || 0;
      return { rank: HAND_RANKS.TWO_PAIR, kickers: [groups[0][0], groups[1][0], kicker], name: '两对' };
    }
    if (groups[0][1] === 2) {
      const kickers = groups.slice(1).map(g => g[0]).sort((a,b) => b-a).slice(0,3);
      return { rank: HAND_RANKS.ONE_PAIR, kickers: [groups[0][0], ...kickers], name: '一对' };
    }
    return { rank: HAND_RANKS.HIGH_CARD, kickers: ranks.slice(0,5), name: '高牌' };
  }

  function evaluate(holeCards, communityCards) {
    const all = [...holeCards, ...communityCards];
    if (all.length < 5) {
      const r = all.map(c => c.rank).sort((a,b) => b-a);
      return { rank: HAND_RANKS.HIGH_CARD, kickers: r, name: '高牌' };
    }
    // Try all C(n,5) combos
    const n = all.length;
    let best = null;
    for (let a = 0; a < n; a++) {
      for (let b = a+1; b < n; b++) {
        for (let c = b+1; c < n; c++) {
          for (let d = c+1; d < n; d++) {
            for (let e = d+1; e < n; e++) {
              const r = eval5Cards([all[a],all[b],all[c],all[d],all[e]]);
              if (!best || compareHands(r, best) > 0) best = r;
            }
          }
        }
      }
    }
    return best;
  }

  function compareHands(a, b) {
    if (a.rank !== b.rank) return a.rank - b.rank;
    for (let i = 0; i < Math.max(a.kickers.length, b.kickers.length); i++) {
      const ak = a.kickers[i] || 0, bk = b.kickers[i] || 0;
      if (ak !== bk) return ak - bk;
    }
    return 0;
  }

  // ── Quick equity estimate (simplified) ──
  function quickEquity(hole, community) {
    const result = evaluate(hole, community);
    if (community.length === 0) {
      return preflopStrength(hole);
    }
    const base = result.rank * 9;
    return { strength: Math.min(95, base + 10), handType: result.name, rank: result.rank };
  }

  function preflopStrength(hole) {
    const [r1, r2] = [hole[0].rank, hole[1].rank].sort((a,b) => b-a);
    const suited = hole[0].suit === hole[1].suit;
    if (r1 === r2 && r1 >= 10) return { strength: 90, category: 'premium' };
    if (r1 === 14 && r2 >= 11 && suited) return { strength: 88, category: 'premium' };
    if (r1 === 14 && r2 >= 12) return { strength: 85, category: 'premium' };
    if (r1 === r2 && r1 >= 7) return { strength: 75, category: 'strong' };
    if (r1 >= 13 && r2 >= 10 && suited) return { strength: 72, category: 'strong' };
    if (r1 === 14 && r2 >= 9 && suited) return { strength: 68, category: 'strong' };
    if (r1 === r2) return { strength: 55, category: 'playable' };
    if (suited && (r1 - r2) <= 2 && r2 >= 8) return { strength: 52, category: 'playable' };
    if (r1 >= 12 && r2 >= 9) return { strength: 48, category: 'playable' };
    return { strength: 30, category: 'weak' };
  }

  // ── Detect draws ──
  function detectDraws(hole, community) {
    const draws = [];
    const all = [...hole, ...community];
    if (all.length < 5) return draws;
    const ranks = all.map(c => c.rank);
    const suits = all.map(c => c.suit);

    // Flush draw
    const suitCounts = {};
    for (const s of suits) suitCounts[s] = (suitCounts[s]||0)+1;
    for (const [s, c] of Object.entries(suitCounts)) {
      if (c === 4) draws.push({ type: 'flush_draw', outs: 9, desc: '同花听牌' });
    }

    // Straight draw (simplified)
    const unique = [...new Set(ranks)].sort((a,b) => a-b);
    for (let i = 0; i < unique.length - 2; i++) {
      const gap = unique[i+2] - unique[i];
      if (gap <= 4 && gap > 0) {
        if (unique[i+2] - unique[i] === 3) {
          draws.push({ type: 'open_ended', outs: 8, desc: '两头顺听牌' });
        } else if (unique[i+2] - unique[i] === 4) {
          draws.push({ type: 'gutshot', outs: 4, desc: '卡顺听牌' });
        }
      }
    }
    return draws;
  }

  // ── Game State ──
  function createGame(numPlayers, sb, bb, stacks) {
    const g = {
      numPlayers,
      sb, bb,
      players: [],
      communityCards: [],
      deck: [],
      pot: 0,
      sidePots: [],
      phase: 'preflop', // preflop|flop|turn|river|showdown|idle
      dealerIdx: 0,
      currentIdx: 0,
      currentBet: 0,
      minRaise: bb,
      lastRaise: bb,
      actionsThisRound: [],
      playersActed: new Set(),
      handNumber: 0,
      history: [], // snapshots for rewind
      events: [],
    };
    for (let i = 0; i < numPlayers; i++) {
      const s = Array.isArray(stacks) ? (stacks[i] || 1000) : (stacks || 1000);
      g.players.push({
        id: i, name: i === 0 ? '你' : `AI-${i}`,
        stack: s, holeCards: [], currentBet: 0, roundBet: 0,
        status: 'waiting', // waiting|active|folded|allin|out
        lastAction: '', isHuman: i === 0
      });
    }
    return g;
  }

  function resetForHand(g) {
    g.communityCards = [];
    g.pot = 0; g.sidePots = [];
    g.currentBet = 0; g.minRaise = g.bb; g.lastRaise = g.bb;
    g.actionsThisRound = [];
    g.playersActed = new Set();
    g.events = [];
    g.phase = 'preflop';
    for (const p of g.players) {
      if (p.stack <= 0) { p.status = 'out'; continue; }
      p.holeCards = []; p.currentBet = 0; p.roundBet = 0;
      p.lastAction = ''; p.status = 'waiting';
    }
    g.deck = shuffle(makeDeck());
  }

  function dealHoleCards(g) {
    for (const p of g.players) {
      if (p.status !== 'out') {
        p.holeCards = [g.deck.pop(), g.deck.pop()];
      }
    }
  }

  function postBlinds(g) {
    const sbIdx = nextActive(g, g.dealerIdx);
    const bbIdx = nextActive(g, sbIdx);
    const sbAmt = Math.min(g.sb, g.players[sbIdx].stack);
    const bbAmt = Math.min(g.bb, g.players[bbIdx].stack);

    g.players[sbIdx].stack -= sbAmt;
    g.players[sbIdx].currentBet += sbAmt;
    g.players[sbIdx].roundBet += sbAmt;
    g.players[sbIdx].lastAction = `SB ${sbAmt}`;

    g.players[bbIdx].stack -= bbAmt;
    g.players[bbIdx].currentBet += bbAmt;
    g.players[bbIdx].roundBet += bbAmt;
    g.players[bbIdx].lastAction = `BB ${bbAmt}`;

    g.currentBet = bbAmt;
    // First to act after BB
    const utg = nextActive(g, bbIdx);
    for (const p of g.players) {
      if (p.status !== 'out') p.status = 'active';
    }
    g.currentIdx = utg;
  }

  function startNewHand(g) {
    g.handNumber++;
    resetForHand(g);
    const active = g.players.filter(p => p.stack > 0);
    if (active.length < 2) return false;
    g.dealerIdx = nextActive(g, g.dealerIdx);
    dealHoleCards(g);
    postBlinds(g);
    g.events.push({ type: 'deal', phase: 'preflop', desc: '发牌' });
    saveSnapshot(g, 'hand_start');
    return true;
  }

  function nextActive(g, fromIdx) {
    const n = g.players.length;
    for (let off = 1; off <= n; off++) {
      const idx = (fromIdx + off) % n;
      if (g.players[idx].status !== 'out') return idx;
    }
    return fromIdx;
  }

  // Find next player who can act (status === 'active') — used post-street
  function nextCanAct(g, fromIdx) {
    const n = g.players.length;
    for (let off = 1; off <= n; off++) {
      const idx = (fromIdx + off) % n;
      if (g.players[idx].status === 'active') return idx;
    }
    return -1; // no one can act
  }

  // ── Actions ──
  function getLegalActions(g, playerIdx) {
    const p = g.players[playerIdx];
    if (p.status !== 'active') return [];
    const toCall = g.currentBet - p.roundBet;
    const actions = [];

    if (toCall === 0) {
      actions.push({ type: 'check', amount: 0 });
    } else {
      actions.push({ type: 'fold', amount: 0 });
      if (toCall >= p.stack) {
        actions.push({ type: 'allin', amount: p.stack });
      } else {
        actions.push({ type: 'call', amount: toCall });
      }
    }

    if (toCall === 0) {
      const minBet = Math.max(g.minRaise, g.bb);
      if (p.stack > minBet) actions.push({ type: 'bet', amount: minBet, min: minBet, max: p.stack });
      if (p.stack > 0) actions.push({ type: 'allin', amount: p.stack });
    } else if (p.stack + p.roundBet > g.currentBet + g.lastRaise) {
      const minTo = g.currentBet + g.lastRaise;
      actions.push({ type: 'raise', amount: minTo - p.roundBet, min: minTo - p.roundBet, max: p.stack });
      if (p.stack > 0) actions.push({ type: 'allin', amount: p.stack });
    } else if (p.stack > 0 && toCall > 0) {
      // Can only call or all-in
    }

    return actions;
  }

  function applyAction(g, playerIdx, action) {
    const p = g.players[playerIdx];
    g.playersActed.add(playerIdx);
    g.events.push({ type: 'action', phase: g.phase, playerIdx, action: { ...action } });

    switch (action.type) {
      case 'fold':
        p.status = 'folded';
        p.lastAction = 'Fold';
        break;
      case 'check':
        p.lastAction = 'Check';
        break;
      case 'call':
        p.stack -= action.amount;
        p.currentBet += action.amount;
        p.roundBet += action.amount;
        p.lastAction = `Call ${action.amount}`;
        break;
      case 'bet':
        p.stack -= action.amount;
        p.currentBet += action.amount;
        p.roundBet += action.amount;
        g.currentBet = p.roundBet;
        g.lastRaise = action.amount;
        g.minRaise = action.amount;
        g.playersActed = new Set([playerIdx]);
        p.lastAction = `Bet ${action.amount}`;
        break;
      case 'raise':
        p.stack -= action.amount;
        p.currentBet += action.amount;
        const oldRound = p.roundBet;
        p.roundBet += action.amount;
        g.lastRaise = p.roundBet - g.currentBet;
        g.currentBet = p.roundBet;
        g.minRaise = g.lastRaise;
        g.playersActed = new Set([playerIdx]);
        p.lastAction = `Raise ${action.amount}`;
        break;
      case 'allin':
        const amt = Math.min(action.amount, p.stack);
        p.stack -= amt;
        p.currentBet += amt;
        p.roundBet += amt;
        p.status = 'allin';
        const newBet = p.roundBet;
        if (newBet > g.currentBet) {
          g.lastRaise = newBet - g.currentBet;
          g.currentBet = newBet;
          g.minRaise = Math.max(g.minRaise, g.lastRaise);
          g.playersActed = new Set([playerIdx]);
        }
        p.lastAction = 'All-in';
        break;
    }

    saveSnapshot(g, action.type);
    return checkRoundComplete(g);
  }

  function checkRoundComplete(g) {
    const activePlayers = g.players.filter(p => p.status === 'active');
    const alivePlayers = g.players.filter(p => p.status === 'active' || p.status === 'allin' || p.status === 'waiting');

    // Players who have chips remaining and haven't folded
    const stillIn = g.players.filter(p => p.status !== 'folded' && p.status !== 'out');

    // Only end hand if NO active players AND NO waiting players with chips
    // (all remaining players have either folded or are all-in)
    if (stillIn.length <= 1) {
      endHand(g);
      return 'hand_over';
    }

    // If no active players but some are waiting, advance to next phase
    if (activePlayers.length === 0) {
      advancePhase(g);
      return 'phase_advanced';
    }

    const allBetsMatch = activePlayers.every(p => p.roundBet === g.currentBet);
    const allActed = activePlayers.every(p => g.playersActed.has(g.players.indexOf(p)));

    if (allBetsMatch && allActed) {
      advancePhase(g);
      return 'phase_advanced';
    }

    // Move to next player (skip folded/allin/waiting)
    const n = g.players.length;
    for (let off = 1; off <= n; off++) {
      const idx = (g.currentIdx + off) % n;
      if (g.players[idx].status === 'active') {
        g.currentIdx = idx;
        return 'next_player';
      }
    }
    // No more active players, advance phase
    advancePhase(g);
    return 'phase_advanced';
  }

  function advancePhase(g) {
    switch (g.phase) {
      case 'preflop':
        g.deck.pop(); // burn
        g.communityCards.push(g.deck.pop(), g.deck.pop(), g.deck.pop());
        g.phase = 'flop';
        g.events.push({ type: 'deal', phase: 'flop', desc: '翻牌' });
        break;
      case 'flop':
        g.deck.pop();
        g.communityCards.push(g.deck.pop());
        g.phase = 'turn';
        g.events.push({ type: 'deal', phase: 'turn', desc: '转牌' });
        break;
      case 'turn':
        g.deck.pop();
        g.communityCards.push(g.deck.pop());
        g.phase = 'river';
        g.events.push({ type: 'deal', phase: 'river', desc: '河牌' });
        break;
      case 'river':
        showdown(g);
        return;
    }

    // Reset round
    for (const p of g.players) {
      p.roundBet = 0;
      if (p.status === 'waiting') p.status = 'active';
    }
    g.currentBet = 0;
    g.lastRaise = g.bb;
    g.minRaise = g.bb;
    g.actionsThisRound = [];
    g.playersActed = new Set();

    // First to act after dealer (postflop) — must be an active player
    const first = nextCanAct(g, g.dealerIdx);
    g.currentIdx = first;

    // If only one can act at start of street (everyone else folded), end hand
    const canAct = g.players.filter(p => p.status === 'active');
    if (canAct.length <= 1) {
      // Only one player left who hasn't folded - they win
      endHand(g);
      return;
    }

    saveSnapshot(g, 'phase_change');
  }

  function showdown(g) {
    g.phase = 'showdown';
    g.events.push({ type: 'showdown', phase: 'showdown', desc: '摊牌' });

    const alive = g.players.filter(p => p.status !== 'folded' && p.status !== 'out');
    const results = alive.map(p => ({
      player: p,
      hand: evaluate(p.holeCards, g.communityCards)
    }));

    // Find winner
    let best = null, winners = [];
    for (const r of results) {
      if (!best || compareHands(r.hand, best) > 0) {
        best = r.hand;
        winners = [r.player];
      } else if (best && compareHands(r.hand, best) === 0) {
        winners.push(r.player);
      }
    }

    // Calculate pot
    const totalPot = g.players.reduce((s, p) => s + p.currentBet, 0);
    const winShare = Math.floor(totalPot / winners.length);
    for (const w of winners) w.stack += winShare;

    g.events.push({ type: 'result', winners: winners.map(w => w.id), pot: totalPot });
    g.phase = 'idle';

    // Save to local storage
    saveHandToHistory(g, results, winners, totalPot);
  }

  function endHand(g) {
    const totalPot = g.players.reduce((s, p) => s + p.currentBet, 0);
    const winner = g.players.find(p => p.status !== 'folded' && p.status !== 'out');
    if (winner) {
      winner.stack += totalPot;
      g.events.push({ type: 'result', winners: [winner.id], pot: totalPot, reason: 'all_folded' });
    }
    saveHandToHistory(g, [], winner ? [winner] : [], totalPot);
    g.phase = 'idle';
  }

  // ── Snapshots for rewind ──
  function saveSnapshot(g, trigger) {
    const snap = {
      trigger,
      phase: g.phase,
      communityCards: g.communityCards.map(c => ({...c})),
      players: g.players.map(p => ({
        id: p.id, name: p.name, stack: p.stack,
        holeCards: p.holeCards.map(c => ({...c})),
        currentBet: p.currentBet, roundBet: p.roundBet,
        status: p.status, lastAction: p.lastAction, isHuman: p.isHuman
      })),
      currentIdx: g.currentIdx,
      currentBet: g.currentBet,
      dealerIdx: g.dealerIdx,
      events: g.events.map(e => ({...e})),
      pot: g.players.reduce((s, p) => s + p.currentBet, 0),
    };
    g.history.push(snap);
  }

  function restoreSnapshot(g, snapIdx) {
    const snap = g.history[snapIdx];
    if (!snap) return false;
    g.phase = snap.phase;
    g.communityCards = snap.communityCards.map(c => ({...c}));
    g.players = snap.players.map(p => ({
      ...p, holeCards: p.holeCards.map(c => ({...c}))
    }));
    g.currentIdx = snap.currentIdx;
    g.currentBet = snap.currentBet;
    g.dealerIdx = snap.dealerIdx;
    g.events = snap.events.map(e => ({...e}));
    g.history = g.history.slice(0, snapIdx + 1);
    g.playersActed = new Set();
    return true;
  }

  // ── Local Storage ──
  function saveHandToHistory(g, results, winners, pot) {
    try {
      const record = {
        date: new Date().toISOString(),
        handNumber: g.handNumber,
        communityCards: g.communityCards.map(cardKey),
        players: g.players.map(p => ({
          name: p.name, holeCards: p.holeCards.map(cardKey),
          stack: p.stack, status: p.status, isHuman: p.isHuman
        })),
        winners: winners.map(w => w.id),
        pot,
        events: g.events.slice(-30), // keep last 30 events
        phase: g.phase,
      };
      const history = JSON.parse(localStorage.getItem('poker_hand_history') || '[]');
      history.unshift(record);
      if (history.length > 100) history.length = 100;
      localStorage.setItem('poker_hand_history', JSON.stringify(history));
    } catch(e) { console.warn('Failed to save hand history', e); }
  }

  function getHandHistory() {
    try {
      return JSON.parse(localStorage.getItem('poker_hand_history') || '[]');
    } catch(e) { return []; }
  }

  // ── User Profile Storage ──
  function saveUserProfile(profile) {
    try {
      localStorage.setItem('poker_user_profile', JSON.stringify(profile));
    } catch(e) {}
  }

  function getUserProfile() {
    try {
      return JSON.parse(localStorage.getItem('poker_user_profile') || '{}');
    } catch(e) { return {}; }
  }

  // ── API Config Storage ──
  function saveAPIConfig(config) {
    try {
      localStorage.setItem('poker_api_config', JSON.stringify(config));
    } catch(e) {}
  }

  function getAPIConfig() {
    try {
      return JSON.parse(localStorage.getItem('poker_api_config') || '{}');
    } catch(e) { return {}; }
  }

  // ── Attach Review to Most Recent History ──
  function attachReviewToHistory(review) {
    try {
      const history = JSON.parse(localStorage.getItem('poker_hand_history') || '[]');
      if (history.length > 0) {
        history[0].review = {
          totalScore: review.totalScore,
          grade: review.grade,
          dimensions: review.dimensions,
        };
        localStorage.setItem('poker_hand_history', JSON.stringify(history));
      }
    } catch(e) { console.warn('Failed to attach review', e); }
  }

  // ── Exports ──
  return {
    SUITS, SUIT_SYMBOLS, RANK_NAMES, HAND_RANKS, HAND_NAMES_CN,
    cardStr, cardKey, isRed, makeDeck, shuffle,
    evaluate, eval5Cards, compareHands, quickEquity, detectDraws,
    createGame, startNewHand, getLegalActions, applyAction,
    advancePhase, showdown, endHand, nextActive, nextCanAct,
    saveSnapshot, restoreSnapshot,
    saveHandToHistory, getHandHistory,
    attachReviewToHistory,
    saveUserProfile, getUserProfile,
    saveAPIConfig, getAPIConfig,
  };
})();
