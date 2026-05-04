from dataclasses import dataclass, field
from .player import Player, PlayerStatus


@dataclass
class SidePot:
    amount: int
    eligible_players: list[int]  # player indices


@dataclass
class PotManager:
    """Manages the main pot and side pots."""

    main_pot: int = 0
    side_pots: list[SidePot] = field(default_factory=list)

    def calculate(self, players: list[Player]):
        """Calculate main pot and side pots based on player bets.

        Players with smaller stacks who are all-in create side pots.
        Only players who contributed to each pot and haven't folded are eligible.
        """
        self.main_pot = 0
        self.side_pots.clear()

        active_players = [p for p in players if p.current_bet > 0]
        if not active_players:
            return

        # Get unique all-in amounts (sorted)
        bets = sorted(set(
            p.current_bet for p in active_players
            if p.status in (PlayerStatus.ALL_IN, PlayerStatus.ACTIVE, PlayerStatus.WAITING)
        ))

        if not bets:
            bets = [max(p.current_bet for p in active_players)]

        prev_level = 0
        for level in bets:
            pot_chunk = 0
            eligible = []
            for i, p in enumerate(players):
                contrib = min(p.current_bet, level) - min(p.current_bet, prev_level)
                if contrib > 0:
                    pot_chunk += contrib
                if p.current_bet >= level and p.status != PlayerStatus.FOLDED:
                    eligible.append(i)

            if pot_chunk > 0:
                if prev_level == 0:
                    self.main_pot += pot_chunk
                else:
                    self.side_pots.append(SidePot(amount=pot_chunk, eligible_players=eligible))

            prev_level = level

        # If all chips ended up in main_pot (no all-ins), just sum everything
        if not self.side_pots:
            self.main_pot = sum(p.current_bet for p in players)

    def total(self) -> int:
        return self.main_pot + sum(sp.amount for sp in self.side_pots)

    def distribute(self, players: list[Player], winner_indices: list[int]):
        """Distribute the pot to winner(s). Handles splits for ties."""
        winners = set(winner_indices)

        # Distribute main pot
        eligible = [i for i in winners
                    if players[i].status != PlayerStatus.FOLDED]
        if eligible:
            share = self.main_pot // len(eligible)
            remainder = self.main_pot % len(eligible)
            for i in eligible:
                players[i].stack += share
            if remainder > 0:
                players[eligible[0]].stack += remainder

        # Distribute side pots
        for sp in self.side_pots:
            sp_winners = [i for i in winners if i in sp.eligible_players]
            if sp_winners:
                share = sp.amount // len(sp_winners)
                remainder = sp.amount % len(sp_winners)
                for i in sp_winners:
                    players[i].stack += share
                if remainder > 0:
                    players[sp_winners[0]].stack += remainder
            else:
                # No winner eligible — return to eligible non-folded players
                eligible = [i for i in sp.eligible_players
                           if players[i].status != PlayerStatus.FOLDED]
                if eligible:
                    share = sp.amount // len(eligible)
                    for i in eligible:
                        players[i].stack += share

        self.main_pot = 0
        self.side_pots.clear()
