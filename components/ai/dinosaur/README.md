# 恐龙 AI 模块 `components/ai/dinosaur/`

恐龙的**独立 AI 模块**：感官 → 决策 → 转向 → 身体，一条独立的链路，
跟岛屿、跟场景摆放、跟具体模型都不耦合。

## 目录

```
components/ai/dinosaur/
  dinosaur_ai.gd          # 大脑：状态机 + 决策（class_name DinosaurAI）
  dinosaur_perception.gd  # 感官：看见什么、听见什么（class_name DinosaurPerception）
  dinosaur_blackboard.gd  # 共享记忆（class_name DinosaurBlackboard）
  dinosaur_steering.gd    # 转向 / 避障 / 群体分离（class_name DinosaurSteering）
  dinosaur_body.gd        # 身体的契约 + 执行器（class_name DinosaurBody）
  dinosaur_ai_config.gd   # 调参表（class_name DinosaurAIConfig）
```

## 分层

```
   ┌──────────────┐   写    ┌──────────────┐   读    ┌──────────────┐
   │  感官        │ ──────→ │   黑板        │ ──────→ │   决策        │
   │ Perception   │         │ Blackboard   │         │  DinosaurAI  │
   └──────────────┘         └──────────────┘         └──────┬───────┘
          ↑ 目标 / 声音                                        │ 意图
          │                                                    ↓
   ┌──────────────┐                                   ┌──────────────┐
   │  场景         │                                   │   转向        │
   │ 玩家 / 树 / 墙 │                                   │  Steering    │
   └──────────────┘                                   └──────┬───────┘
                                                                │ 方向 + 速度
                                                                ↓
                                                        ┌──────────────┐
                                                        │   身体        │
                                                        │ DinosaurBody │
                                                        └──────────────┘
```

**感知只往黑板里写，决策只读黑板**，两边不直接通信。加一种感官、加一条
决策规则，都不会牵动另一边。

## 状态机

```
            ┌──────────── 看见目标 ────────────┐
            │                                  ▼
   REST ──▶ PATROL ──▶ INVESTIGATE ──▶ CHASE ──▶ ATTACK
     ▲        │  ▲         │            │          │
     │        │  └─ 听到动静 ┘            │          │
     └─休息够─┘                          └─ 超过记忆力 ┘

   任何状态 ── 血量低 / 遇到大个子 ──▶ FLEE ── 安全 ──▶ PATROL
   任何状态 ── 血量归零 ──▶ DEAD
```

| 状态 | 在干嘛 | 出口 |
| --- | --- | --- |
| `REST` | 站着不动（Idle 动画），歇一会儿 | 歇够 → `PATROL`；看见目标 → `CHASE` |
| `PATROL` | 沿路线走（Walk 动画） | 看见目标 → `CHASE`；听见动静 → `INVESTIGATE`；被大个子吓到 → `FLEE`；巡完一圈 → `REST` |
| `INVESTIGATE` | 走到可疑点看看 | 到了 / 超时 → `PATROL`；看见目标 → `CHASE` |
| `CHASE` | 追目标（Run 动画） | 够到 → `ATTACK`；跟丢 → `INVESTIGATE`（去最后已知位置）；被吓到 → `FLEE` |
| `ATTACK` | 停下面向目标，播攻击动画、发 `attacked` 信号 | 目标跑远 → `CHASE`；跟丢 → `INVESTIGATE` |
| `FLEE` | 往反方向跑 | 安全了 → `PATROL` |
| `DEAD` | 播死亡动画，停 | —— |

## 三个关键设计

### 1. 视线被树挡住 —— 树是掩体，不只是障碍

感知的视线检测是**一条射线**，从眼睛打到目标胸口，打在**植被层**上就算
被挡：

```gdscript
query.collision_mask = LAYER_VEGETATION | LAYER_STRUCTURE | LAYER_WORLD
```

所以玩家躲在香蕉树后面，恐龙**看不见** —— 这是整套 AI 的核心玩法。

注意：**身体能穿过去，看不见**。恐龙的碰撞掩码里没有植被层（不然巡逻
会被树干卡住），但视线会被树干挡住。身体和视线 purposely 分开：
能走过去，但看不清。

大恐龙眼睛高，看得**过**矮树（视线从 4 m 高往下斜，矮树挡不住）；
小恐龙（迅猛龙眼睛 0.8 m）矮树就能挡。体型越大越"看得远"，天然成立。

### 2. 反应延迟 + 记忆

- **反应延迟**（`reaction_time`）：看见目标不是立刻追，先愣 0.2~0.6 秒。
  玩家才有时间跑掉，恐龙也才不像自动炮台。
- **记忆**（`memory_time`）：目标跑进树丛看不见了，恐龙会**奔着最后知道的
  位置**去找（`INVESTIGATE`），而不是当场傻站。记忆过期（5~9 秒）才放弃。

### 3. 群体行为

- **分离**：同伴之间保持距离（`separation_radius`），挤在一起会互相顶开。
- **威慑**：体型比自己大 1.6 倍以上、而且靠得近（`threat_radius`）才算威胁，
  小恐龙会逃命。阈值定得宽一点，不然一头蜥脚龙在附近，满岛的恐龙都在逃，
  巡逻就乱了。
- **卡住看门狗**：想走却挪不动超过 2.5 秒 → 换个路点 / 换个目标。
  玩家站在路中间也不会把巡逻卡死。

## 调参表 `DinosaurAIConfig`

每种恐龙一份（内嵌在各自的场景里当子资源）。改数值就能改性格：

| 参数 | 作用 | 霸王龙 | 迅猛龙 |
| --- | --- | --- | --- |
| `sight_range` | 看多远 | 24 m | 20 m |
| `sight_half_angle_deg` | 视野半角 | 55° | 70° |
| `hearing_range` | 听多远 | 16 m | 22 m |
| `eye_height` | 眼睛高度 | 4 m | 0.8 m |
| `reaction_time` | 反应延迟 | 0.30 s | 0.20 s |
| `memory_time` | 记忆力 | 8 s | 9 s |
| `patrol_speed_scale` | 巡逻速度倍率 | 1.0 | 1.0 |
| `chase_speed_scale` | 追击速度倍率 | 1.45 | 1.9 |
| `attack_range` | 够多近才动手 | 4.2 m | 2.4 m |
| `attack_damage` | 伤害 | 24 | 7 |
| `max_health` | 血量 | 140 | 45 |
| `flee_health_ratio` | 血量低于多少就跑 | 0.25 | 0.5 |
| `body_size` | 体型（比大小用） | 11 m | 2.2 m |
| `threat_radius` | 多近会怕大个子 | 12 m | 10 m |
| `turn_speed_deg` | 转向速度 | 40°/s | 90°/s |

## 碰撞层

`project.godot` 的 `layer_names`：

| 层 | 名字 | 恐龙撞吗 |
| --- | --- | --- |
| 1 | world | ✅ 踩着走 |
| 2 | vegetation | ❌ 不撞（但**挡视线**） |
| 3 | structure | ❌ |
| 4 | prop | ❌ |
| 5 | creature | ✅ 跟同类、玩家 |

恐龙的 `collision_mask = world | creature`：**树、墙、石头都挡不住它们**，
巡逻不会卡住。代价是会从树干里穿过去 —— 用软避让（两侧射线）往空的一边
偏一点来缓解。

## 对外接口

```gdscript
# 状态切换（调试 / 游戏逻辑挂钩）
signal state_changed(from_state: int, to_state: int)
# 挥了一下嘴
signal attacked(target: Node3D, damage: float)
# 彻底放弃了一个目标
signal target_lost(target: Node3D)
# 挨了一下
signal damaged(amount: float, attacker: Node3D)
```

```gdscript
# 挨打（由游戏逻辑调用）
ai.take_damage(12.0, player_node)

# 当前状态 / 记忆（调试 / 自检）
ai.get_state_name()        # "PATROL" / "CHASE" / ...
ai.get_blackboard().target # 当前锁定的目标
```

## 目标从哪来

AI 盯着**组**里的节点（`config.target_group`，默认 `"player"`）。
玩家节点加进 `player` 组就会被盯上：

```gdscript
[node name="CharacterBody3D" type="CharacterBody3D" groups=["player"]]
```

听觉是"目标跑得快就算有声音"：感知读目标的 `velocity`，
跑得越快声音传得越远（`noise_speed_threshold` / `noise_reach_scale`）。
玩家冲刺会被远处的恐龙听见。

## 用法

```gdscript
var trex := preload("res://components/vegetation/dinosaur/t_rex.tscn").instantiate()
trex.route = PackedVector3Array([Vector3(0, 0, 0), Vector3(10, 0, 0)])
add_child(trex)
```

路线留空 = 站着不动（当布景）。路线挂在**身体**上而不是 AI 上 ——
Godot 的场景实例化只允许覆写实例根节点的属性，AI 是子节点，属性存不进
父场景。
