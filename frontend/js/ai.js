// ============================================================
// ai.js — AI opponent using strategy from Python backend
// ============================================================
window.PokerAI = (() => {
  'use strict';
  const E = window.PokerEngine;

  const DIFFICULTY = { EASY: 1, MEDIUM: 2, HARD: 3 };

  function decide(game, playerIdx, difficulty) {
    const p = game.players[playerIdx];
    const legal = E.getLegalActions(game, playerIdx);
    if (!legal.length) return { type: 'fold', amount: 0 };

    const strength = E.quickEquity(p.holeCards, game.communityCards);
    const draws = E.detectDraws(p.holeCards, game.communityCards);
    const posName = getPosName(game, playerIdx);
    const livePot = game.players.reduce((s, p) => s + p.currentBet, 0) || game.sb + game.bb;

    const s = strength.strength * getPosMult(posName);

    const can = {};
    for (const a of legal) can[a.type] = a;

    if (difficulty <= DIFFICULTY.EASY) {
      return basicDecision(s, can, legal, livePot, game, p);
    } else if (difficulty <= DIFFICULTY.MEDIUM) {
      return mediumDecision(s, can, legal, livePot, game, p, draws, posName);
    } else {
      return hardDecision(s, can, legal, livePot, game, p, draws, posName, strength);
    }
  }

  function basicDecision(s, can, legal, pot, game, p) {
    if (s >= 80) {
      if (can.raise) return can.raise;
      if (can.bet) return can.bet;
      if (can.check) return can.check;
      if (can.call) return can.call;
    } else if (s >= 55) {
      if (can.bet) return can.bet;
      if (can.check) return can.check;
      if (can.call && can.call.amount <= pot * 0.3) return can.call;
      if (can.fold) return can.fold;
    } else {
      if (can.check) return can.check;
      if (can.fold) return can.fold;
    }
    return legal[0];
  }

  function mediumDecision(s, can, legal, pot, game, p, draws, pos) {
    const toCall = game.currentBet - p.roundBet;
    // Don't re-raise too much
    const raiseCount = game.events.filter(e => e.type === 'action' &&
      (e.action.type === 'raise' || e.action.type === 'bet')).length;

    if (s >= 78) {
      if (can.raise && raiseCount < 6) {
        const amt = validRaise(game, p, pot);
        return { type: 'raise', amount: amt };
      }
      if (can.bet) return { type: 'bet', amount: validBet(game, pot, 0.66) };
      if (can.check && Math.random() < 0.12) return can.check; // trap
      if (can.call) return can.call;
      return can.check || legal[0];
    } else if (s >= 55) {
      if (can.bet) return { type: 'bet', amount: validBet(game, pot, 0.5) };
      if (can.raise && draws.length > 0) {
        return { type: 'raise', amount: validRaise(game, p, pot) };
      }
      if (can.check) return can.check;
      if (can.call && toCall <= pot * 0.25) return can.call;
      return can.fold || can.check || legal[0];
    } else if (s >= 35) {
      if (can.bet && Math.random() < 0.2 && ['btn','co','hj'].includes(pos)) {
        return { type: 'bet', amount: validBet(game, pot, 0.4) };
      }
      if (can.check) return can.check;
      if (can.call && toCall <= pot * 0.15) return can.call;
      return can.fold || legal[0];
    } else {
      if (can.check) return can.check;
      return can.fold || legal[0];
    }
  }

  function hardDecision(s, can, legal, pot, game, p, draws, pos, strength) {
    const toCall = game.currentBet - p.roundBet;
    const raiseCount = game.events.filter(e => e.type === 'action' &&
      (e.action.type === 'raise' || e.action.type === 'bet')).length;

    // Mixed strategy
    if (s >= 80) {
      if (Math.random() < 0.15 && can.check && game.phase === 'flop') return can.check;
      if (can.raise && raiseCount < 8) {
        return { type: 'raise', amount: validRaise(game, p, pot) };
      }
      if (can.bet) return { type: 'bet', amount: validBet(game, pot, 0.7) };
      if (can.call) return can.call;
      return can.check || legal[0];
    }

    // Semi-bluff draws
    if (draws.length > 0 && (strength.rank || 1) <= 4) {
      const totalOuts = draws.reduce((s, d) => s + d.outs, 0);
      if (totalOuts >= 12 && can.raise) {
        return { type: 'raise', amount: validRaise(game, p, pot) };
      }
      if (totalOuts >= 8 && Math.random() < 0.55 && can.bet) {
        return { type: 'bet', amount: validBet(game, pot, 0.55) };
      }
    }

    return mediumDecision(s, can, legal, pot, game, p, draws, pos);
  }

  function validBet(game, pot, pct) {
    const min = Math.max(game.bb, game.minRaise);
    const desired = Math.max(min, Math.floor(pot * pct));
    return Math.max(min, desired);
  }

  function validRaise(game, p, pot) {
    const current = game.currentBet;
    const minR = game.minRaise;
    if (current === 0) {
      return Math.max(game.bb * 2, Math.floor(pot * 0.66));
    }
    const desiredTo = current + Math.max(minR, Math.floor(pot * 0.5));
    return desiredTo - p.roundBet;
  }

  function getPosName(game, playerIdx) {
    const rel = (playerIdx - game.dealerIdx + game.numPlayers) % game.numPlayers;
    const names = { 0: 'btn', 1: 'sb', 2: 'bb', 3: 'utg', 4: 'mp', 5: 'mp', 6: 'hj', 7: 'co' };
    return names[rel] || 'utg';
  }

  function getPosMult(pos) {
    const mults = { btn: 1.3, co: 1.15, hj: 1.05, mp: 1.0, utg: 0.9, sb: 0.85, bb: 0.95 };
    return mults[pos] || 1.0;
  }

  return { decide, DIFFICULTY, getPosName, getPosMult, validBet, validRaise };
})();
