from enum import IntEnum
from collections import Counter
from .card import Card, Rank


class HandRank(IntEnum):
    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10

    def name_cn(self):
        names = {
            1: '高牌', 2: '一对', 3: '两对', 4: '三条',
            5: '顺子', 6: '同花', 7: '葫芦', 8: '四条',
            9: '同花顺', 10: '皇家同花顺'
        }
        return names[self.value]


class HandResult:
    """Result of evaluating a poker hand."""
    __slots__ = ('rank', 'kickers', 'cards_used')

    def __init__(self, rank: HandRank, kickers: list[int], cards_used: list[Card]):
        self.rank = rank
        self.kickers = kickers  # sorted descending for comparison
        self.cards_used = cards_used

    def __lt__(self, other: 'HandResult') -> bool:
        if self.rank != other.rank:
            return self.rank < other.rank
        for a, b in zip(self.kickers, other.kickers):
            if a != b:
                return a < b
        return False

    def __eq__(self, other: 'HandResult') -> bool:
        if self.rank != other.rank:
            return False
        return self.kickers == other.kickers

    def __gt__(self, other: 'HandResult') -> bool:
        return other < self and not self == other

    def __le__(self, other: 'HandResult') -> bool:
        return self < other or self == other

    def __ge__(self, other: 'HandResult') -> bool:
        return self > other or self == other


class HandEvaluator:
    """Evaluate the best 5-card poker hand from 7 cards (2 hole + 5 community).

    Uses a deterministic algorithm: generate all C(7,5) combinations,
    evaluate each, and return the best.
    """

    @staticmethod
    def evaluate(hole_cards: list[Card], community_cards: list[Card]) -> HandResult:
        """Find the best 5-card hand from hole + community cards."""
        all_cards = hole_cards + community_cards
        n = len(all_cards)

        if n < 5:
            # Not enough cards for a full hand — use what we have
            ranks = sorted([c.rank.value for c in all_cards], reverse=True)
            return HandResult(HandRank.HIGH_CARD, ranks[:5] if ranks else [0], all_cards)

        best = None
        # Generate all C(n, n-2) combinations = C(n, 5)
        for i in range(n):
            for j in range(i + 1, n):
                cards_5 = [all_cards[k] for k in range(n) if k != i and k != j]
                result = HandEvaluator._eval_5(cards_5)
                if best is None or result > best:
                    best = result

        return best

    @staticmethod
    def evaluate_exact(cards: list[Card]) -> HandResult:
        """Evaluate exactly 5 cards."""
        if len(cards) != 5:
            raise ValueError("Must provide exactly 5 cards")
        return HandEvaluator._eval_5(cards)

    @staticmethod
    def _eval_5(cards: list[Card]) -> HandResult:
        """Evaluate exactly 5 cards and return HandResult."""
        ranks = [c.rank.value for c in cards]
        suits = [c.suit.value for c in cards]

        rank_counts = Counter(ranks)
        suit_counts = Counter(suits)

        is_flush = max(suit_counts.values()) >= 5
        is_straight, straight_high = HandEvaluator._check_straight(ranks)

        # Build kicker info
        sorted_ranks = sorted(ranks, reverse=True)

        if is_flush and is_straight:
            if straight_high == Rank.ACE.value:
                return HandResult(HandRank.ROYAL_FLUSH, [straight_high], cards)
            return HandResult(HandRank.STRAIGHT_FLUSH, [straight_high], cards)

        # Quads
        if 4 in rank_counts.values():
            quad_rank = max(r for r, c in rank_counts.items() if c == 4)
            kicker = max(r for r in ranks if r != quad_rank)
            return HandResult(HandRank.FOUR_OF_A_KIND, [quad_rank, kicker], cards)

        # Full house or trips
        if 3 in rank_counts.values():
            trip_rank = max(r for r, c in rank_counts.items() if c == 3)
            if 2 in rank_counts.values():
                pair_rank = max(r for r, c in rank_counts.items() if c >= 2 and r != trip_rank)
                return HandResult(HandRank.FULL_HOUSE, [trip_rank, pair_rank], cards)
            kickers = sorted([r for r in ranks if r != trip_rank], reverse=True)[:2]
            return HandResult(HandRank.THREE_OF_A_KIND, [trip_rank] + kickers, cards)

        # Flush
        if is_flush:
            flush_suit = max(suit_counts, key=suit_counts.get)
            flush_ranks = sorted([c.rank.value for c in cards if c.suit.value == flush_suit],
                                 reverse=True)[:5]
            return HandResult(HandRank.FLUSH, flush_ranks, cards)

        # Straight
        if is_straight:
            return HandResult(HandRank.STRAIGHT, [straight_high], cards)

        # Count pairs
        pair_ranks = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)

        if len(pair_ranks) >= 2:
            # Two pair
            kicker = max(r for r in ranks if r not in pair_ranks[:2])
            return HandResult(HandRank.TWO_PAIR, pair_ranks[:2] + [kicker], cards)

        if len(pair_ranks) == 1:
            kickers = sorted([r for r in ranks if r != pair_ranks[0]], reverse=True)[:3]
            return HandResult(HandRank.ONE_PAIR, [pair_ranks[0]] + kickers, cards)

        # High card
        return HandResult(HandRank.HIGH_CARD, sorted_ranks[:5], cards)

    @staticmethod
    def _check_straight(ranks: list[int]) -> tuple[bool, int | None]:
        """Check if ranks contain a straight. Returns (is_straight, high_card)."""
        unique = sorted(set(ranks))
        if len(unique) < 5:
            return False, None

        # Normal straight check
        for i in range(len(unique) - 4):
            if unique[i + 4] - unique[i] == 4:
                return True, unique[i + 4]

        # Wheel: A-2-3-4-5
        if set([14, 2, 3, 4, 5]).issubset(set(unique)):
            return True, 5  # 5-high straight

        return False, None

    @staticmethod
    def compare_hands(results: list[HandResult]) -> list[int]:
        """Compare multiple hands, return indices of winners (handles ties)."""
        best = max(results)
        return [i for i, r in enumerate(results) if r == best]
