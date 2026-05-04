"""Strategy engine that combines range, equity, position, and game state
to make poker decisions at different difficulty levels."""

from enum import IntEnum
from dataclasses import dataclass
import random

from ..engine.card import Card
from ..engine.action import Action, ActionType
from ..engine.hand import HandEvaluator
from ..engine.game_state import GameState, GamePhase
from ..engine.player import Player, PlayerStatus
from .range_parser import HandRange, get_position_range, get_3bet_range, get_position_name
from .equity import EquityCalculator


class Difficulty(IntEnum):
    BEGINNER = 1    # Plays face-up hand value only
    EASY = 2        # Basic position awareness
    MEDIUM = 3      # Range-based decisions, pot odds
    HARD = 4        # GTO approximation, mixed strategy
    EXPERT = 5      # Deep MCTS, opponent modeling


@dataclass
class StrategyConfig:
    difficulty: Difficulty = Difficulty.MEDIUM
    aggression: float = 0.5  # 0=passive, 1=aggressive
    bluff_frequency: float = 0.2
    position_adjustment: bool = True
    use_opponent_modeling: bool = False


class StrategyEngine:
    """Makes poker decisions based on game state and strategy configuration."""

    def __init__(self, config: StrategyConfig = None, seed: int = None):
        self.config = config or StrategyConfig()
        self.equity_calc = EquityCalculator(num_simulations=3000, seed=seed)
        self._rng = random.Random(seed)

    def decide(self, game: GameState, player_idx: int) -> Action:
        """Main decision function. Returns the action to take."""
        player = game.players[player_idx]
        legal_actions = game.betting_round.get_legal_actions(player, game.players)

        if not legal_actions:
            return Action.fold()

        # Get position info
        rel_pos = (player_idx - game.dealer_idx) % len(game.players)
        pos_name = get_position_name(rel_pos)

        # Hand strength assessment
        strength = self._assess_hand(player.hole_cards, game.community_cards,
                                     game.phase, pos_name)

        if self.config.difficulty <= Difficulty.EASY:
            return self._basic_decision(strength, legal_actions, game)
        elif self.config.difficulty <= Difficulty.MEDIUM:
            return self._medium_decision(strength, legal_actions, game, player, pos_name)
        elif self.config.difficulty <= Difficulty.HARD:
            return self._advanced_decision(strength, legal_actions, game, player, pos_name)
        else:
            return self._expert_decision(strength, legal_actions, game, player, pos_name)

    def _assess_hand(self, hole: list[Card], community: list[Card],
                     phase: GamePhase, position: str) -> dict:
        """Assess current hand strength."""
        if len(community) == 0:
            strength = EquityCalculator.quick_equity(hole)
        else:
            result = HandEvaluator.evaluate(hole, community)
            strength = {
                "hand_type": result.rank.name_cn(),
                "rank_value": result.rank.value,
                "kickers": result.kickers,
                "strength": min(95, result.rank.value * 10),
            }

            # Add draw detection
            strength["draws"] = self._detect_draws(hole, community)

        # Position multiplier
        pos_mult = {
            'btn': 1.3, 'co': 1.15, 'hj': 1.05, 'mp': 1.0,
            'utg': 0.9, 'sb': 0.85, 'bb': 0.95
        }
        strength["position_multiplier"] = pos_mult.get(position, 1.0)
        strength["adjusted_strength"] = strength.get("strength", 50) * pos_mult.get(position, 1.0)

        return strength

    def _basic_decision(self, strength: dict, legal_actions: list[Action],
                        game: GameState) -> Action:
        """Simple beginner-level decision making."""
        s = strength.get("strength", 50)

        can_check = any(a.action_type == ActionType.CHECK for a in legal_actions)
        can_call = any(a.action_type == ActionType.CALL for a in legal_actions)
        can_bet = any(a.action_type == ActionType.BET for a in legal_actions)
        can_raise = any(a.action_type == ActionType.RAISE for a in legal_actions)

        if s >= 80:
            if can_raise:
                return Action.raise_(self._valid_raise_amount(game, game.players[game.current_player_idx]))
            if can_bet:
                return Action.bet(self._valid_bet_amount(game, 0.75))
            return Action.check() if can_check else Action.fold()

        elif s >= 60:
            if can_bet:
                return Action.bet(self._valid_bet_amount(game, 0.5))
            if can_raise:
                to_call = game.betting_round.current_bet - game.players[game.current_player_idx].round_bet
                return Action.call(to_call)
            return Action.check() if can_check else Action.fold()

        elif s >= 40:
            if can_check:
                return Action.check()
            if can_call:
                to_call = game.betting_round.current_bet - game.players[game.current_player_idx].round_bet
                if to_call <= int(game.live_pot() * 0.3):
                    return Action.call(to_call)
            return Action.fold()

        else:
            if can_check:
                return Action.check()
            return Action.fold()

    def _min_bet(self, game: GameState) -> int:
        """Minimum bet amount (at least big blind or min_raise)."""
        return max(game.config.big_blind, game.betting_round.min_raise)

    def _valid_raise_amount(self, game: GameState, player: Player, multiplier: float = 2.5) -> int:
        """Compute a valid raise amount (total chips to add on top of current round bet)."""
        current = game.betting_round.current_bet
        min_raise = game.betting_round.min_raise
        # Desired raise-to amount
        if current == 0:
            desired = max(game.config.big_blind * 2, int(game.live_pot() * 0.66))
        else:
            desired = current + max(min_raise, int(game.live_pot() * 0.5))
        # Amount to add (on top of what's already in this round)
        return desired - player.round_bet

    def _valid_bet_amount(self, game: GameState, multiplier: float = 0.66) -> int:
        """Compute a valid bet amount (total chips to put in)."""
        min_bet = max(game.config.big_blind, game.betting_round.min_raise)
        pct_amount = int(game.live_pot() * multiplier / 100) * 100
        return max(min_bet, int(game.live_pot() * multiplier)) or min_bet

    def _medium_decision(self, strength: dict, legal_actions: list[Action],
                         game: GameState, player: Player, position: str) -> Action:
        """Medium-level decision with pot odds and position awareness."""
        s = strength.get("adjusted_strength", 50)
        draws = strength.get("draws", [])

        can_check = any(a.action_type == ActionType.CHECK for a in legal_actions)
        can_bet = any(a.action_type == ActionType.BET for a in legal_actions)
        can_call = any(a.action_type == ActionType.CALL for a in legal_actions)
        can_raise = any(a.action_type == ActionType.RAISE for a in legal_actions)

        # Pot odds calculation
        to_call = game.betting_round.current_bet - player.round_bet
        if to_call > 0:
            pot_odds = to_call / (game.live_pot() + to_call) * 100 if game.live_pot() > 0 else 50

            # Draw equity
            draw_equity = 0
            if draws:
                draw_equity = sum(d.get("outs", 0) for d in draws) * (
                    4 if game.phase == GamePhase.FLOP else 2
                )

            if s + draw_equity < pot_odds and can_check:
                if to_call > game.config.big_blind * 5 and s < 50:
                    return Action.fold()

        # Decision
        if s >= 75:
            # Limit re-raises to avoid infinite loop (cap at ~5 per round)
            raise_count = sum(1 for a in game.betting_round.actions if a.is_aggressive)
            if can_raise and raise_count < 5:
                return Action.raise_(self._valid_raise_amount(game, player))
            elif can_raise:
                return Action.call(to_call) if to_call > 0 else Action.check()
            if can_bet:
                return Action.bet(self._valid_bet_amount(game, 0.66))
            if can_check:
                if self._rng.random() < 0.15:
                    return Action.check()
                return Action.bet(self._valid_bet_amount(game, 0.5))
            return Action.call(min(to_call, player.stack))

        elif s >= 55:
            if can_bet:
                return Action.bet(self._valid_bet_amount(game, 0.5))
            if can_raise:
                if draws:
                    return Action.raise_(self._valid_raise_amount(game, player))
                return Action.call(to_call)
            if can_check:
                return Action.check()
            small_call = int(game.live_pot() * 0.25)
            return Action.call(min(to_call, player.stack)) if to_call < max(small_call, 1) else Action.fold()

        elif s >= 35:
            if can_bet and self._rng.random() < self.config.bluff_frequency and position in ('btn', 'co', 'hj'):
                return Action.bet(self._valid_bet_amount(game, 0.4))
            if can_check:
                return Action.check()
            if can_call and to_call <= int(game.live_pot() * 0.15):
                return Action.call(to_call)
            return Action.fold()

        else:
            if can_check:
                return Action.check()
            if to_call == 0:
                return Action.check()
            return Action.fold()

    def _advanced_decision(self, strength: dict, legal_actions: list[Action],
                           game: GameState, player: Player, position: str) -> Action:
        """Advanced decision with mixed strategy and range considerations."""
        # Uses medium as base with more sophisticated mixing
        s = strength.get("adjusted_strength", 50)
        draws = strength.get("draws", [])
        hand_type = strength.get("rank_value", 1)

        pot_pct = lambda pct: max(1, int(game.live_pot() * pct / 100))

        can_check = any(a.action_type == ActionType.CHECK for a in legal_actions)
        can_bet = any(a.action_type == ActionType.BET for a in legal_actions)
        can_raise = any(a.action_type == ActionType.RAISE for a in legal_actions)

        to_call = game.betting_round.current_bet - player.round_bet

        # Mixed strategy randomization
        rand = self._rng.random()

        # Polarized strategy for strong hands
        if s >= 80:
            if rand < 0.2 and can_check and game.phase <= GamePhase.FLOP:
                if can_check:
                    return Action.check()
            if can_raise:
                return Action.raise_(self._valid_raise_amount(game, player))
            if can_bet:
                return Action.bet(self._valid_bet_amount(game, 0.7))
            return Action.call(min(to_call, player.stack))

        # Semi-bluff with strong draws
        if draws and hand_type <= 4:
            total_outs = sum(d.get("outs", 0) for d in draws)
            if total_outs >= 12:
                if can_raise:
                    return Action.raise_(self._valid_raise_amount(game, player))
                if can_bet:
                    return Action.bet(self._valid_bet_amount(game, 0.66))
            elif total_outs >= 8 and rand < 0.6:
                if can_bet:
                    return Action.bet(self._valid_bet_amount(game, 0.5))
                if can_raise:
                    return Action.raise_(self._valid_raise_amount(game, player))

        # Bluff frequency based on board texture
        board_texture = self._board_texture(game.community_cards)
        bluff_chance = self.config.bluff_frequency
        if board_texture == "dry":
            bluff_chance *= 1.5
        elif board_texture == "wet":
            bluff_chance *= 0.5

        if s < 40 and can_bet and rand < bluff_chance:
            return Action.bet(self._valid_bet_amount(game, 0.33))

        # Default to medium logic
        return self._medium_decision(strength, legal_actions, game, player, position)

    def _expert_decision(self, strength: dict, legal_actions: list[Action],
                         game: GameState, player: Player, position: str) -> Action:
        """Expert level with deeper thinking — placeholder for MCTS integration."""
        # For now, uses advanced with more randomization
        return self._advanced_decision(strength, legal_actions, game, player, position)

    def _detect_draws(self, hole: list[Card], community: list[Card]) -> list[dict]:
        """Detect drawing possibilities."""
        draws = []
        all_cards = hole + community
        ranks = [c.rank.value for c in all_cards]
        suits = [c.suit.value for c in all_cards]

        # Flush draw detection
        suit_counts = {}
        for c in all_cards:
            suit_counts[c.suit.value] = suit_counts.get(c.suit.value, 0) + 1
        for suit, count in suit_counts.items():
            if count == 4:
                draws.append({"type": "flush_draw", "outs": 9, "description": "同花听牌"})

        # Straight draw detection
        unique_ranks = sorted(set(ranks))
        for i in range(len(unique_ranks) - 3):
            if unique_ranks[i + 3] - unique_ranks[i] <= 4:
                missing = (unique_ranks[i] + unique_ranks[i + 3]) - sum(unique_ranks[i:i + 4])
                outs = 4 if missing else 8
                if outs == 8:
                    draws.append({"type": "open_ended", "outs": 8, "description": "两头顺听牌"})
                elif outs == 4:
                    draws.append({"type": "gutshot", "outs": 4, "description": "卡顺听牌"})

        # Wheel draw
        if set([14, 2, 3, 4]).issubset(set(ranks)):
            draws.append({"type": "wheel_draw", "outs": 4, "description": "轮子听牌"})

        return draws

    def _board_texture(self, community: list[Card]) -> str:
        """Classify board texture."""
        if len(community) < 3:
            return "preflop"

        ranks = [c.rank.value for c in community]
        suits = [c.suit.value for c in community]

        # Check for flush draw on board
        suit_counts = {}
        for s in suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1

        has_flush_draw = any(c >= 3 for c in suit_counts.values())

        # Check for straight draws
        sorted_ranks = sorted(ranks)
        has_straight_draw = False
        if len(sorted_ranks) >= 3:
            for i in range(len(sorted_ranks) - 2):
                if sorted_ranks[i + 2] - sorted_ranks[i] <= 4:
                    has_straight_draw = True

        # High card presence
        high_ranks = sum(1 for r in ranks if r >= 10)

        if has_flush_draw and has_straight_draw:
            return "very_wet"
        elif has_flush_draw or has_straight_draw:
            return "wet"
        elif high_ranks >= 2:
            return "high_card"
        else:
            return "dry"

    def suggest_training(self, game: GameState, player_idx: int) -> list[str]:
        """Analyze the current situation and suggest training focus areas."""
        suggestions = []
        player = game.players[player_idx]
        rel_pos = (player_idx - game.dealer_idx) % len(game.players)

        if rel_pos <= 2 and game.phase == GamePhase.PREFLOP:
            hand_strength = EquityCalculator.quick_equity(player.hole_cards)
            if hand_strength.get("category") == "weak" and player.status != PlayerStatus.FOLDED:
                suggestions.append("EP weak hand discipline — fold more from early position")

        if game.phase >= GamePhase.FLOP:
            result = HandEvaluator.evaluate(player.hole_cards, game.community_cards)
            if result.rank.value <= 2 and player.round_bet > 0:
                suggestions.append("Weak made hand pot control — check more with marginal hands")

        return suggestions
