"""Prepare review data for the 3D visualization frontend.

Generates structured data for:
- 3D timeline rendering
- Radar chart (5D scoring)
- Equity progression graph
- Decision tree visualization
- Heat map data
"""

from dataclasses import dataclass, field

from .scorer import HandReview, DimensionScore, ScoreGrade
from ..engine.game_state import GameState, GameEvent, GamePhase
from ..engine.card import Card


@dataclass
class VisualizationData:
    """Complete visualization data package for one hand review."""
    hand_id: str
    timeline_3d: dict  # 3D time-nodes
    radar_data: dict   # 5D radar chart
    equity_curve: dict  # equity over time
    decisions: list[dict]  # decision tree
    positions_3d: dict  # table positions
    replay_data: dict  # for step-by-step replay


class VisualizerDataPrep:
    """Prepares review data into frontend-ready format."""

    def prepare(self, game: GameState, review: HandReview,
                player_idx: int) -> VisualizationData:
        """Generate all visualization data for one hand."""
        return VisualizationData(
            hand_id=review.hand_id,
            timeline_3d=self._build_timeline_3d(game, player_idx),
            radar_data=self._build_radar(review),
            equity_curve=self._build_equity_curve(game, player_idx, review),
            decisions=self._build_decision_tree(game, player_idx),
            positions_3d=self._build_positions_3d(game),
            replay_data=self._build_replay_data(game, review),
        )

    def _build_timeline_3d(self, game: GameState, player_idx: int) -> dict:
        """Build 3D timeline structure.

        Returns data for rendering a 3D timeline with nodes at each decision point,
        colored by decision quality. Can be rotated/zoomed in 3D space.
        """
        nodes = []
        edges = []

        community_so_far = []
        for i, event in enumerate(game.events):
            # Track community cards
            if event.type == "deal" and "cards" in event.data:
                community_so_far = event.data["cards"]
            elif event.type == "deal" and "card" in event.data:
                community_so_far.append(event.data["card"])

            # Phase change
            x = event.phase.value * 2  # horizontal axis = phase
            y = event.timestamp * 0.5  # vertical axis = time
            z = 0  # depth — could represent pot size

            node = {
                "id": str(i),
                "x": x,
                "y": y,
                "z": z,
                "type": event.type,
                "phase": event.phase.name_cn(),
                "is_player_action": event.player_idx == player_idx,
                "label": event.data.get("action", event.data.get("type", "")),
                "community_cards": list(community_so_far),
                "color": "#6366f1" if event.player_idx == player_idx else "#94a3b8",
                "size": 0.8 if event.player_idx == player_idx else 0.5,
                "timestamp": event.timestamp,
            }
            nodes.append(node)

            if i > 0:
                edges.append({"from": str(i - 1), "to": str(i)})

        return {
            "nodes": nodes,
            "edges": edges,
            "phases": [p.name_cn() for p in GamePhase if p != GamePhase.IDLE],
            "total_steps": len(nodes),
            "player_actions": [n for n in nodes if n["is_player_action"]],
        }

    def _build_radar(self, review: HandReview) -> dict:
        """Build 5-dimensional radar chart data."""
        dim_order = ["range", "position", "odds", "aggression", "mental"]
        labels = ["范围选择", "位置利用", "赔率数学", "侵略平衡", "心理博弈"]
        values = []
        for dim_name in dim_order:
            if dim_name in review.dimensions:
                values.append(review.dimensions[dim_name].score)
            else:
                values.append(50)

        return {
            "labels": labels,
            "values": values,
            "total_score": review.total_score,
            "grade": review.grade.label_cn(),
            "grade_color": review.grade.color(),
            "dimensions": [
                {
                    "name": d.name_cn,
                    "score": d.score,
                    "color": d.grade.color(),
                    "details": d.details,
                    "errors": [e.get("message", "") for e in d.errors],
                }
                for d in review.dimensions.values()
            ],
        }

    def _build_equity_curve(self, game: GameState, player_idx: int,
                            review: HandReview) -> dict:
        """Build equity progression over the hand."""
        # Simplified equity tracking using hand strength as proxy
        data_points = []
        actions = [e for e in game.events
                   if e.player_idx == player_idx and e.type == "action"]

        for event in game.events:
            if event.type in ("deal", "phase_change", "action"):
                community_len = 0
                if event.phase >= GamePhase.FLOP:
                    community_len = 3
                if event.phase >= GamePhase.TURN:
                    community_len = 4
                if event.phase >= GamePhase.RIVER:
                    community_len = 5

                data_points.append({
                    "step": event.timestamp,
                    "phase": event.phase.name_cn(),
                    "equity_estimate": 50 + (community_len * 5),  # placeholder
                })

        return {
            "data_points": data_points,
            "max_equity": 100,
            "phases_marked": [
                {"step": self._find_phase_start(game, p), "label": p.name_cn()}
                for p in [GamePhase.PREFLOP, GamePhase.FLOP,
                         GamePhase.TURN, GamePhase.RIVER]
            ],
        }

    def _build_decision_tree(self, game: GameState, player_idx: int) -> list[dict]:
        """Build decision tree visualization data."""
        decisions = []
        player = game.players[player_idx]
        player_events = [e for e in game.events
                        if e.player_idx == player_idx and e.type == "action"]

        for event in player_events:
            community = []
            if event.phase >= GamePhase.FLOP:
                community = [str(c) for c in game.community_cards[:3]]
            if event.phase >= GamePhase.TURN and len(game.community_cards) > 3:
                community.append(str(game.community_cards[3]))
            if event.phase >= GamePhase.RIVER and len(game.community_cards) > 4:
                community.append(str(game.community_cards[4]))

            decisions.append({
                "phase": event.phase.name_cn(),
                "community": community,
                "hole_cards": [str(c) for c in player.hole_cards],
                "action": event.data.get("action", "?"),
                "stack_remaining": player.stack,
                "pot_size": game.pot_manager.total(),
                "timestamp": event.timestamp,
            })

        return decisions

    def _build_positions_3d(self, game: GameState) -> dict:
        """Build 3D position layout for the poker table."""
        positions = []
        n = len(game.players)
        for i, p in enumerate(game.players):
            angle = (i / n) * 2 * 3.14159 - 1.5708  # start from top
            radius = 3.0
            pos = {
                "seat_idx": p.seat_idx,
                "name": p.name,
                "x": round(radius * 1.5 * (1 - (i / (n - 1)) * 2) if n > 1 else 0, 2),
                "y": 0,
                "z": round(radius * 0.8, 2),
                "stack": p.stack,
                "is_dealer": i == game.dealer_idx,
                "is_active": p.is_active,
                "status": p.status.name,
                "last_action": p.last_action,
            }
            positions.append(pos)

        return {
            "positions": positions,
            "dealer_idx": game.dealer_idx,
            "community_cards": [str(c) for c in game.community_cards],
            "pot_total": game.pot_manager.total(),
        }

    def _build_replay_data(self, game: GameState, review: HandReview) -> dict:
        """Build data for step-by-step replay with the ability to jump in."""
        steps = []
        for i, event in enumerate(game.events):
            step = {
                "step_id": i,
                "phase": event.phase.name_cn(),
                "event_type": event.type,
                "player_idx": event.player_idx,
                "data": event.data,
                "can_resume_from": event.type == "action",
                "resume_state": None,  # Would contain full game state snapshot
            }

            # Mark errors on relevant steps
            for err in review.critical_errors:
                if "timestamp" in err and err.get("timestamp") == event.timestamp:
                    step["has_error"] = True
                    step["error_info"] = {
                        "message": err.get("message", ""),
                        "severity": err.get("severity", ""),
                        "ev_loss": err.get("ev_loss", 0),
                    }

            steps.append(step)

        return {
            "hand_id": review.hand_id,
            "total_steps": len(steps),
            "steps": steps,
            "errors_at_steps": {
                s["step_id"]: s.get("error_info", {})
                for s in steps if s.get("has_error")
            },
        }

    def _find_phase_start(self, game: GameState, phase: GamePhase) -> int:
        """Find the first event timestamp for a phase."""
        for event in game.events:
            if event.phase == phase:
                return event.timestamp
        return 0
