from enum import IntEnum
from dataclasses import dataclass


class Suit(IntEnum):
    SPADE = 0    # ♠
    HEART = 1    # ♥
    DIAMOND = 2  # ♦
    CLUB = 3     # ♣

    def __str__(self):
        return ['♠', '♥', '♦', '♣'][self.value]

    def emoji(self):
        return ['♠️', '♥️', '♦️', '♣️'][self.value]

    @staticmethod
    def from_char(c: str):
        mapping = {'s': Suit.SPADE, 'h': Suit.HEART,
                   'd': Suit.DIAMOND, 'c': Suit.CLUB,
                   'S': Suit.SPADE, 'H': Suit.HEART,
                   'D': Suit.DIAMOND, 'C': Suit.CLUB}
        return mapping[c]


class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    def __str__(self):
        names = {2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7',
                 8: '8', 9: '9', 10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
        return names[self.value]

    @classmethod
    def from_char(cls, c: str):
        mapping = {'2': cls.TWO, '3': cls.THREE, '4': cls.FOUR, '5': cls.FIVE,
                   '6': cls.SIX, '7': cls.SEVEN, '8': cls.EIGHT, '9': cls.NINE,
                   'T': cls.TEN, 'J': cls.JACK, 'Q': cls.QUEEN, 'K': cls.KING, 'A': cls.ACE}
        return mapping[c.upper()]


@dataclass(frozen=True, slots=True)
class Card:
    rank: Rank
    suit: Suit

    def __str__(self):
        return f"{self.rank}{self.suit}"

    def __repr__(self):
        return self.__str__()

    @classmethod
    def from_str(cls, s: str):
        """Parse from string like 'As', 'Th', '2d', 'Kc'"""
        if len(s) != 2:
            raise ValueError(f"Invalid card string: {s}")
        return cls(Rank.from_char(s[0]), Suit.from_char(s[1]))

    @classmethod
    def from_int(cls, n: int):
        """Create card from 0-51 integer (for deck generation)"""
        return cls(Rank(n % 13 + 2), Suit(n // 13))


