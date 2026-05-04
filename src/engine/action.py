from enum import IntEnum
from dataclasses import dataclass


class ActionType(IntEnum):
    FOLD = 0
    CHECK = 1
    CALL = 2
    BET = 3
    RAISE = 4
    ALL_IN = 5


@dataclass(frozen=True, slots=True)
class Action:
    """A single action taken by a player."""
    action_type: ActionType
    amount: int = 0  # total chips put in (not added on top)
    player_idx: int = -1  # filled in by engine

    def __str__(self):
        names = {0: 'Fold', 1: 'Check', 2: 'Call', 3: 'Bet', 4: 'Raise', 5: 'All-in'}
        if self.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN, ActionType.CALL):
            return f"{names[self.action_type.value]} {self.amount}"
        return names[self.action_type.value]

    @classmethod
    def fold(cls):
        return cls(ActionType.FOLD, 0)

    @classmethod
    def check(cls):
        return cls(ActionType.CHECK, 0)

    @classmethod
    def call(cls, amount: int):
        return cls(ActionType.CALL, amount)

    @classmethod
    def bet(cls, amount: int):
        return cls(ActionType.BET, amount)

    @classmethod
    def raise_(cls, amount: int):
        return cls(ActionType.RAISE, amount)

    @classmethod
    def all_in(cls, amount: int):
        return cls(ActionType.ALL_IN, amount)

    @property
    def is_aggressive(self) -> bool:
        return self.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)

    @property
    def is_passive(self) -> bool:
        return self.action_type in (ActionType.CHECK, ActionType.CALL)

    @property
    def ends_hand(self) -> bool:
        return self.action_type == ActionType.FOLD
