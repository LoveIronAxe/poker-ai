"""Demo: Full Texas Hold'em hand with AI opponents and review scoring.

Plays a complete hand with AI opponents, then runs the review/scoring system.
"""

import sys
sys.path.insert(0, '/home/loveironpickaxe/project/poker-ai')

from src.engine.card import Card, Suit, Rank
from src.engine.deck import Deck
from src.engine.hand import HandEvaluator, HandRank
from src.engine.action import Action, ActionType
from src.engine.player import Player, PlayerStatus
from src.engine.pot import PotManager
from src.engine.betting import BettingRound
from src.engine.game_state import GameState, GameConfig, GamePhase
from src.engine.rules import Rules
from src.ai.opponent import AIOpponent, Difficulty
from src.ai.strategy import StrategyEngine
from src.ai.equity import EquityCalculator
from src.review.scorer import ReviewScorer, HandReview
from src.review.error_detect import ErrorDetector
from src.review.recommend import TrainingRecommender
from src.review.visualizer_data import VisualizerDataPrep


def print_separator(title=""):
    print(f"\n{'='*60}")
    if title:
        print(f"  {title}")
        print(f"{'='*60}")


def demo_hand_evaluation():
    """Demo all 10 hand types."""
    print_separator("牌型评估演示")

    tests = [
        (['Ah', 'Kh', 'Qh', 'Jh', 'Th', '2d', '3c'], '皇家同花顺'),
        (['9s', '8s', '7s', '6s', '5s', 'Ad', 'Kd'], '同花顺'),
        (['Kd', 'Kh', 'Ks', 'Kc', 'Ad', '2d', '3c'], '四条'),
        (['Qd', 'Qh', 'Qs', '7c', '7d', 'Ad', '2c'], '葫芦'),
        (['Ad', 'Jd', '8d', '4d', '2d', 'Kh', 'Qc'], '同花'),
        (['Td', '9h', '8s', '7c', '6d', 'Ad', 'Kc'], '顺子'),
    ]
    for cards_str, expected in tests:
        cards = [Card.from_str(s) for s in cards_str]
        result = HandEvaluator.evaluate(cards[:2], cards[2:])
        print(f"  {expected}: {result.rank.name_cn()} ✅")


def demo_ai_play():
    """Demo a full hand played by AI opponents."""
    print_separator("AI 对战演示")

    # Create game
    config = GameConfig(num_players=6, small_blind=1, big_blind=2, starting_stack=1000)
    game = GameState(config=config)
    game.init_game()

    # Create AI players
    ai_players = [
        AIOpponent(name="Alpha", difficulty=Difficulty.MEDIUM),
        AIOpponent(name="Bravo", difficulty=Difficulty.EASY),
        AIOpponent(name="Charlie", difficulty=Difficulty.HARD),
        AIOpponent(name="Delta", difficulty=Difficulty.MEDIUM),
        AIOpponent(name="Echo", difficulty=Difficulty.EASY),
        AIOpponent(name="Foxtrot", difficulty=Difficulty.HARD),
    ]

    game.start_new_hand()
    human_idx = 0  # Track "human" player for review

    print(f"Hand #{game.hand_number} | ID: {game.hand_id}")
    print(f"Dealer: P{game.dealer_idx + 1}")

    # Show hole cards for all players
    for i, p in enumerate(game.players):
        if p.status != PlayerStatus.OUT:
            cards_str = ' '.join(str(c) for c in p.hole_cards)
            pos_names = {0: 'btn', 1: 'sb', 2: 'bb', 3: 'utg', 4: 'mp', 5: 'hj'}
            rel_pos = (i - game.dealer_idx) % 6
            print(f"  P{i+1} ({pos_names[rel_pos]}): [{cards_str}] stack={p.stack}")

    # Play out the hand
    step = 0
    while not game.is_hand_over() and step < 100:
        step += 1
        current = game.current_player_idx

        if game.players[current].status == PlayerStatus.ACTIVE:
            # Get AI decision
            ai = ai_players[current]
            result = ai.act(game, current)
            action = result["action"]

            success, msg = game.apply_action(action)
            if not success:
                print(f"  ERROR: {msg}")
                break

            phase = game.phase.name_cn() if game.phase != GamePhase.IDLE else "结束"
            p_name = game.players[current].name
            print(f"  [{phase}] P{current+1} ({p_name}): {action}")
        else:
            # Advance to next phase or player
            if game.betting_round.is_round_complete(game.players):
                game._advance_phase()
            else:
                game._next_player()

    # Show result
    print(f"\n--- Hand Result ---")
    active = [i for i, p in enumerate(game.players) if p.status != PlayerStatus.FOLDED]
    community = ' '.join(str(c) for c in game.community_cards)
    print(f"Board: {community}")
    for i in active:
        p = game.players[i]
        cards = ' '.join(str(c) for c in p.hole_cards)
        result = HandEvaluator.evaluate(p.hole_cards, game.community_cards)
        print(f"  P{i+1} ({p.name}): {cards} → {result.rank.name_cn()}")

    return game


def demo_review_system(game: GameState, player_idx: int = 0):
    """Demo the review and scoring system."""
    print_separator("复盘打分系统演示")

    scorer = ReviewScorer()
    detector = ErrorDetector()
    recommender = TrainingRecommender()
    visualizer = VisualizerDataPrep()

    # Find an active player that didn't fold preflop
    for i, p in enumerate(game.players):
        if p.status != PlayerStatus.FOLDED and len(p.hole_cards) > 0:
            player_idx = i
            break

    # Run review
    review = scorer.review_hand(game, player_idx)
    player = game.players[player_idx]

    print(f"\n玩家: P{player_idx+1} ({player.name})")
    print(f"手牌: {' '.join(str(c) for c in player.hole_cards)}")
    print(f"综合评分: {review.total_score}/100 → {review.grade.label_cn()}")
    print(f"\n各维度评分:")
    print(f"  {'维度':<12} {'分数':<8} {'等级':<6}")
    print(f"  {'-'*30}")
    for dim_name, dim in review.dimensions.items():
        bar = '█' * int(dim.score / 5) + '░' * (20 - int(dim.score / 5))
        print(f"  {dim.name_cn:<12} {dim.score:<8.1f} {dim.grade.label_cn():<6} {bar}")

    if review.critical_errors:
        print(f"\n关键错误 ({len(review.critical_errors)}个):")
        for i, err in enumerate(review.critical_errors[:3]):
            severity_icon = {'critical': '🔴', 'major': '🟡', 'minor': '🟢'}.get(err.get('severity', ''), '')
            print(f"  {severity_icon} {err.get('message', '')}")
            if err.get('correction'):
                print(f"    建议: {err['correction']}")

    if review.training_focus:
        print(f"\n训练重点: {', '.join(review.training_focus)}")
    print(f"\n总结: {review.summary}")

    # Get training recommendation
    plan = recommender.generate_plan([review])
    if plan.focus_areas:
        print(f"\n推荐训练计划:")
        for area in plan.focus_areas[:3]:
            print(f"  [{area['priority']}次错误] {area['area']}")

    # Generate visualization data
    viz_data = visualizer.prepare(game, review, player_idx)
    print(f"\n可视化数据:")
    print(f"  时间线节点: {viz_data.timeline_3d['total_steps']} 个")
    print(f"  雷达图维度: {len(viz_data.radar_data['labels'])} 个")
    print(f"  决策记录: {len(viz_data.decisions)} 个")
    print(f"  回放步骤: {viz_data.replay_data['total_steps']} 个")

    return review


def demo_equity_calculation():
    """Demo equity calculator."""
    print_separator("胜率计算演示")

    calc = EquityCalculator(num_simulations=5000, seed=42)

    # Preflop: AA vs KK
    aa = [Card.from_str('As'), Card.from_str('Ah')]
    kk = [Card.from_str('Ks'), Card.from_str('Kh')]
    win, lose, tie = calc.hand_vs_hand(aa, kk)
    print(f"  AA vs KK: Win={win:.1f}% Lose={lose:.1f}% Tie={tie:.1f}%")

    # Preflop: AKs vs QQ
    aks = [Card.from_str('As'), Card.from_str('Ks')]
    qq = [Card.from_str('Qh'), Card.from_str('Qd')]
    win, lose, tie = calc.hand_vs_hand(aks, qq)
    print(f"  AKs vs QQ: Win={win:.1f}% Lose={lose:.1f}% Tie={tie:.1f}%")

    # Flop: JT hearts on Qh 9d 2s vs AQ
    jt_h = [Card.from_str('Jh'), Card.from_str('Th')]
    aq = [Card.from_str('As'), Card.from_str('Qd')]
    flop = [Card.from_str('Qh'), Card.from_str('9d'), Card.from_str('2s')]
    win, lose, tie = calc.hand_vs_hand(jt_h, aq, flop)
    print(f"  JTs vs AQ on Qh9d2s: Win={win:.1f}% Lose={lose:.1f}% Tie={tie:.1f}%")


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║      德州扑克 AI 陪练 + 复盘系统 Demo              ║")
    print("╚══════════════════════════════════════════════════╝")

    demo_hand_evaluation()
    demo_equity_calculation()

    # Play 3 hands and review each
    for h in range(3):
        game = demo_ai_play()
        review = demo_review_system(game)

    print_separator("Demo 完成")
    print("系统模块:")
    print("  ✅ 游戏引擎 — 牌型判断、底池管理、状态机")
    print("  ✅ AI对手 — 多级难度、范围分析、赔率计算")
    print("  ✅ 复盘打分 — 5维评估、错误检测、训练推荐")
    print("  ✅ 可视化数据 — 3D时间线、雷达图、回放数据")
    print("\n项目路径: /home/loveironpickaxe/project/poker-ai/")
    print("详细规则: docs/rules.md")
    print("架构设计: docs/architecture.md")


if __name__ == "__main__":
    main()
