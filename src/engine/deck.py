import random
from .card import Card


class Deck:
    """Standard 52-card deck with shuffle and deal operations."""

    def __init__(self, seed: int = None):
        self.cards: list[Card] = [Card.from_int(i) for i in range(52)]
        self.dealt: set[Card] = set()
        self._rng = random.Random(seed)

    def shuffle(self):
        """Shuffle all 52 cards back into the deck."""
        self.cards = [Card.from_int(i) for i in range(52)]
        self._rng.shuffle(self.cards)
        self.dealt.clear()

    def deal(self, n: int = 1) -> list[Card]:
        """Deal n cards from the top of the deck."""
        if len(self.cards) < n:
            raise ValueError(f"Not enough cards in deck: {len(self.cards)} < {n}")
        dealt = [self.cards.pop() for _ in range(n)]
        self.dealt.update(dealt)
        return dealt

    def deal_specific(self, cards: list[str]) -> list[Card]:
        """Deal specific cards (for testing/training scenarios). Remove them from deck."""
        result = []
        for s in cards:
            card = Card.from_str(s)
            if card in self.dealt:
                raise ValueError(f"Card already dealt: {card}")
            self.cards = [c for c in self.cards if c != card]
            self.dealt.add(card)
            result.append(card)
        return result

    def remaining(self) -> int:
        return len(self.cards)

    def remove_cards(self, cards: list[Card]):
        """Remove specific cards from deck (e.g., known dead cards)."""
        for card in cards:
            if card in self.cards:
                self.cards.remove(card)
                self.dealt.add(card)
