from enum import IntEnum
from dataclasses import dataclass, field
from .card import Card


class PlayerStatus(IntEnum):
    ACTIVE = 0       # still in hand, not yet acted this round
    WAITING = 1      # has acted this round, waiting for others
    FOLDED = 2       # folded
    ALL_IN = 3       # all-in, cannot act further
    OUT = 4          # busted, no chips


@dataclass
class Player:
    """Represents a player at the table."""
    name: str
    stack: int  # total chips
    seat_idx: int  # physical seat at table (0-8)
    is_human: bool = False

    # Per-hand state
    hole_cards: list[Card] = field(default_factory=list)
    current_bet: int = 0  # total chips bet in current hand
    round_bet: int = 0    # chips bet in current betting round
    status: PlayerStatus = PlayerStatus.OUT
    last_action: str = ""

    def reset_for_hand(self):
        """Reset player state for a new hand."""
        self.hole_cards.clear()
        self.current_bet = 0
        self.round_bet = 0
        self.last_action = ""
        if self.stack > 0:
            self.status = PlayerStatus.ACTIVE

    def reset_round_bet(self):
        """Reset round-specific bet tracking."""
        self.round_bet = 0

    def bet(self, amount: int):
        """Player puts chips into the pot."""
        actual = min(amount, self.stack)
        self.stack -= actual
        self.current_bet += actual
        self.round_bet += actual
        if self.stack == 0:
            self.status = PlayerStatus.ALL_IN
        return actual

    def post_blind(self, amount: int):
        """Post a blind (forced bet)."""
        return self.bet(amount)

    def can_act(self) -> bool:
        return self.status in (PlayerStatus.ACTIVE, PlayerStatus.WAITING)

    @property
    def is_active(self) -> bool:
        return self.status in (PlayerStatus.ACTIVE, PlayerStatus.WAITING)

    @property
    def chips_in_pot(self) -> int:
        return self.current_bet
