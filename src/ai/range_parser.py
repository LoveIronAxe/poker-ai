"""Hand range parsing and evaluation.

Ranges are specified as strings like:
  "AKs, TT+, AQo+, 98s"
  "22-88"  (pairs 22 through 88)
  "ATs-AKs" (suited aces T through K)
  "KQo+" (KQo and better offsuit broadways)
"""

from ..engine.card import Card, Rank, Suit


class HandRange:
    """Represents a set of starting hands."""

    def __init__(self):
        self.hands: set[tuple] = set()  # set of (rank1, rank2, suited_bool)

    @classmethod
    def from_string(cls, range_str: str) -> 'HandRange':
        """Parse a range string into a HandRange."""
        hr = cls()
        parts = [p.strip() for p in range_str.split(',') if p.strip()]
        for part in parts:
            hr._parse_part(part)
        return hr

    @classmethod
    def all_hands(cls) -> 'HandRange':
        """Return range containing all 169 starting hands."""
        hr = cls()
        for r1 in range(2, 15):
            for r2 in range(2, r1 + 1):
                if r1 == r2:
                    hr.hands.add((r1, r2, None))  # pocket pair
                else:
                    hr.hands.add((r1, r2, True))   # suited
                    hr.hands.add((r1, r2, False))  # offsuit
        return hr

    @classmethod
    def tight_range(cls) -> 'HandRange':
        """UTG opening range (~12%)."""
        return cls.from_string("77+, ATs+, KJs+, QJs, JTs, T9s, 98s, AQo+")

    @classmethod
    def medium_range(cls) -> 'HandRange':
        """MP opening range (~18%)."""
        return cls.from_string("55+, A8s+, KTs+, QTs+, J9s+, T8s+, 97s+, 87s, AJo+, KQo")

    @classmethod
    def loose_range(cls) -> 'HandRange':
        """BTN opening range (~40%)."""
        return cls.from_string("22+, A2s+, K5s+, Q8s+, J8s+, T7s+, 97s+, 86s+, 76s, 65s, 54s, A2o+, K9o+, Q9o+, J9o+, T9o")

    def _parse_part(self, part: str):
        """Parse a single range component like 'AKs', 'TT+', 'AQo+', '98s'."""
        part = part.strip()

        # Handle '+' suffix (e.g., TT+, ATs+, KQo+)
        plus = part.endswith('+')
        if plus:
            part = part[:-1]

        suited = None
        if len(part) >= 3 and part[-1] in ('s', 'o'):
            suited = part[-1] == 's'
            part = part[:-1]
        elif len(part) == 2:
            if part[0] == part[1]:
                suited = None  # pocket pair
            else:
                # Bare like 'AK' means both suited and offsuit
                suited = None

        if len(part) != 2:
            return

        r1 = Rank.from_char(part[0]).value
        r2 = Rank.from_char(part[1]).value

        if r1 < r2:
            r1, r2 = r2, r1  # ensure r1 >= r2

        if plus:
            if r1 == r2:
                # TT+ means TT, JJ, QQ, KK, AA
                for r in range(r1, 15):
                    self.hands.add((r, r, None))
            else:
                # ATs+ means ATs, AJs, AQs, AKs
                for r in range(r2 + 1, r1 + 1):
                    if r > r1:
                        break
                    # Plus on suited: ATs+ = ATs, AJs, AQs, AKs
                    pass
                # Actually ATs+ means all suited aces with kicker >= T
                if r1 >= Rank.ACE.value - 1 and suited is True:
                    for kicker in range(r2, r1 + 1):
                        self.hands.add((r1, kicker, True))
                elif r1 >= Rank.ACE.value - 1 and suited is False:
                    for kicker in range(r2, r1 + 1):
                        self.hands.add((r1, kicker, False))
                elif r1 >= Rank.ACE.value - 1 and suited is None:
                    for kicker in range(r2, r1 + 1):
                        self.hands.add((r1, kicker, True))
                        self.hands.add((r1, kicker, False))
        else:
            if suited is None and r1 != r2:
                # Add both suited and offsuit
                self.hands.add((r1, r2, True))
                self.hands.add((r1, r2, False))
            else:
                self.hands.add((r1, r2, suited))

    def contains(self, hole_cards: list[Card]) -> bool:
        """Check if hole cards are in the range."""
        if len(hole_cards) != 2:
            return False
        r1 = hole_cards[0].rank.value
        r2 = hole_cards[1].rank.value
        if r1 < r2:
            r1, r2 = r2, r1

        is_suited = hole_cards[0].suit == hole_cards[1].suit

        if r1 == r2:
            return (r1, r2, None) in self.hands

        return ((r1, r2, is_suited) in self.hands or
                (r1, r2, None) in self.hands)  # None means both

    def size(self) -> int:
        return len(self.hands)

    def intersection(self, other: 'HandRange') -> 'HandRange':
        result = HandRange()
        result.hands = self.hands & other.hands
        return result

    def __contains__(self, item) -> bool:
        if isinstance(item, list):
            return self.contains(item)
        return item in self.hands

    def __repr__(self):
        return f"HandRange({len(self.hands)} combos)"


def get_position_range(position_name: str, is_calling: bool = False) -> HandRange:
    """Get standard opening/calling range for a position.

    position_name: 'utg', 'mp', 'hj', 'co', 'btn', 'sb', 'bb'
    """
    ranges = {
        'utg': "77+, ATs+, KJs+, QJs, JTs, T9s, 98s, AQo+",
        'mp': "55+, A8s+, KTs+, QTs+, J9s+, T8s+, 97s+, 87s, 76s, AJo+, KQo",
        'hj': "44+, A5s+, K9s+, Q9s+, J9s+, T8s+, 97s+, 86s+, 76s, 65s, ATo+, KJo+, QJo",
        'co': "33+, A2s+, K7s+, Q8s+, J8s+, T7s+, 97s+, 86s+, 75s+, 65s, 54s, A8o+, KTo+, QTo+, JTo",
        'btn': "22+, A2s+, K5s+, Q8s+, J8s+, T7s+, 97s+, 86s+, 75s+, 65s, 54s, A2o+, K9o+, Q9o+, J9o+, T9o",
        'sb': "22+, A2s+, K8s+, Q8s+, J8s+, T7s+, 97s+, 87s, A2o+, KTo+, QTo+, JTo",
        'bb': "22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 96s+, 86s+, 75s+, 65s, A2o+, K5o+, Q8o+, J8o+, T8o+",
    }
    return HandRange.from_string(ranges.get(position_name, ranges['utg']))


def get_3bet_range(position_name: str) -> HandRange:
    """Standard 3-bet ranges by position."""
    three_bet_ranges = {
        'utg': "QQ+, AKs, AKo",
        'mp': "JJ+, AKs, AKo, AQs",
        'hj': "TT+, AKs, AKo, AQs, KQs",
        'co': "99+, ATs+, AJo+, KQs, QJs",
        'btn': "88+, A8s+, AJo+, KTs+, QTs+, JTs",
        'sb': "77+, A5s+, ATo+, KJs+, QJs, JTs, T9s",
        'bb': "66+, A2s+, ATo+, KTs+, QTs+, JTs, T9s, 98s",
    }
    return HandRange.from_string(three_bet_ranges.get(position_name, three_bet_ranges['mp']))


def get_position_name(relative_pos: int) -> str:
    """Convert relative position from BTN to position name.
    BTN=0, SB=1, BB=2, UTG=3, UTG+1=4, MP=5, HJ=6, CO=7
    """
    names = {0: 'btn', 1: 'sb', 2: 'bb', 3: 'utg', 4: 'mp', 5: 'mp', 6: 'hj', 7: 'co'}
    return names.get(relative_pos, 'utg')
