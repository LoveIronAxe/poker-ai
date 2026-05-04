"""Error detection — identify specific mistakes in a played hand."""

from ..engine.card import Card
from ..engine.action import Action, ActionType
from ..engine.hand import HandEvaluator, HandRank
from ..engine.game_state import GameState, GamePhase, GameEvent
from ..engine.player import Player, PlayerStatus
from ..ai.equity import EquityCalculator


class ErrorDetector:
    """Detects specific poker errors from hand history."""

    ERROR_TYPES = {
        "fold_winner": "弃掉赢牌",
        "missed_value": "错失价值",
        "overplay_marginal": "过度操作边缘牌",
        "bad_bluff_spot": "不良诈唬时机",
        "sizing_error": "下注尺度错误",
        "call_too_wide": "跟注范围过宽",
        "fold_too_tight": "过度弃牌",
        "slow_play_mistake": "慢打失误",
        "position_mistake": "位置失误",
        "odds_mistake": "赔率计算失误",
    }

    def __init__(self):
        self.equity = EquityCalculator(num_simulations=3000)

    def detect_errors(self, game: GameState, player_idx: int) -> list[dict]:
        """Detect all errors made by a player in this hand."""
        errors = []
        player = game.players[player_idx]

        # Skip if player folded preflop
        if player.status == PlayerStatus.FOLDED:
            return errors

        # Check for missed value opportunities
        errors.extend(self._detect_missed_value(game, player_idx))

        # Check for bad calls
        errors.extend(self._detect_bad_calls(game, player_idx))

        # Check for sizing errors
        errors.extend(self._detect_sizing_errors(game, player_idx))

        # Check for fold mistakes (if we can see opponent cards)
        errors.extend(self._detect_fold_errors(game, player_idx))

        return errors

    def _detect_missed_value(self, game: GameState, player_idx: int) -> list[dict]:
        """Detect spots where player missed value bets."""
        errors = []
        player = game.players[player_idx]
        actions = [e for e in game.events
                   if e.player_idx == player_idx and e.type == "action"]

        for event in actions:
            if event.phase >= GamePhase.RIVER:
                action_str = event.data.get("action", "")
                if "Check" in action_str or "check" in action_str.lower():
                    # On river, check if player had a strong hand
                    community = game.community_cards[:5] if len(game.community_cards) >= 5 else game.community_cards
                    if len(community) + len(player.hole_cards) >= 5:
                        result = HandEvaluator.evaluate(player.hole_cards, community)
                        if result.rank.value >= HandRank.TWO_PAIR.value:
                            errors.append({
                                "type": "missed_value",
                                "phase": event.phase.name_cn(),
                                "hand_strength": result.rank.name_cn(),
                                "message": f"河牌用{result.rank.name_cn()}过牌，错失价值下注机会",
                                "severity": "critical",
                                "ev_loss": -8.0,
                                "training_tag": "价值下注",
                            })

        return errors

    def _detect_bad_calls(self, game: GameState, player_idx: int) -> list[dict]:
        """Detect calls made with insufficient equity."""
        errors = []
        player = game.players[player_idx]
        actions = [e for e in game.events
                   if e.player_idx == player_idx and e.type == "action"]

        for event in actions:
            action_str = event.data.get("action", "")
            if "Call" in action_str and "all-in" not in action_str.lower():
                if event.phase >= GamePhase.TURN:
                    # Rough heuristic: calling big bets on turn/river with weak hands
                    if player.round_bet > game.config.big_blind * 10:
                        community = game.community_cards[:4] if event.phase == GamePhase.TURN else game.community_cards[:5]
                        if len(player.hole_cards) > 0:
                            result = HandEvaluator.evaluate(player.hole_cards, community)
                            if result.rank.value <= HandRank.ONE_PAIR.value:
                                errors.append({
                                    "type": "call_too_wide",
                                    "phase": event.phase.name_cn(),
                                    "hand_strength": result.rank.name_cn(),
                                    "message": f"{event.phase.name_cn()}用{result.rank.name_cn()}跟注大注",
                                    "severity": "major",
                                    "ev_loss": -5.0,
                                    "training_tag": "赔率计算",
                                })

        return errors

    def _detect_sizing_errors(self, game: GameState, player_idx: int) -> list[dict]:
        """Detect bet sizing mistakes."""
        errors = []
        player = game.players[player_idx]
        pot = game.pot_manager.total()

        if pot == 0:
            return errors

        actions = [e for e in game.events
                   if e.player_idx == player_idx and e.type == "action"]

        for event in actions:
            action_str = event.data.get("action", "")
            # Parse the bet amount if available
            for word in action_str.split():
                if word.isdigit():
                    amount = int(word)
                    pot_pct = amount / pot * 100 if pot > 0 else 0

                    # Too small bet (< 20% pot) on wet boards
                    if pot_pct < 20 and amount > 0:
                        pass  # Can be strategic (small c-bet)

                    # Overbet (> 200% pot) without nuts
                    if pot_pct > 200 and event.phase < GamePhase.RIVER:
                        community = game.community_cards[:3] if event.phase == GamePhase.FLOP else game.community_cards
                        if len(player.hole_cards) > 0:
                            result = HandEvaluator.evaluate(player.hole_cards, community)
                            if result.rank.value < HandRank.FLUSH.value:
                                errors.append({
                                    "type": "sizing_error",
                                    "phase": event.phase.name_cn(),
                                    "pot_pct": round(pot_pct, 1),
                                    "message": f"在{event.phase.name_cn()}超额下注{pot_pct:.0f}%底池",
                                    "severity": "major",
                                    "ev_loss": -4.0,
                                    "training_tag": "下注尺度",
                                })

        return errors

    def _detect_fold_errors(self, game: GameState, player_idx: int) -> list[dict]:
        """Detect folds that were too tight given pot odds."""
        errors = []
        actions = [e for e in game.events
                   if e.player_idx == player_idx and e.type == "action"]

        for event in actions:
            action_str = event.data.get("action", "")
            if "Fold" in action_str:
                to_call = game.betting_round.current_bet - game.players[player_idx].round_bet
                pot = game.pot_manager.total()
                if pot > 0 and to_call > 0:
                    pot_odds = to_call / (pot + to_call) * 100
                    # Folding when getting very good odds (< 15% needed)
                    if pot_odds < 15 and len(game.players[player_idx].hole_cards) > 0:
                        # Check if player had decent equity
                        hole = game.players[player_idx].hole_cards
                        # Rough check — any pair or better draw
                        result = HandEvaluator.evaluate(hole, game.community_cards)
                        if result.rank.value >= HandRank.ONE_PAIR.value:
                            errors.append({
                                "type": "fold_too_tight",
                                "phase": event.phase.name_cn(),
                                "pot_odds": round(pot_odds, 1),
                                "message": f"用{result.rank.name_cn()}弃牌，但赔率仅需{pot_odds:.0f}%胜率",
                                "severity": "major",
                                "ev_loss": -2.0,
                                "training_tag": "赔率计算",
                            })

        return errors
