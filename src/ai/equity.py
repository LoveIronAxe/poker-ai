"""Monte Carlo equity calculator for Texas Hold'em."""

import random
from itertools import combinations

from ..engine.card import Card, Rank
from ..engine.deck import Deck
from ..engine.hand import HandEvaluator


class EquityCalculator:
    """Calculate hand vs hand or hand vs range equity using Monte Carlo simulation."""

    def __init__(self, num_simulations: int = 5000, seed: int = None):
        self.num_simulations = num_simulations
        self._rng = random.Random(seed)

    def hand_vs_hand(self, hole1: list[Card], hole2: list[Card],
                     community: list[Card] = None,
                     dead_cards: list[Card] = None) -> tuple[float, float, float]:
        """Calculate equity of hole1 vs hole2 given known community cards.

        Returns (win%, lose%, tie%) for hole1.
        """
        community = community or []
        dead_cards = dead_cards or []
        known = set(hole1 + hole2 + community + dead_cards)

        # If enough community cards, do exhaustive enumeration
        remaining = [Card.from_int(i) for i in range(52)
                     if Card.from_int(i) not in known]

        cards_needed = 5 - len(community)
        if cards_needed == 0:
            # All community cards known — just compare
            r1 = HandEvaluator.evaluate(hole1, community)
            r2 = HandEvaluator.evaluate(hole2, community)
            if r1 > r2:
                return (1.0, 0.0, 0.0)
            elif r1 < r2:
                return (0.0, 1.0, 0.0)
            else:
                return (0.0, 0.0, 1.0)

        # Run Monte Carlo
        wins = ties = 0
        total = min(self.num_simulations,
                    self._count_combinations(len(remaining), cards_needed))

        for _ in range(total):
            dealt = self._rng.sample(remaining, cards_needed)
            full_community = community + dealt
            r1 = HandEvaluator.evaluate(hole1, full_community)
            r2 = HandEvaluator.evaluate(hole2, full_community)
            if r1 > r2:
                wins += 1
            elif r1 == r2:
                ties += 1

        win_pct = wins / total * 100 if total > 0 else 0
        lose_pct = (total - wins - ties) / total * 100 if total > 0 else 0
        tie_pct = ties / total * 100 if total > 0 else 0
        return (win_pct, lose_pct, tie_pct)

    def hand_vs_n_players(self, hole: list[Card], num_opponents: int,
                          community: list[Card] = None) -> float:
        """Quick estimate: equity of hole cards vs N random hands."""
        community = community or []
        known = set(hole + community)
        remaining = [Card.from_int(i) for i in range(52)
                     if Card.from_int(i) not in known]

        cards_needed = 5 - len(community)
        wins = 0
        total = min(self.num_simulations, 3000)

        for _ in range(total):
            sim_cards = self._rng.sample(remaining,
                                        cards_needed + 2 * num_opponents)
            opp_holes = [sim_cards[i*2:(i+1)*2] for i in range(num_opponents)]
            sim_community = community + sim_cards[2*num_opponents:]

            my_result = HandEvaluator.evaluate(hole, sim_community)
            opp_results = [HandEvaluator.evaluate(oh, sim_community) for oh in opp_holes]

            if all(my_result >= r for r in opp_results):
                wins += 1

        return wins / total * 100 if total > 0 else 0

    @staticmethod
    def quick_equity(hole: list[Card], community: list[Card] = None) -> dict:
        """Fast approximate equity stats using precomputed data."""
        community = community or []
        if len(community) == 0:
            return EquityCalculator._preflop_strength(hole)
        elif len(community) == 3:
            return EquityCalculator._flop_strength(hole, community)
        else:
            return {"note": "Use Monte Carlo for accurate equity"}

    @staticmethod
    def _preflop_strength(hole: list[Card]) -> dict:
        """Precomputed preflop hand strength categories."""
        r1, r2 = hole[0].rank.value, hole[1].rank.value
        if r1 < r2:
            r1, r2 = r2, r1
        suited = hole[0].suit == hole[1].suit
        gap = r1 - r2

        # Premium
        if r1 == r2 and r1 >= 10:  # JJ+
            return {"category": "premium", "strength": 90, "suggestion": "Raise/3-bet"}
        if r1 == 14 and r2 >= 11 and suited:  # AKs, AQs
            return {"category": "premium", "strength": 88, "suggestion": "Raise/3-bet"}
        if r1 == 14 and r2 >= 12:  # AK, AQ
            return {"category": "premium", "strength": 85, "suggestion": "Raise"}

        # Strong
        if r1 == r2 and r1 >= 7:  # 77-TT
            return {"category": "strong", "strength": 75, "suggestion": "Raise"}
        if r1 >= 13 and r2 >= 10 and suited:  # KTs+, QJs
            return {"category": "strong", "strength": 72, "suggestion": "Raise/Call"}
        if r1 == 14 and r2 >= 9 and suited:  # A9s-AJs
            return {"category": "strong", "strength": 70, "suggestion": "Raise/Call"}
        if r1 == 14 and r2 >= 10:  # AT-AJ
            return {"category": "strong", "strength": 68, "suggestion": "Raise/Call"}

        # Playable
        if r1 == r2:  # Any pocket pair
            return {"category": "playable", "strength": 55, "suggestion": "Limp/Call"}
        if suited and gap <= 2 and r1 >= 8:  # Suited connectors
            return {"category": "playable", "strength": 52, "suggestion": "Call in position"}
        if r1 >= 12 and r2 >= 9:  # K9+, Q9+, J9+
            return {"category": "playable", "strength": 48, "suggestion": "Late position call"}
        if suited and r1 >= 10 and gap <= 1:  # Suited broadway connectors
            return {"category": "playable", "strength": 48, "suggestion": "Late position call"}

        # Weak
        return {"category": "weak", "strength": 30, "suggestion": "Fold (early), Call (blind defense)"}

    @staticmethod
    def _flop_strength(hole: list[Card], community: list[Card]) -> dict:
        """Assess hand strength after the flop."""
        result = HandEvaluator.evaluate(hole, community)
        return {
            "hand_type": result.rank.name_cn(),
            "strength": min(95, result.rank.value * 10),
            "kickers": result.kickers
        }

    @staticmethod
    def _count_combinations(n: int, k: int) -> int:
        if k < 0 or k > n:
            return 0
        result = 1
        for i in range(k):
            result = result * (n - i) // (i + 1)
        return min(result, 100000)  # Cap at 100k for performance
