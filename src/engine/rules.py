from .action import Action, ActionType
from .player import Player, PlayerStatus


class Rules:
    """Validates poker rules and constraints."""

    @staticmethod
    def validate_action(action: Action, player: Player,
                        current_bet: int, min_raise: int) -> tuple[bool, str]:
        """Check if an action is legal. Returns (is_valid, error_message)."""
        if not player.can_act():
            return False, "Player cannot act"

        to_call = current_bet - player.round_bet

        if action.action_type == ActionType.FOLD:
            if to_call == 0:
                return False, "Cannot fold when no bet to call (check instead)"
            return True, ""

        elif action.action_type == ActionType.CHECK:
            if to_call > 0:
                return False, f"Cannot check — must call {to_call}, raise, or fold"
            return True, ""

        elif action.action_type == ActionType.CALL:
            if to_call == 0:
                return False, "Nothing to call (check instead)"
            if action.amount != to_call and action.amount != player.stack:
                return False, f"Call amount must be {to_call} or all-in"
            return True, ""

        elif action.action_type == ActionType.BET:
            if to_call > 0:
                return False, "Cannot bet when there's action — use raise"
            if action.amount < min_raise and action.amount < player.stack:
                return False, f"Minimum bet is {min_raise}"
            if action.amount > player.stack:
                return False, "Bet exceeds stack"
            return True, ""

        elif action.action_type == ActionType.RAISE:
            if to_call == 0:
                return False, "Cannot raise with no bet to raise (use bet)"
            min_total = current_bet + min_raise
            if action.amount + player.round_bet < min_total and action.amount < player.stack:
                return False, f"Minimum raise is to {min_total} total"
            if action.amount > player.stack:
                return False, "Raise exceeds stack"
            return True, ""

        elif action.action_type == ActionType.ALL_IN:
            if player.stack == 0:
                return False, "No chips to go all-in with"
            return True, ""

        return False, f"Unknown action type: {action.action_type}"

    @staticmethod
    def get_min_raise(current_bet: int, last_raise: int, big_blind: int) -> int:
        """Get the minimum raise size."""
        if current_bet == 0:
            return big_blind
        return max(last_raise, big_blind)

    @staticmethod
    def is_valid_bet_size(amount: int, pot: int, is_no_limit: bool = True) -> bool:
        """Check if a bet size is valid."""
        if amount <= 0:
            return False
        if is_no_limit:
            return True  # Any positive amount is valid in NLHE
        # For limit games, would check fixed amounts
        return True

    @staticmethod
    def need_to_showdown(players: list[Player]) -> bool:
        """Determine if we need a showdown (more than 1 active/all-in player)."""
        alive = [p for p in players if p.status != PlayerStatus.FOLDED]
        return len(alive) > 1

    @staticmethod
    def get_next_to_act(players: list[Player], start_idx: int) -> int | None:
        """Find the next player who needs to act. Returns None if none found."""
        n = len(players)
        for offset in range(n):
            idx = (start_idx + offset) % n
            p = players[idx]
            if p.status == PlayerStatus.ACTIVE:
                return idx
        return None
