// ============================================================
// ai.js — AI opponent strategy (JS)
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
    const livePot = game.players.reduce((sum, pl) => sum + pl.currentBet, 0) || game.sb + game.bb;

    const rawS = strength.strength;
    const s = rawS * getPosMult(posName);

    const can = {};
    for (const a of legal) can[a.type] = a;

    const isPremium = rawS >= 78;
    const toCall = game.currentBet - p.roundBet;
    const isPreflop = game.phase === 'preflop';

    if (difficulty <= DIFFICULTY.EASY) {
      return basicDecision(s, can, legal, livePot, game, p, isPremium, toCall);
    } else if (difficulty <= DIFFICULTY.MEDIUM) {
      return mediumDecision(s, can, legal, livePot, game, p, draws, posName, isPremium, toCall, isPreflop);
    } else {
      return hardDecision(s, can, legal, livePot, game, p, draws, posName, strength, isPremium, toCall, isPreflop);
    }
  }

  // ── Easy AI ──
  function basicDecision(s, can, legal, pot, game, p, isPremium, toCall) {
    // Premium hands: always raise or call, NEVER fold
    if (isPremium) {
      if (can.raise) return can.raise;
      if (can.bet) return can.bet;
      if (can.call) return can.call;
      if (can.check) return can.check;
      return legal[0];
    }

    if (s >= 65) {
      if (can.raise) return can.raise;
      if (can.bet) return can.bet;
      if (can.call) return can.call;
      if (can.check) return can.check;
    } else if (s >= 40) {
      if (can.bet) return { type: 'bet', amount: validBet(game, pot, 0.4) };
      if (can.check) return can.check;
      if (can.call && toCall <= pot * 0.5) return can.call;
      if (can.call) return can.call;
      if (can.fold && toCall > pot * 1.2) return can.fold;
    } else {
      if (can.check) return can.check;
      if (can.call && toCall <= pot * 0.2) return can.call;
      if (can.raise && Math.random() < 0.08) return can.raise;
      if (can.fold && toCall > 0) return can.fold;
      if (can.call) return can.call;
    }
    return can.check || can.call || legal[0];
  }

  // ── Medium AI ──
  function mediumDecision(s, can, legal, pot, game, p, draws, pos, isPremium, toCall, isPreflop) {
    const raiseCount = game.events.filter(e => e.type === 'action' &&
      (e.action.type === 'raise' || e.action.type === 'bet')).length;

    // Premium: never fold, play aggressively
    if (isPremium) {
      if (can.raise && raiseCount < 8) {
        return { type: 'raise', amount: validRaise(game, p, pot) };
      }
      if (can.bet) return { type: 'bet', amount: validBet(game, pot, 0.7) };
      if (can.check && Math.random() < 0.10) return can.check;
      if (can.call) return can.call;
      return can.check || legal[0];
    }

    if (s >= 65) {
      if (can.raise && raiseCount < 5) {
        return { type: 'raise', amount: validRaise(game, p, pot) };
      }
      if (can.bet) return { type: 'bet', amount: validBet(game, pot, 0.55) };
      if (can.call) return can.call;
      if (can.check) return can.check;
    } else if (s >= 45) {
      if (can.bet) return { type: 'bet', amount: validBet(game, pot, 0.45) };
      if (can.raise && draws.length > 0 && raiseCount < 3) {
        return { type: 'raise', amount: validRaise(game, p, pot) };
      }
      if (can.check) return can.check;
      if (can.call && toCall <= pot * 0.45) return can.call;
      if (can.call) return can.call;
      return can.fold || can.check || legal[0];
    } else if (s >= 30) {
      if (can.bet && Math.random() < 0.25 && ['btn','co','hj'].includes(pos)) {
        return { type: 'bet', amount: validBet(game, pot, 0.35) };
      }
      if (can.check) return can.check;
      if (can.call && toCall <= pot * 0.3) return can.call;
      if (can.call) return can.call;
      return can.fold || legal[0];
    } else {
      if (can.check) return can.check;
      if (can.call && toCall <= pot * 0.15) return can.call;
      // Blind defense
      if (can.call && (pos === 'bb' || pos === 'sb') && toCall <= pot * 0.3) return can.call;
      // Occasional bluff from late position
      if (can.raise && Math.random() < 0.06 && ['btn','co'].includes(pos)) {
        return { type: 'raise', amount: validRaise(game, p, pot) };
      }
      if (can.fold) return can.fold;
      return can.call || legal[0];
    }
  }

  // ── Hard AI ──
  function hardDecision(s, can, legal, pot, game, p, draws, pos, strength, isPremium, toCall, isPreflop) {
    const raiseCount = game.events.filter(e => e.type === 'action' &&
      (e.action.type === 'raise' || e.action.type === 'bet')).length;

    // Premium: play fast but can trap
    if (isPremium) {
      if (Math.random() < 0.12 && can.check && (game.phase === 'flop' || game.phase === 'turn')) {
        return can.check;
      }
      if (can.raise && raiseCount < 10) {
        return { type: 'raise', amount: validRaise(game, p, pot) };
      }
      if (can.bet) return { type: 'bet', amount: validBet(game, pot, 0.75) };
      if (can.call) return can.call;
      return can.check || legal[0];
    }

    // Semi-bluff with strong draws
    if (draws.length > 0) {
      const totalOuts = draws.reduce((sum, d) => sum + d.outs, 0);
      if (totalOuts >= 12 && can.raise && raiseCount < 6) {
        return { type: 'raise', amount: validRaise(game, p, pot) };
      }
      if (totalOuts >= 8 && Math.random() < 0.5 && can.bet) {
        return { type: 'bet', amount: validBet(game, pot, 0.5) };
      }
    }

    // Position-based bluff
    if (can.bet && Math.random() < 0.18 && ['btn','co'].includes(pos) && s < 50) {
      return { type: 'bet', amount: validBet(game, pot, 0.4) };
    }

    return mediumDecision(s, can, legal, pot, game, p, draws, pos, isPremium, toCall, isPreflop);
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
