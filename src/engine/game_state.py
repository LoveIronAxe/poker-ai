from enum import IntEnum
from dataclasses import dataclass, field
import uuid

from .card import Card
from .deck import Deck
from .hand import HandEvaluator, HandResult
from .player import Player, PlayerStatus
from .action import Action, ActionType
from .pot import PotManager
from .betting import BettingRound
from .rules import Rules


class GamePhase(IntEnum):
    IDLE = 0
    PREFLOP = 1
    FLOP = 2
    TURN = 3
    RIVER = 4
    SHOWDOWN = 5

    def name_cn(self):
        return {0: '等待', 1: '翻牌前', 2: '翻牌', 3: '转牌', 4: '河牌', 5: '摊牌'}[self.value]


@dataclass
class GameConfig:
    """Configuration for a poker game."""
    num_players: int = 9
    small_blind: int = 1
    big_blind: int = 2
    starting_stack: int = 1000
    ante: int = 0


@dataclass
class GameEvent:
    """Record of an event in the game for replay/review."""
    type: str  # 'deal', 'action', 'phase_change', 'showdown', 'pot_awarded'
    phase: GamePhase
    player_idx: int | None
    data: dict
    timestamp: int  # sequence number


@dataclass
class GameState:
    """Complete state of a Texas Hold'em game."""

    config: GameConfig
    hand_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    players: list[Player] = field(default_factory=list)
    community_cards: list[Card] = field(default_factory=list)
    deck: Deck = field(default_factory=Deck)
    pot_manager: PotManager = field(default_factory=PotManager)
    betting_round: BettingRound = field(default_factory=BettingRound)
    phase: GamePhase = GamePhase.IDLE
    dealer_idx: int = 0
    current_player_idx: int = 0
    hand_number: int = 0
    events: list[GameEvent] = field(default_factory=list)
    _event_seq: int = 0

    def init_game(self):
        """Initialize players and start the first hand."""
        self.players = [
            Player(name=f"Player {i+1}", stack=self.config.starting_stack, seat_idx=i)
            for i in range(self.config.num_players)
        ]
        self.dealer_idx = 0
        self.hand_number = 0

    def start_new_hand(self):
        """Deal a new hand."""
        self.hand_id = str(uuid.uuid4())[:8]
        self.hand_number += 1
        self.community_cards.clear()
        self.pot_manager = PotManager()
        self.phase = GamePhase.PREFLOP
        self._event_seq = 0
        self.events.clear()

        # Remove busted players and reset active ones
        for p in self.players:
            if p.stack <= 0:
                p.status = PlayerStatus.OUT
            else:
                p.reset_for_hand()

        # Move dealer button
        active_seats = [i for i, p in enumerate(self.players) if p.stack > 0]
        if len(active_seats) < 2:
            return False  # Game over

        self.dealer_idx = self._next_active_player(self.dealer_idx)

        # Shuffle and deal
        self.deck.shuffle()

        # Post blinds
        sb_idx = self._next_active_player(self.dealer_idx)
        bb_idx = self._next_active_player(sb_idx)

        self.players[sb_idx].bet(min(self.config.small_blind, self.players[sb_idx].stack))
        self.players[sb_idx].last_action = f"post SB {self.players[sb_idx].current_bet}"

        self.players[bb_idx].bet(min(self.config.big_blind, self.players[bb_idx].stack))
        self.players[bb_idx].last_action = f"post BB {self.players[bb_idx].current_bet}"

        # Post antes if any
        if self.config.ante > 0:
            for p in self.players:
                if p.stack > 0:
                    p.bet(min(self.config.ante, p.stack))

        # Deal 2 hole cards to each active player
        for p in self.players:
            if p.status != PlayerStatus.OUT:
                p.hole_cards = self.deck.deal(2)

        self._add_event('deal', None, {'type': 'hole_cards'})

        # Set up first betting round - UTG acts first in preflop
        # UTG is 2 seats after BB in 9-max (BB+1)
        utg_idx = self._next_active_player(bb_idx)
        for p in self.players:
            if p.status != PlayerStatus.OUT:
                p.status = PlayerStatus.ACTIVE

        self.betting_round.start(self.config.big_blind, utg_idx, self.players, is_preflop=True)
        self.current_player_idx = utg_idx
        self.phase = GamePhase.PREFLOP

        self._add_event('phase_change', None, {'phase': 'preflop'})
        return True

    def apply_action(self, action: Action) -> tuple[bool, str]:
        """Apply a player action and advance the game state.

        Returns (success, error_message).
        """
        player = self.players[self.current_player_idx]

        # Validate
        is_valid, error = Rules.validate_action(
            action, player,
            self.betting_round.current_bet,
            self.betting_round.min_raise
        )
        if not is_valid:
            return False, error

        # Apply to betting round
        action = Action(action.action_type, action.amount, self.current_player_idx)
        self.betting_round.apply_action(action, player, self.current_player_idx)
        self._add_event('action', self.current_player_idx, {
            'action': str(action),
            'round': self.phase.name_cn()
        })

        # Check for hand ending conditions
        active_count = self.betting_round.count_active(self.players)
        if active_count <= 1:
            self._handle_hand_end()
            return True, ""

        # Check if round is complete
        if self.betting_round.is_round_complete(self.players):
            self._advance_phase()
            return True, ""

        # Move to next player
        self._next_player()
        return True, ""

    def get_game_view(self, player_idx: int = -1) -> dict:
        """Get a view of the game state (for API/frontend).

        If player_idx is provided, their hole cards are included.
        """
        view = {
            'hand_id': self.hand_id,
            'hand_number': self.hand_number,
            'phase': self.phase.value,
            'phase_name': self.phase.name_cn(),
            'community_cards': [str(c) for c in self.community_cards],
            'pot': {
                'main': self.pot_manager.main_pot,
                'side': [{'amount': sp.amount, 'eligible': sp.eligible_players}
                         for sp in self.pot_manager.side_pots]
            },
            'total_pot': self.pot_manager.total(),
            'dealer_idx': self.dealer_idx,
            'current_player_idx': self.current_player_idx,
            'current_bet': self.betting_round.current_bet,
            'min_raise': self.betting_round.min_raise,
            'players': []
        }

        for i, p in enumerate(self.players):
            pv = {
                'name': p.name,
                'stack': p.stack,
                'current_bet': p.current_bet,
                'status': p.status.name,
                'last_action': p.last_action,
                'is_active': p.status == PlayerStatus.ACTIVE,
                'seat_idx': p.seat_idx,
            }
            if i == player_idx:
                pv['hole_cards'] = [str(c) for c in p.hole_cards]
            view['players'].append(pv)

        if player_idx >= 0:
            player = self.players[player_idx]
            view['my_legal_actions'] = [
                {'type': a.action_type.name.lower(), 'amount': a.amount}
                for a in self.betting_round.get_legal_actions(player, self.players)
            ]

        return view

    def _advance_phase(self):
        """Move to the next phase of the game."""
        if self.phase == GamePhase.PREFLOP:
            self._deal_flop()
        elif self.phase == GamePhase.FLOP:
            self._deal_turn()
        elif self.phase == GamePhase.TURN:
            self._deal_river()
        elif self.phase == GamePhase.RIVER:
            self._handle_showdown()
            return

        # Reset for new betting round
        self._start_new_betting_round()

    def _deal_flop(self):
        self.deck.deal(1)  # burn
        self.community_cards.extend(self.deck.deal(3))
        self.phase = GamePhase.FLOP
        self._add_event('deal', None, {'type': 'flop', 'cards': [str(c) for c in self.community_cards[-3:]]})

    def _deal_turn(self):
        self.deck.deal(1)  # burn
        self.community_cards.extend(self.deck.deal(1))
        self.phase = GamePhase.TURN
        self._add_event('deal', None, {'type': 'turn', 'card': str(self.community_cards[-1])})

    def _deal_river(self):
        self.deck.deal(1)  # burn
        self.community_cards.extend(self.deck.deal(1))
        self.phase = GamePhase.RIVER
        self._add_event('deal', None, {'type': 'river', 'card': str(self.community_cards[-1])})

    def _start_new_betting_round(self):
        """Start betting for a new street. First active player after dealer acts first."""
        # Find first active player after dealer (postflop)
        first = self._next_active_player(self.dealer_idx)
        for p in self.players:
            if p.status == PlayerStatus.WAITING:
                p.status = PlayerStatus.ACTIVE

        self.betting_round.start(self.config.big_blind, first, self.players)
        self.current_player_idx = first

        # If only one player can act, skip
        active = [i for i, p in enumerate(self.players) if p.status == PlayerStatus.ACTIVE]
        if len(active) <= 1:
            # Advance through remaining phases
            while self.phase < GamePhase.RIVER:
                if self.phase == GamePhase.PREFLOP:
                    self._deal_flop()
                elif self.phase == GamePhase.FLOP:
                    self._deal_turn()
                elif self.phase == GamePhase.TURN:
                    self._deal_river()
            self._handle_showdown()

    def _handle_hand_end(self):
        """Handle end of hand (all but one folded)."""
        active = [p for p in self.players if p.status != PlayerStatus.FOLDED]
        self.pot_manager.calculate(self.players)

        winner_idx = self.players.index(active[0])
        self.pot_manager.distribute(self.players, [winner_idx])
        self._add_event('pot_awarded', winner_idx, {
            'amount': self.pot_manager.total(),
            'reason': 'all_folded'
        })
        self.phase = GamePhase.IDLE

    def _handle_showdown(self):
        """Handle showdown — compare hands and award pot."""
        self.phase = GamePhase.SHOWDOWN
        self._add_event('phase_change', None, {'phase': 'showdown'})

        # Evaluate all non-folded players
        active_players = [(i, p) for i, p in enumerate(self.players)
                         if p.status != PlayerStatus.FOLDED]

        results = []
        for i, p in active_players:
            result = HandEvaluator.evaluate(p.hole_cards, self.community_cards)
            results.append((i, result))

        # Find winner(s)
        hand_results = [r for _, r in results]
        winner_indices_in_active = HandEvaluator.compare_hands(hand_results)
        winner_indices = [results[wi][0] for wi in winner_indices_in_active]

        # Calculate and distribute pot
        self.pot_manager.calculate(self.players)
        for i, result in results:
            self._add_event('showdown', i, {
                'hand_rank': result.rank.name_cn(),
                'hand_value': str(result.rank.value),
                'kickers': result.kickers
            })

        self.pot_manager.distribute(self.players, winner_indices)

        total_won = self.pot_manager.total()
        self._add_event('pot_awarded', winner_indices[0] if len(winner_indices) == 1 else None, {
            'amount': total_won,
            'winners': winner_indices,
            'reason': 'showdown'
        })

        self.phase = GamePhase.IDLE

    def _next_player(self):
        """Advance to the next player who can act."""
        n = len(self.players)
        for offset in range(1, n + 1):
            idx = (self.current_player_idx + offset) % n
            if self.players[idx].status == PlayerStatus.ACTIVE:
                self.current_player_idx = idx
                return
        # No active players found — advance phase
        self._advance_phase()

    def _next_active_player(self, from_idx: int) -> int:
        """Find next non-OUT player after from_idx (clockwise)."""
        n = len(self.players)
        for offset in range(1, n + 1):
            idx = (from_idx + offset) % n
            if self.players[idx].status != PlayerStatus.OUT:
                return idx
        return from_idx  # Should not happen if at least 2 players

    def _add_event(self, event_type: str, player_idx: int | None, data: dict):
        self.events.append(GameEvent(
            type=event_type,
            phase=self.phase,
            player_idx=player_idx,
            data=data,
            timestamp=self._event_seq
        ))
        self._event_seq += 1

    def is_hand_over(self) -> bool:
        return self.phase == GamePhase.IDLE

    def live_pot(self) -> int:
        """Total chips committed to the pot (live, not just at showdown)."""
        return sum(p.current_bet for p in self.players)

    def get_active_player_count(self) -> int:
        return sum(1 for p in self.players if p.stack > 0)
