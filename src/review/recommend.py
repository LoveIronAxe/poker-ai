"""Training recommendation system.

Based on review results and player history, generates specific,
actionable training plans and practice scenarios.
"""

from dataclasses import dataclass, field
from collections import Counter

from .scorer import HandReview, ScoreGrade
from ..engine.game_state import GameState, GameConfig
from ..engine.card import Card


@dataclass
class TrainingPlan:
    """A structured training plan based on identified weaknesses."""
    focus_areas: list[dict]  # [{"area": ..., "priority": ..., "exercises": [...]}]
    drill_scenarios: list[dict]  # Specific scenarios for practice
    estimated_sessions: int
    weekly_schedule: list[dict]


@dataclass
class PracticeScenario:
    """A specific training scenario to practice."""
    name: str
    description: str
    setup_cards: dict  # hole_cards + community_cards
    position: str
    stack_size: int
    opponent_action: str
    correct_action: str
    explanation: str
    difficulty: int  # 1-5


class TrainingRecommender:
    """Generates training recommendations from review data."""

    # Pre-built training scenarios
    SCENARIO_LIBRARY = {
        "3bet_defense": PracticeScenario(
            name="3-Bet防守",
            description="面对3-Bet的决策训练",
            setup_cards={"hole": ["Ts", "9s"], "community": []},
            position="BTN",
            stack_size=100,
            opponent_action="BB 3-Bet to 12BB",
            correct_action="跟注（有位置+同花连张）",
            explanation="同花连张在BTN对抗BB的3-Bet有足够的隐含赔率跟注",
            difficulty=3,
        ),
        "cbet_dry": PracticeScenario(
            name="干燥牌面C-Bet",
            description="干燥翻牌的持续下注频率",
            setup_cards={"hole": ["As", "5s"], "community": ["Kd", "7h", "2c"]},
            position="CO",
            stack_size=100,
            opponent_action="BB check",
            correct_action="下注33%底池（高频率小注C-bet）",
            explanation="K72彩虹是极干燥牌面，适合高频率小注C-Bet",
            difficulty=2,
        ),
        "draw_semibluff": PracticeScenario(
            name="听牌半诈唬",
            description="用强听牌进行半诈唬加注",
            setup_cards={"hole": ["Jh", "Th"], "community": ["Qh", "9d", "2s"]},
            position="BTN",
            stack_size=100,
            opponent_action="MP bet 66% pot",
            correct_action="加注到2.5x对手下注",
            explanation="两头顺+后门同花听牌是极佳的半诈唬牌，需要建立底池",
            difficulty=3,
        ),
        "river_value": PracticeScenario(
            name="河牌价值下注",
            description="河牌击中后的价值下注尺度",
            setup_cards={"hole": ["Ah", "Kh"], "community": ["Ad", "Kc", "8d", "3s", "2h"]},
            position="BTN",
            stack_size=100,
            opponent_action="BB check",
            correct_action="下注75-100%底池（大价值下注）",
            explanation="顶两对是河牌极强的牌，应该用大注获得最大价值",
            difficulty=2,
        ),
        "bluff_catch": PracticeScenario(
            name="抓诈训练",
            description="识别对手诈唬并用中等牌抓诈",
            setup_cards={"hole": ["9c", "9s"], "community": ["Jd", "7h", "4c", "2s", "3d"]},
            position="BB",
            stack_size=100,
            opponent_action="BTN bet 75% pot on river",
            correct_action="跟注（对方范围中有大量错过的听牌）",
            explanation="顺子听牌全部错过，对手的价值范围很窄，9对足够抓诈",
            difficulty=4,
        ),
    }

    def generate_plan(self, reviews: list[HandReview],
                      session_count: int = 10) -> TrainingPlan:
        """Generate a training plan from multiple hand reviews."""
        if not reviews:
            return TrainingPlan(
                focus_areas=[{
                    "area": "基础训练",
                    "priority": 1,
                    "exercises": ["起手牌范围记忆", "牌型识别练习", "赔率计算练习"],
                }],
                drill_scenarios=[self.SCENARIO_LIBRARY["cbet_dry"]],
                estimated_sessions=3,
                weekly_schedule=[]
            )

        # Aggregate error types
        all_errors = []
        for review in reviews:
            all_errors.extend(review.critical_errors)

        error_counts = Counter(e.get("training_tag", "其他") for e in all_errors)

        # Build focus areas sorted by frequency
        focus_areas = []
        for tag, count in error_counts.most_common(5):
            exercises = self._get_exercises_for(tag)
            focus_areas.append({
                "area": tag,
                "priority": count,
                "error_count": count,
                "exercises": exercises,
            })

        # Find matching scenarios
        relevant_scenarios = []
        for tag, _ in error_counts.most_common(3):
            for key, scenario in self.SCENARIO_LIBRARY.items():
                if tag in scenario.explanation or tag in scenario.name:
                    relevant_scenarios.append(scenario)

        # Weekly schedule
        weekly_schedule = self._build_schedule(focus_areas, session_count)

        return TrainingPlan(
            focus_areas=focus_areas,
            drill_scenarios=relevant_scenarios[:5] or list(self.SCENARIO_LIBRARY.values())[:3],
            estimated_sessions=3 + len(focus_areas) * 2,
            weekly_schedule=weekly_schedule,
        )

    def recommend_next_scenario(self, reviews: list[HandReview]) -> dict:
        """Recommend the single most important next scenario to practice."""
        if not reviews or not reviews[-1].critical_errors:
            return {
                "scenario": self.SCENARIO_LIBRARY["cbet_dry"],
                "reason": "持续下注是德州扑克最基础的技能"
            }

        latest_errors = reviews[-1].critical_errors
        top_error = max(latest_errors, key=lambda e: abs(e.get("ev_loss", 0)))

        # Find best matching scenario
        best_match = None
        for key, scenario in self.SCENARIO_LIBRARY.items():
            if top_error.get("training_tag", "") in scenario.name:
                best_match = scenario
                break

        if not best_match:
            # Return most relevant based on error type
            error_type = top_error.get("type", "")
            if "value" in error_type.lower():
                best_match = self.SCENARIO_LIBRARY["river_value"]
            elif "bluff" in error_type.lower():
                best_match = self.SCENARIO_LIBRARY["bluff_catch"]
            elif "draw" in error_type.lower():
                best_match = self.SCENARIO_LIBRARY["draw_semibluff"]
            else:
                best_match = self.SCENARIO_LIBRARY["cbet_dry"]

        return {
            "scenario": best_match,
            "reason": f"针对你最近的错误: {top_error.get('message', '')}"
        }

    def _get_exercises_for(self, tag: str) -> list[str]:
        """Get training exercises for a specific skill area."""
        exercise_map = {
            "EP开池范围": [
                "记忆各位置开池范围表",
                "练习用范围计算器做Preflop决策",
                "录制30分钟游戏并统计VPIP/PFR",
            ],
            "位置范围意识": [
                "各位置VPIP目标：UTG 12%, MP 18%, CO 25%, BTN 40%",
                "每次翻牌前问自己：'这个位置我会用哪些牌开池？'",
            ],
            "赔率计算": [
                "练习四二法则快速心算",
                "每次跟注前口头计算底池赔率",
                "使用Equity计算器验证直觉",
            ],
            "价值下注": [
                "河牌练习：判断哪些牌力值得下注",
                "三街价值下注练习（翻牌/转牌/河牌连续下注）",
                "记录每次过牌是否错失价值",
            ],
            "诈唬频率": [
                "半诈唬识别练习：哪些听牌适合半诈唬",
                "GTO平衡练习：确保范围中价值/诈唬比例",
                "翻牌后继续下注练习",
            ],
            "下注尺度": [
                "不同牌面的标准下注尺度练习",
                "极化vs合并范围的下注策略",
                "SPR管理与下注规划",
            ],
            "庄位侵略性": [
                "庄位偷盲练习：CO/HJ平跟后3-Bet",
                "庄位翻牌后C-bet练习",
                "庄位河牌决策练习",
            ],
            "SB防守": [
                "SB只玩TOP 20%范围",
                "SB 3-Bet or Fold策略练习",
            ],
            "情绪控制": [
                "冥想/呼吸练习（5分钟）",
                "设定止损限额（3个买入）",
                "每次Bad Beat后暂停5分钟",
            ],
        }
        return exercise_map.get(tag, ["基础翻牌前策略复习", "手牌回顾分析练习"])

    def _build_schedule(self, focus_areas: list[dict],
                        total_sessions: int) -> list[dict]:
        """Build a weekly training schedule."""
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        schedule = []

        for i, day in enumerate(days):
            if i >= total_sessions:
                break
            area = focus_areas[i % len(focus_areas)] if focus_areas else {
                "area": "基础训练", "exercises": ["起手牌范围复习"]
            }
            schedule.append({
                "day": day,
                "focus": area["area"],
                "duration": "30分钟",
                "activities": area.get("exercises", [])[:2],
            })

        return schedule
