from dataclasses import dataclass, field
from .action import Action, ActionType
from .player import Player, PlayerStatus


@dataclass
class BettingRound:
    """Manages a single betting round (preflop/flop/turn/river)."""

    current_bet: int = 0      # the current highest bet amount
    last_raise: int = 0       # the size of the last raise
    min_raise: int = 0        # minimum raise size
    actions: list[Action] = field(default_factory=list)
    players_acted: set[int] = field(default_factory=set)
    round_complete: bool = False

    def start(self, big_blind: int, first_to_act: int, players: list[Player],
              is_preflop: bool = False):
        """Initialize the betting round."""
        self.last_raise = big_blind
        self.min_raise = big_blind
        self.actions.clear()
        self.players_acted.clear()
        self.round_complete = False

        if not is_preflop:
            for p in players:
                p.reset_round_bet()

        # Current bet tracks the highest round bet (blinds preflop, 0 postflop)
        self.current_bet = max((p.round_bet for p in players), default=0)
        if self.current_bet == 0 and is_preflop:
            self.current_bet = big_blind

    def get_legal_actions(self, player: Player, players: list[Player]) -> list[Action]:
        """Get all legal actions for a player."""
        if not player.can_act():
            return []

        actions = []
        to_call = self.current_bet - player.round_bet
        max_bet = player.stack

        if to_call == 0:
            actions.append(Action.check())
        else:
            actions.append(Action.fold())
            if to_call >= player.stack:
                actions.append(Action.all_in(player.stack + player.round_bet))
            else:
                actions.append(Action.call(to_call))

        # Betting/raising options
        if to_call == 0:
            # Can bet
            min_bet = max(self.min_raise, player.stack) if player.stack <= self.min_raise else self.min_raise
            if player.stack > min_bet:
                actions.append(Action.bet(min_bet))
            if player.stack > 0:
                actions.append(Action.all_in(player.stack))
        else:
            # Can raise
            min_raise_to = self.current_bet + self.last_raise
            if player.stack + player.round_bet > min_raise_to:
                actions.append(Action.raise_(min_raise_to - player.round_bet))
            if player.stack + player.round_bet > self.current_bet:
                actions.append(Action.all_in(player.stack + player.round_bet))

        return actions

    def apply_action(self, action: Action, player: Player, player_idx: int):
        """Apply an action and update round state."""
        action = Action(action.action_type, action.amount, player_idx)
        self.actions.append(action)
        self.players_acted.add(player_idx)

        if action.action_type == ActionType.FOLD:
            player.status = PlayerStatus.FOLDED
            player.last_action = "fold"

        elif action.action_type == ActionType.CHECK:
            player.last_action = "check"

        elif action.action_type == ActionType.CALL:
            actual = player.bet(action.amount)
            player.last_action = "call"

        elif action.action_type == ActionType.BET:
            actual = player.bet(action.amount)
            self.current_bet = player.round_bet
            self.last_raise = action.amount
            self.min_raise = action.amount
            player.last_action = f"bet {actual}"

        elif action.action_type == ActionType.RAISE:
            added = player.round_bet + action.amount - self.current_bet
            actual = player.bet(action.amount)
            self.last_raise = player.round_bet - self.current_bet
            self.current_bet = player.round_bet
            self.min_raise = self.last_raise
            player.last_action = f"raise to {player.round_bet}"

            # Reset players who need to act again after a raise
            self.players_acted = {player_idx}

        elif action.action_type == ActionType.ALL_IN:
            total = player.stack + player.round_bet
            actual = player.bet(player.stack)
            new_bet = player.round_bet

            if new_bet > self.current_bet:
                if self.current_bet == 0:
                    player.last_action = f"all-in bet {new_bet}"
                else:
                    raise_amount = new_bet - self.current_bet
                    if raise_amount >= self.last_raise:
                        self.last_raise = raise_amount
                        self.players_acted = {player_idx}
                    player.last_action = f"all-in raise to {new_bet}"
                self.current_bet = max(self.current_bet, new_bet)
                self.min_raise = max(self.min_raise, self.last_raise)
            else:
                # All-in for less — just a call
                player.last_action = "all-in call"
                player.status = PlayerStatus.ALL_IN

    def is_round_complete(self, players: list[Player]) -> bool:
        """Check if the betting round is over."""
        active_players = [i for i, p in enumerate(players) if p.status == PlayerStatus.ACTIVE]

        # No active players left
        if not active_players:
            # Players who are WAITING or ALL_IN survive
            survivors = [i for i, p in enumerate(players) if p.is_active or p.status == PlayerStatus.ALL_IN]
            self.round_complete = True
            return True

        # All active players have acted and bets are matched
        all_bets_equal = all(
            players[i].round_bet == self.current_bet
            for i in active_players
        )
        all_have_acted = all(i in self.players_acted for i in active_players)

        if all_bets_equal and all_have_acted:
            self.round_complete = True
            # Transition ACTIVE → WAITING for next round
            for i in active_players:
                players[i].status = PlayerStatus.WAITING
            return True

        return False

    def count_active(self, players: list[Player]) -> int:
        """Count players who can still act (not folded)."""
        return sum(1 for p in players if p.status != PlayerStatus.FOLDED)

    def get_last_aggressor(self) -> int | None:
        """Get the index of the last player who bet or raised."""
        for action in reversed(self.actions):
            if action.is_aggressive:
                return action.player_idx
        return None
