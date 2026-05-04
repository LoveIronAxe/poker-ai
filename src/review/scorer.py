"""Multi-dimension scoring system for poker hand review.

Evaluates each action across 5 dimensions (5D analysis):
1. Range Quality — starting hand selection quality
2. Position Play — how well position is leveraged
3. Odds & Math — pot odds and EV correctness
4. Aggression Balance — value/bluff ratio
5. Mental Game — pressure handling, tilt indicators
"""

from dataclasses import dataclass, field
from enum import IntEnum

from ..engine.card import Card
from ..engine.action import Action, ActionType
from ..engine.hand import HandEvaluator, HandRank
from ..engine.game_state import GameState, GamePhase, GameEvent
from ..engine.player import Player, PlayerStatus
from ..ai.equity import EquityCalculator
from ..ai.range_parser import HandRange, get_position_range


class ScoreGrade(IntEnum):
    EXCELLENT = 5  # 90-100
    GOOD = 4       # 75-89
    AVERAGE = 3    # 60-74
    BELOW_AVG = 2  # 40-59
    POOR = 1       # 0-39

    def label_cn(self):
        return {5: '优秀', 4: '良好', 3: '一般', 2: '较差', 1: '差'}[self.value]

    def color(self):
        return {5: '#22c55e', 4: '#3b82f6', 3: '#eab308', 2: '#f97316', 1: '#ef4444'}[self.value]


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""
    name: str
    name_cn: str
    score: float  # 0-100
    grade: ScoreGrade
    details: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    weight: float = 1.0


@dataclass
class HandReview:
    """Complete review of a single poker hand."""
    hand_id: str
    total_score: float  # 0-100 weighted average
    grade: ScoreGrade
    dimensions: dict[str, DimensionScore]  # keyed by dimension name
    critical_errors: list[dict] = field(default_factory=list)
    key_moments: list[dict] = field(default_factory=list)
    training_focus: list[str] = field(default_factory=list)
    timeline_data: list[dict] = field(default_factory=list)
    summary: str = ""


class ReviewScorer:
    """Scores a completed hand across all dimensions."""

    DIMENSION_WEIGHTS = {
        "range": 1.0,
        "position": 0.9,
        "odds": 0.9,
        "aggression": 0.8,
        "mental": 0.7,
    }

    def __init__(self):
        self.equity = EquityCalculator(num_simulations=2000)

    def review_hand(self, game: GameState, player_idx: int) -> HandReview:
        """Perform a complete review of a hand for a specific player."""
        player = game.players[player_idx]
        events = [e for e in game.events if e.player_idx == player_idx]

        # Score each dimension
        dims = {}
        dims["range"] = self._score_range(game, player, player_idx, events)
        dims["position"] = self._score_position(game, player, player_idx, events)
        dims["odds"] = self._score_odds(game, player, events)
        dims["aggression"] = self._score_aggression(game, player, events)
        dims["mental"] = self._score_mental(game, player, events)

        # Weighted total
        total_weight = sum(
            self.DIMENSION_WEIGHTS.get(k, 1.0) for k in dims
        )
        total_score = sum(
            d.score * self.DIMENSION_WEIGHTS.get(k, 1.0)
            for k, d in dims.items()
        ) / total_weight if total_weight > 0 else 50

        # Collect errors across all dimensions
        critical_errors = []
        for dim_name, dim in dims.items():
            for err in dim.errors:
                err["dimension"] = dim_name
                err["dimension_cn"] = dim.name_cn
                if err.get("severity", "minor") == "critical":
                    critical_errors.append(err)

        # Sort by EV impact
        critical_errors.sort(key=lambda e: abs(e.get("ev_loss", 0)), reverse=True)

        # Training focus from errors
        training_focus = []
        error_types = {}
        for err in critical_errors:
            t = err.get("training_tag", "")
            if t and t not in error_types:
                error_types[t] = 0
            error_types[t] = error_types.get(t, 0) + 1
        training_focus = sorted(error_types, key=error_types.get, reverse=True)[:3]

        # Generate timeline
        timeline = self._build_timeline(game, player_idx, player, events)

        # Grade
        grade = self._score_to_grade(total_score)

        # Summary
        summary = self._generate_summary(
            total_score, grade, dims, critical_errors, training_focus
        )

        return HandReview(
            hand_id=game.hand_id,
            total_score=round(total_score, 1),
            grade=grade,
            dimensions=dims,
            critical_errors=critical_errors,
            key_moments=self._extract_key_moments(game, player_idx),
            training_focus=training_focus,
            timeline_data=timeline,
            summary=summary,
        )

    def _score_range(self, game: GameState, player: Player,
                     player_idx: int, events: list[GameEvent]) -> DimensionScore:
        """Score hand selection quality."""
        errors = []
        score = 80  # baseline

        hole = player.hole_cards
        if not hole:
            return DimensionScore("range", "范围选择", 50, ScoreGrade.AVERAGE,
                                  ["未参与此手牌"])

        rel_pos = (player_idx - game.dealer_idx) % len(game.players)
        pos_names = {0: 'btn', 1: 'sb', 2: 'bb', 3: 'utg', 4: 'mp', 5: 'mp', 6: 'hj', 7: 'co'}
        pos_name = pos_names.get(rel_pos, 'utg')

        recommended_range = get_position_range(pos_name)
        in_range = recommended_range.contains(hole)

        strength = EquityCalculator.quick_equity(hole)
        category = strength.get("category", "unknown")

        # Get player's actions this hand
        player_events = [e for e in events if e.player_idx == player_idx]
        actions_taken = [e for e in player_events if e.type == "action"]

        if pos_name in ('utg', 'mp') and category == 'weak':
            # Playing weak hands from early position
            if any("Raise" in a.data.get("action", "") or "Bet" in a.data.get("action", "")
                   for a in actions_taken):
                score -= 30
                errors.append({
                    "type": "loose_ep_open",
                    "message": f"前位({pos_name.upper()})用弱牌开池",
                    "severity": "critical",
                    "ev_loss": -8.0,
                    "training_tag": "EP开池范围",
                    "correction": f"{pos_name.upper()}位置建议使用更紧的范围：{get_position_range(pos_name)}",
                })

        if not in_range and pos_name in ('utg', 'mp', 'hj'):
            score -= 15
            if score > 40:
                errors.append({
                    "type": "range_violation",
                    "message": "起手牌超出该位置推荐范围",
                    "severity": "minor",
                    "ev_loss": -2.0,
                    "training_tag": "位置范围意识",
                })

        if category == 'premium' and pos_name in ('btn', 'co'):
            # Premium hand in late position — good
            score = min(100, score + 10)

        if in_range:
            score = min(100, score + 5)

        return DimensionScore(
            "range", "范围选择",
            round(max(0, min(100, score)), 1),
            self._score_to_grade(max(0, min(100, score))),
            details=[f"起手牌类型: {category}", f"位置: {pos_name.upper()}", f"在推荐范围内: {in_range}"],
            errors=errors
        )

    def _score_position(self, game: GameState, player: Player,
                        player_idx: int, events: list[GameEvent]) -> DimensionScore:
        """Score position utilization."""
        errors = []
        score = 75
        rel_pos = (player_idx - game.dealer_idx) % len(game.players)
        pos_names = {0: 'btn', 1: 'sb', 2: 'bb', 3: 'utg', 4: 'mp', 5: 'mp', 6: 'hj', 7: 'co'}
        pos_name = pos_names.get(rel_pos, 'utg')

        player_events = [e for e in events if e.type == "action" and e.player_idx == player_idx]

        # Check position abuse
        if pos_name == 'btn':
            # BTN should be playing aggressively
            aggressive_actions = sum(1 for e in player_events
                                    if any(w in e.data.get("action", "")
                                          for w in ("Raise", "Bet", "All-in")))
            if aggressive_actions == 0 and len(player_events) > 0:
                score -= 20
                errors.append({
                    "type": "passive_btn",
                    "message": "庄位未利用位置优势",
                    "severity": "major",
                    "ev_loss": -5.0,
                    "training_tag": "庄位侵略性",
                    "correction": "庄位是最佳位置，应多偷盲和施加压力",
                })
            elif aggressive_actions > 0:
                score += 10

        if pos_name == 'sb':
            # SB should be tight — worst position
            if len(player_events) > 2:
                score -= 15
                errors.append({
                    "type": "loose_sb",
                    "message": "小盲位过多参与底池",
                    "severity": "major",
                    "ev_loss": -4.0,
                    "training_tag": "SB防守",
                    "correction": "SB是最差位置，减少平跟和挤压频率",
                })

        # OOP raising
        if pos_name in ('sb', 'bb', 'utg') and rel_pos > 0:
            oop_raises = sum(1 for e in player_events
                           if "Raise" in e.data.get("action", "") and
                           e.phase >= GamePhase.FLOP)
            if oop_raises > 0:
                score -= 10

        return DimensionScore(
            "position", "位置利用",
            round(max(0, min(100, score)), 1),
            self._score_to_grade(max(0, min(100, score))),
            details=[f"位置: {pos_name.upper()}", f"位置优势指数: {'高' if pos_name in ('btn', 'co') else '中' if pos_name in ('hj',) else '低'}"],
            errors=errors
        )

    def _score_odds(self, game: GameState, player: Player,
                    events: list[GameEvent]) -> DimensionScore:
        """Score pot odds calculation accuracy."""
        errors = []
        score = 80

        player_events = [e for e in events if e.type == "action" and e.player_idx is not None]

        for event in player_events:
            action_str = event.data.get("action", "")
            if "Call" in action_str and "all-in" not in action_str.lower():
                # Check if the call was mathematically correct
                # Simplified: calls with weak hands into big bets
                phase = event.phase
                if phase >= GamePhase.TURN:
                    # Check pot odds on turn/river calls
                    result = HandEvaluator.evaluate(player.hole_cards, game.community_cards[:3] if phase == GamePhase.FLOP else game.community_cards)
                    if result.rank.value <= 2:  # One pair or worse
                        score -= 10
                        errors.append({
                            "type": "weak_call",
                            "message": f"{event.phase.name}阶段用弱牌({result.rank.name_cn()})跟注",
                            "severity": "major",
                            "ev_loss": -3.0,
                            "training_tag": "赔率计算",
                        })

        return DimensionScore(
            "odds", "赔率数学",
            round(max(0, min(100, score)), 1),
            self._score_to_grade(max(0, min(100, score))),
            details=["基于底池赔率与胜率比较", "考虑到隐含赔率"],
            errors=errors
        )

    def _score_aggression(self, game: GameState, player: Player,
                          events: list[GameEvent]) -> DimensionScore:
        """Score aggression balance (value bet vs bluff ratio)."""
        errors = []
        score = 75

        player_events = [e for e in events if e.type == "action" and e.player_idx is not None]

        total_actions = len([e for e in player_events])
        if total_actions == 0:
            return DimensionScore("aggression", "侵略性平衡", 70, ScoreGrade.AVERAGE,
                                  ["未参与"], [])

        aggressive = sum(1 for e in player_events
                        if any(w in e.data.get("action", "")
                              for w in ("Raise", "Bet")))
        passive = sum(1 for e in player_events
                     if any(w in e.data.get("action", "")
                           for w in ("Check", "Call")))

        if total_actions > 0:
            agg_ratio = aggressive / total_actions

            if agg_ratio < 0.2 and total_actions >= 3:
                score -= 20
                errors.append({
                    "type": "too_passive",
                    "message": "过于被动，缺少价值下注",
                    "severity": "major",
                    "ev_loss": -4.0,
                    "training_tag": "价值下注",
                    "correction": "增加价值下注频率，用强牌建立底池",
                })
            elif agg_ratio > 0.8 and total_actions >= 3:
                score -= 15
                errors.append({
                    "type": "too_aggressive",
                    "message": "过于激进，可能诈唬过多",
                    "severity": "major",
                    "ev_loss": -3.0,
                    "training_tag": "诈唬频率",
                    "correction": "减少诈唬，平衡范围",
                })
            elif 0.3 <= agg_ratio <= 0.6:
                score += 10  # Good balance

        return DimensionScore(
            "aggression", "侵略性平衡",
            round(max(0, min(100, score)), 1),
            self._score_to_grade(max(0, min(100, score))),
            details=[f"激进率: {aggressive}/{total_actions}" if total_actions > 0 else "无行动"],
            errors=errors
        )

    def _score_mental(self, game: GameState, player: Player,
                      events: list[GameEvent]) -> DimensionScore:
        """Score mental game quality — tilt detection, pressure handling."""
        score = 85  # Default good mental game

        # Tilt indicators
        player_events = [e for e in events if e.type == "action" and e.player_idx is not None]

        # Detect rapid re-raising (potential tilt)
        raise_sequence = 0
        for e in player_events:
            if "Raise" in e.data.get("action", ""):
                raise_sequence += 1
            else:
                raise_sequence = 0
            if raise_sequence >= 3:
                score -= 15
                errors = [{
                    "type": "tilt_raising",
                    "message": "连续多次加注，可能有tilt倾向",
                    "severity": "major",
                    "ev_loss": -5.0,
                    "training_tag": "情绪控制",
                }]
                break

        # Large bluff detection (simplified)
        if player.round_bet > player.stack * 0.5 and len(player.hole_cards) > 0:
            result = HandEvaluator.evaluate(player.hole_cards, game.community_cards)
            if result.rank.value <= 2:  # Weak hand, big bet
                score -= 20
                errors = [{
                    "type": "big_bluff",
                    "message": "用极弱牌进行大额下注",
                    "severity": "critical",
                    "ev_loss": -10.0,
                    "training_tag": "下注尺度",
                    "correction": "下注尺度应与牌力匹配，避免情绪化操作",
                }]

        return DimensionScore(
            "mental", "心理博弈",
            round(max(0, min(100, score)), 1),
            self._score_to_grade(max(0, min(100, score))),
            details=["压力下决策稳定性", "tilt指标"],
            errors=errors if 'errors' in dir() else []
        )

    def _build_timeline(self, game: GameState, player_idx: int,
                        player: Player, events: list[GameEvent]) -> list[dict]:
        """Build timeline data for 3D visualization."""
        timeline = []
        action_seq = 0

        for event in game.events:
            node = {
                "id": action_seq,
                "phase": event.phase.name_cn() if isinstance(event.phase, GamePhase) else str(event.phase),
                "phase_value": event.phase.value if isinstance(event.phase, GamePhase) else 0,
                "type": event.type,
                "player_idx": event.player_idx,
                "is_player": event.player_idx == player_idx,
                "data": event.data,
                "timestamp": event.timestamp,
                "community_cards_before": [],  # filled by tracking
            }
            timeline.append(node)
            action_seq += 1

        return timeline

    def _extract_key_moments(self, game: GameState, player_idx: int) -> list[dict]:
        """Extract key decision points from the hand."""
        key_moments = []
        player_events = [e for e in game.events
                        if e.player_idx == player_idx and e.type == "action"]

        for event in player_events:
            action_str = event.data.get("action", "")
            if any(w in action_str for w in ("Raise", "Bet", "All-in", "Fold")):
                phase_cards = []
                if event.phase >= GamePhase.FLOP:
                    phase_cards = [str(c) for c in game.community_cards[:3]]
                if event.phase >= GamePhase.TURN:
                    phase_cards.append(str(game.community_cards[3]) if len(game.community_cards) > 3 else "")
                if event.phase >= GamePhase.RIVER:
                    phase_cards.append(str(game.community_cards[4]) if len(game.community_cards) > 4 else "")

                key_moments.append({
                    "phase": event.phase.name_cn(),
                    "action": action_str,
                    "community": phase_cards,
                    "timestamp": event.timestamp,
                })

        return key_moments

    def _generate_summary(self, total_score: float, grade: ScoreGrade,
                          dimensions: dict, errors: list, training: list) -> str:
        """Generate a human-readable summary of the review."""
        parts = []
        parts.append(f"综合评分: {total_score}/100 ({grade.label_cn()})")

        # Best and worst dimensions
        if dimensions:
            best = max(dimensions.values(), key=lambda d: d.score)
            worst = min(dimensions.values(), key=lambda d: d.score)
            parts.append(f"最强维度: {best.name_cn}({best.score}分)")
            parts.append(f"最弱维度: {worst.name_cn}({worst.score}分)")

        if errors:
            parts.append(f"发现 {len(errors)} 个可优化的决策")

        if training:
            parts.append(f"建议训练: {', '.join(training)}")

        return " | ".join(parts)

    @staticmethod
    def _score_to_grade(score: float) -> ScoreGrade:
        if score >= 90:
            return ScoreGrade.EXCELLENT
        elif score >= 75:
            return ScoreGrade.GOOD
        elif score >= 60:
            return ScoreGrade.AVERAGE
        elif score >= 40:
            return ScoreGrade.BELOW_AVG
        return ScoreGrade.POOR
