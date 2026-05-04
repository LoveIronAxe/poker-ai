# 德州扑克 AI 陪练 + 复盘系统 架构设计

## 1. 技术栈

| 层级 | 技术选型 | 原因 |
|------|----------|------|
| 前端框架 | React 18 + TypeScript | 组件化、生态丰富 |
| 3D可视化 | Three.js + React Three Fiber | 围棋5D风格棋盘渲染 |
| 后端框架 | Python FastAPI | 高性能异步、AI集成方便 |
| 实时通信 | WebSocket | 实时对局、AI思考流 |
| 游戏引擎 | Python (自研) | 完全可控的德州扑克逻辑 |
| AI推理 | PyTorch + 自研求解器 | GTO近似 + 范围分析 |
| 数据库 | PostgreSQL + Redis | 牌局历史 + 缓存 |
| 数据分析 | NumPy + Pandas | 统计分析、GTO偏差计算 |

## 2. 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │ Game UI  │ │3D Table  │ │Timeline  │ │Review View │ │
│  │          │ │(Three.js)│ │(3D Time) │ │(Dashboard) │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │
│                         │                                │
│              WebSocket / REST API                        │
└─────────────────────────┼──────────────────────────────┘
                          │
┌─────────────────────────┼──────────────────────────────┐
│                 Backend (FastAPI)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │
│  │Game API  │ │ WS Server│ │Review API│ │Train API  │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘ │
│       │            │            │              │        │
│  ┌────┴────────────┴────────────┴──────────────┴─────┐ │
│  │                  Core Engine                       │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │ │
│  │  │Hand Eval │ │Betting   │ │Pot Calculator    │  │ │
│  │  │          │ │Manager   │ │(Side Pots)       │  │ │
│  │  └──────────┘ └──────────┘ └──────────────────┘  │ │
│  └──────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────┐ │
│  │                  AI Engine                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │ │
│  │  │Range     │ │MCTS      │ │Equity            │ │ │
│  │  │Analyzer  │ │Solver    │ │Calculator        │ │ │
│  │  └──────────┘ └──────────┘ └──────────────────┘ │ │
│  └──────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────┐ │
│  │              Review & Scoring                     │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │ │
│  │  │Dimension │ │Error     │ │Training          │ │ │
│  │  │Scorer    │ │Detector  │ │Recommender       │ │ │
│  │  └──────────┘ └──────────┘ └──────────────────┘ │ │
│  └──────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────┘
```

## 3. 核心模块详细设计

### 3.1 游戏引擎 (src/engine/)

```
engine/
├── __init__.py
├── card.py          # 牌、牌组
├── hand.py          # 手牌、牌型评估
├── deck.py          # 洗牌、发牌
├── player.py        # 玩家状态
├── pot.py           # 底池管理、边池计算
├── action.py        # 下注动作枚举
├── betting.py       # 下注轮管理
├── game_state.py    # 游戏状态机
└── rules.py         # 规则验证
```

**状态机设计：**
```
IDLE → DEALING → PREFLOP → FLOP → TURN → RIVER → SHOWDOWN → IDLE
                                   ↓ 任一阶段有人全下无人跟注
                                   → SHOWDOWN (跳过后续发牌)
```

### 3.2 AI 引擎 (src/ai/)

```
ai/
├── __init__.py
├── range.py         # 手牌范围定义
├── equity.py        # 胜率计算器(蒙特卡洛)
├── decision.py      # 决策树
├── mcts.py          # 蒙特卡洛树搜索
├── gto.py           # GTO近似求解
├── opponent.py      # 对手建模
├── difficulty.py    # 难度级别
└── strategy.py      # 策略整合
```

**AI难度分级：**
| Level | 名称 | 特点 |
|-------|------|------|
| 1 | 初学者 | 基础起手牌表，无位置意识 |
| 2 | 初级 | 有位置概念，基本赔率计算 |
| 3 | 中级 | 范围思考，混合策略 |
| 4 | 高级 | GTO近似，对手建模 |
| 5 | 专家 | 深度MCTS，实时调整 |

### 3.3 复盘系统 (src/review/)

```
review/
├── __init__.py
├── parser.py        # 牌局历史解析
├── scorer.py        # 多维度打分
├── error_detect.py  # 错误检测
├── gto_compare.py   # GTO偏差分析
├── recommend.py     # 训练建议生成
└── visualizer_data.py # 可视化数据准备
```

**打分维度（5D 评估）：**
1. **范围维度**：起手牌选择是否合理
2. **位置维度**：位置利用效率
3. **赔率维度**：底池赔率计算准确度
4. **激进维度**：价值下注和诈唬比例
5. **心理维度**：面对压力的决策质量

### 3.4 前端可视化 (frontend/)

```
frontend/
├── src/
│   ├── components/
│   │   ├── Game/
│   │   │   ├── PokerTable.tsx      # 主游戏桌
│   │   │   ├── Card3D.tsx          # 3D牌组件
│   │   │   ├── PlayerSeat.tsx      # 玩家座位
│   │   │   ├── ActionBar.tsx       # 操作按钮
│   │   │   └── ChipStack.tsx       # 筹码堆
│   │   ├── Review/
│   │   │   ├── Timeline3D.tsx      # 3D时间线
│   │   │   ├── ScoreRadar.tsx      # 雷达图打分
│   │   │   ├── HandReplay.tsx      # 手牌回放
│   │   │   ├── EquityGraph.tsx     # 胜率曲线图
│   │   │   └── ErrorHighlight.tsx  # 错误高亮
│   │   └── Charts/
│   │       ├── PositionStats.tsx   # 位置统计
│   │       ├── RangeHeatmap.tsx    # 范围热力图
│   │       └── ProgressionTree.tsx # 决策树展示
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   └── useGameState.ts
│   └── utils/
│       └── pokerHelpers.ts
└── package.json
```

## 4. API 设计

### REST Endpoints
```
POST   /api/game/new          # 创建新游戏
POST   /api/game/{id}/action  # 执行动作
GET    /api/game/{id}/state   # 获取游戏状态
GET    /api/game/{id}/history # 游戏历史

POST   /api/review/analyze    # 分析一手牌
GET    /api/review/{id}       # 获取复盘结果
GET    /api/review/stats      # 统计数据

GET    /api/train/recommend   # 训练推荐
POST   /api/train/scenario    # 创建训练场景
```

### WebSocket Events
```
Client → Server:
  game.action    # 玩家动作
  game.new       # 请求新游戏
  review.seek    # 跳转到某个时间点继续

Server → Client:
  game.state     # 游戏状态更新
  game.result    # 手牌结果
  ai.thinking    # AI思考过程
  review.data    # 复盘数据推送
```

## 5. 数据结构

### 5.1 GameState
```python
{
    "hand_id": "uuid",
    "players": [
        {
            "id": "uuid",
            "name": "Player",
            "position": "BTN",
            "stack": 1000,
            "hole_cards": ["Ah", "Kh"],
            "current_bet": 0,
            "is_active": True,
            "is_all_in": False
        }
    ],
    "community_cards": ["Qs", "Jh", "2d", "8c"],
    "pot": {"main": 150, "side_pots": []},
    "current_round": "turn",
    "current_player_idx": 2,
    "current_bet": 50,
    "min_raise": 100,
    "dealer_idx": 0
}
```

### 5.2 ReviewData
```python
{
    "hand_id": "uuid",
    "score_total": 87.5,
    "dimensions": {
        "range": {"score": 90, "errors": []},
        "position": {"score": 85, "errors": ["SB位过于激进"]},
        "odds": {"score": 82, "errors": ["转牌赔率不足时跟注"]},
        "aggression": {"score": 88, "errors": []},
        "mental": {"score": 92, "errors": []}
    },
    "critical_errors": [
        {
            "step": 12,
            "round": "flop",
            "action": "call",
            "gto_action": "raise 66%",
            "ev_loss": -15.3,
            "explanation": "两头顺+同花听牌应半诈唬加注"
        }
    ],
    "training_focus": ["3-Bet防守", "庄位偷盲", "听牌半诈唬"]
}
```

## 6. 3D时间线设计（5D围棋风格）

```
时间线示意图（可3D旋转、缩放）：

  Preflop          Flop            Turn          River
  ───●──────────────●──────────────●──────────────●────>
     │              │              │              │
  ┌──┴──┐      ┌───┴───┐     ┌───┴───┐     ┌───┴───┐
  │ AKs │      │ 听花  │     │ 击中  │     │ 坚果  │
  │3-Bet│      │ C-bet │     │ 控池  │     │ 价值  │
  └─────┘      └───────┘     └───────┘     └───────┘
  ✅正确        ⚠️可优化     ✅正确        ✅正确

功能：
- 每个节点展示该步的牌面、胜率、决策
- 点击任意节点 → 从该状态开始继续训练
- 3D旋转查看不同维度
- 颜色编码：绿(正确)/黄(可优化)/红(错误)
```

## 7. 开发阶段规划

### Phase 1：游戏引擎核心
- 完整的德州扑克规则实现
- 牌型判断、边池计算
- 基本CLI界面可玩

### Phase 2：AI对手
- 范围系统
- MCTS决策
- 多级难度

### Phase 3：复盘系统
- 多维度打分
- GTO偏差比较
- 训练推荐

### Phase 4：前端可视化
- React + Three.js 3D桌面
- 时间线组件
- WebSocket实时通信

### Phase 5：完整集成
- 端到端工作流
- 数据持久化
- 性能优化
