"""AI opponent that plays Texas Hold'em at configurable difficulty levels."""

from dataclasses import dataclass, field
import random
import time

from ..engine.action import Action
from ..engine.game_state import GameState
from ..engine.player import Player
from .strategy import StrategyEngine, StrategyConfig, Difficulty


@dataclass
class AIOpponent:
    """An AI player that makes decisions and can explain its reasoning."""

    name: str
    difficulty: Difficulty = Difficulty.MEDIUM
    strategy_config: StrategyConfig = None
    thinking_time: float = 0.3  # minimum think time for realism
    verbose: bool = False

    # Internal state
    _strategy: StrategyEngine = field(init=False)
    _hand_history: list[dict] = field(default_factory=list)
    _rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self):
        if self.strategy_config is None:
            self.strategy_config = StrategyConfig(difficulty=self.difficulty)
        self._strategy = StrategyEngine(self.strategy_config)

    def act(self, game: GameState, player_idx: int) -> dict:
        """Make a decision and return the action with reasoning."""
        start = time.time()

        action = self._strategy.decide(game, player_idx)

        elapsed = time.time() - start
        if elapsed < self.thinking_time:
            time.sleep(self.thinking_time - elapsed)

        # Build reasoning for transparency
        reasoning = self._generate_reasoning(game, player_idx, action)

        if self.verbose:
            print(f"[AI {self.name}] {reasoning}")

        # Record for learning
        self._hand_history.append({
            "phase": game.phase.value,
            "action": str(action),
            "cards": [str(c) for c in game.players[player_idx].hole_cards],
            "community": [str(c) for c in game.community_cards],
            "reasoning": reasoning
        })

        return {"action": action, "reasoning": reasoning}

    def _generate_reasoning(self, game: GameState, player_idx: int, action: Action) -> str:
        """Generate human-readable reasoning for the decision."""
        player = game.players[player_idx]
        cards = player.hole_cards
        community = game.community_cards

        parts = []
        parts.append(f"Hole: {''.join(str(c) for c in cards)}")

        if community:
            parts.append(f"Board: {''.join(str(c) for c in community)}")

        parts.append(f"Action: {action}")

        return " | ".join(parts)

    def reset_hand(self):
        """Reset per-hand state."""
        self._hand_history.clear()

    def get_stats(self) -> dict:
        """Get playing statistics for this session."""
        if not self._hand_history:
            return {"hands_played": 0}

        actions = [h["action"] for h in self._hand_history]
        folds = sum(1 for a in actions if "Fold" in a)
        raises = sum(1 for a in actions if "Raise" in a or "Bet" in a)

        return {
            "hands_played": len(self._hand_history),
            "vpip": (len(actions) - folds) / len(actions) * 100 if actions else 0,
            "pfr": raises / len(actions) * 100 if actions else 0,
            "aggression_factor": raises / max(1, folds) if folds > 0 else raises
        }


def create_ai_players(num_players: int, difficulty: Difficulty = Difficulty.MEDIUM) -> list[AIOpponent]:
    """Create a pool of AI opponents."""
    names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta", "Iota"]
    ais = []
    for i in range(num_players):
        # Vary difficulty slightly
        diff = difficulty
        if i > 0 and difficulty >= Difficulty.MEDIUM:
            diff = Difficulty(max(1, min(5, difficulty.value + random.randint(-1, 1))))
        ais.append(AIOpponent(name=names[i % len(names)], difficulty=diff))
    return ais
