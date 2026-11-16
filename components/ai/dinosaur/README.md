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
| `FLEE` | 往反方向跑 | 逃够 `FLEE_DURATION` 秒 → `PATROL` |
| `DEAD` | 播死亡动画，停 | —— |
| `UNSTICK` | **转向 → 前进**脱困：先原地转一个角度，再朝转完的方向走 | 走动了 → `PATROL`；还是卡 → 继续朝**同一个方向**转更大的角度再试 |

## ⚠️ 朝向：Godot 的前方是 **-Z**

这是这块代码里最容易写错、错了最难查的一处：

```gdscript
# ❌ 错的：atan2(x, z) 是 +Z 方向
rotation.y = atan2(desired.x, desired.z)

# ✅ 对的：Godot 的前方是 -Z
rotation.y = atan2(-desired.x, -desired.z)
```

写错的后果特别隐蔽：**恐龙速度是满的，方向是反的** —— 它会一路**倒着开**，
离自己的巡逻路线越来越远，最后一头撞进树丛里被顶住，然后卡死。
表现是"恐龙在原地抖动 / 到处乱窜"，看起来像 AI 出了问题，其实是朝向量反了。

同一个陷阱在**烘焙脚本**里也有：恐龙的初始朝向要用
`atan2(dir.x, dir.z) + PI`，和身体里的转向逻辑保持一致。

## 三个关键设计

### 1. 视线被树挡住 —— 树是掩体，不只是障碍

感知的视线检测是**一条射线**，从眼睛打到目标胸口，打在**植被层**上就算
被挡：

```gdscript
query.collision_mask = LAYER_VEGETATION | LAYER_STRUCTURE | LAYER_WORLD
```

所以玩家躲在香蕉树后面，恐龙**看不见** —— 这是整套 AI 的核心玩法。

注意：**身体是实心的**，恐龙撞得到树干和残墙（树是掩体、围墙是建筑，
都得站得住），但**看不见**。身体和视线是两回事：
撞得到，但看不清。

为了不让实心的恐龙在巡逻时被树干顶住，布局那边会**沿着整条巡逻路线
清出一条走廊**（宽度 = 恐龙胶囊半径 + 树干半径 + 余量），
再加上转向里的软避让和卡住看门狗，巡逻不会一顿一顿的。

大恐龙眼睛高，看得**过**矮树（视线从 4 m 高往下斜，矮树挡不住）；
小恐龙（迅猛龙眼睛 0.8 m）矮树就能挡。体型越大越"看得远"，天然成立。

### 2. 反应延迟 + 记忆

- **反应延迟**（`reaction_time`）：看见目标不是立刻追，先愣 0.2~0.6 秒
  （`DinosaurAI._update_reaction()` 记下"什么时候才能开始追"，
  `remembers_target()` / `can_attack()` 都卡这个时间）。
  玩家才有时间跑掉，恐龙也才不像自动炮台。
- **记忆**（`memory_time`）：目标跑进树丛看不见了，恐龙会**奔着最后知道的
  位置**去找（`INVESTIGATE`），而不是当场傻站。记忆过期（5~9 秒）才放弃。
- **调查超时**（`investigate_time`）：查了 8 秒还找不到，就放弃回去巡逻，
  不会为了一个够不着的动静在原地站到天荒地老。
- **休息有尽头**（`rest_time`）：巡完一圈歇 6 秒，歇完接着巡逻。
  （"想歇"是一个独立的开关 `_wants_rest`，不是"巡完一圈就永远歇着"。）

### 3. 群体行为

- **分离**：同伴之间保持距离（`separation_radius`），挤在一起会互相顶开。
- **威慑**：体型比自己大 1.6 倍以上、而且靠得近（`threat_radius`）才算威胁，
  小恐龙会逃命。阈值定得宽一点，不然一头蜥脚龙在附近，满岛的恐龙都在逃，
  巡逻就乱了。
- **卡住看门狗**：想走却挪不动超过 2.5 秒 → 换个路点 / 换个目标。
  玩家站在路中间也不会把巡逻卡死。

## 卡住了怎么办：转向 → 前进 → 再转更大的角度

恐龙的**身体是实心的**（树、墙、石头都撞得到），被顶住就动不了。
硬顶没用 —— 得**换个方向**走。脱困（`UNSTICK`）就是这么一套：

```
卡住 ──▶ ① 转向：原地转到"这次要试的朝向"（不动）
         ② 前进：朝转完的方向走一小段（unstick_time）
            ├─ 走动了 ──▶ 脱困成功，换个路点，回到巡逻 / 追击
            └─ 还是卡 ──▶ ③ 朝**同一个方向**再转一个步长 ──▶ 回到 ①
```

转角是**累加**的：30° → 60° → 90° …… 一直朝**同一边**转，
最多转满一圈（每个方向都试一遍，总能找到一个能走的方向）。

第一次转的方向不是随机的 —— 取"撞到的东西的法线反方向"那一侧，
所以大多数情况一下就绕开了。

| 参数 | 作用 | 默认 |
| --- | --- | --- |
| `stuck_timeout` | 想走却挪不动多久算卡住（秒） | 2.0 |
| `unstick_turn_step_deg` | 一次转多少度（步长） | 30 |
| `unstick_time` | 每次"前进"试多久（秒） | 1.2 |

## 调参表 `DinosaurAIConfig`

每种恐龙一份。**数值真源是 `components/dinosaurs/dinosaur_species_config.gd`**（不是场景里的子资源了）：
场景里只留模型、碰撞胶囊和 `species_id`，进场景时 AI 按 `species_id` 去配置里
把这一种的数值读进来（见 `DinosaurAIConfig.apply_species()` /
`components/dinosaurs/dinosaur_species_config.gd`）。改数值只改这一个文件，不用碰场景。

下面这张表是配置的可读版本（设计意图见 `requirements/numerical/dinosaur.md`）：

| 参数 | 作用 | 霸王龙 | 迅猛龙 |
| --- | --- | --- | --- |
| `sight_range` | 看多远 | 24 m | 20 m |
| `sight_half_angle_deg` | 视野半角 | 55° | 70° |
| `hearing_range` | 听多远 | 16 m | 22 m |
| `eye_height` | 眼睛高度 | 4 m | 0.8 m |
| `reaction_time` | 反应延迟 | 0.30 s | 0.20 s |
| `memory_time` | 记忆力 | 8 s | 9 s |
| `investigate_time` | 调查最多花多久 | 8 s | 8 s |
| `rest_time` | 歇多久再接着巡逻 | 6 s | 6 s |
| `patrol_speed_scale` | 巡逻速度倍率 | 1.0 | 1.0 |
| `chase_speed_scale` | 追击速度倍率 | 1.5 | 1.9 |
| `attack_range` | 够多近才动手 | 4.2 m | 2.4 m |
| `attack_damage` | 伤害 | 24 | 7 |
| `max_health` | 血量 | 140 | 45 |
| `flee_health_ratio` | 血量低于多少就跑 | 0.25 | 0.5 |
| `body_size` | 体型（比大小用） | 11 m | 2.2 m |
| `threat_radius` | 多近会怕大个子 | 12 m | 6 m |
| `turn_speed_deg` | 转向速度 | 40°/s | 90°/s |
| `unstick_turn_step_deg` | 脱困时一次转多少度 | 30° | 30° |

## 碰撞层

`project.godot` 的 `layer_names`：

| 层 | 名字 | 恐龙撞吗 |
| --- | --- | --- |
| 1 | world | ✅ 踩着走 |
| 2 | vegetation | ✅ 撞（树干是实心的） |
| 3 | structure | ✅ 撞（残墙是建筑） |
| 4 | prop | ❌ 不撞（石头最高 5 m，跨得过去） |
| 5 | creature | ✅ 跟同类、玩家 |
| 6 | boundary | ✅ 撞（岛缘的隐形围栏，只挡恐龙） |

恐龙的 `collision_mask = world | vegetation | structure | creature | boundary`：
**树、墙挡得住它们，石头挡不住**。

代价是可能被顶住 —— 所以有三重保险：
1. **布局**：沿整条巡逻路线清出一条走廊（宽度 = 胶囊半径 + 树干半径 + 余量），
   路线上不长树；
2. **软避让**（转向里的两侧射线）—— 撞上就沿障碍滑行，不偏离路线；
3. **卡住看门狗** —— 想走却挪不动超过 2 s 就换个路点。

这套规则由 `components/island/tests/verify_island.gd` 守着。

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

### 建筑目标（玩家盖的房子）

玩家用工具盖的房子要能被恐龙拆，就多了一条"盯建筑"的通道：

```gdscript
# 每种恐龙的 DinosaurAIConfig 里填：
config.structure_target_group = "dinosaur_structure"

# 房子加进这个组，就会被恐龙盯上
building.add_to_group("dinosaur_structure")
```

感知会把**两个组**的目标放一起比，谁近盯谁。
留空（默认）就只追玩家，行为跟以前一模一样。

建筑是实心的，所以有两个坑，AI 里都处理了：

| 坑 | 现象 | 处理 |
| --- | --- | --- |
| 建筑挡住自己的视线 | 射向建筑的那条线**先打到建筑自己**，恐龙永远看不见它 | 视线射线**排除目标自己的刚体**（`DinosaurPerception._has_line_of_sight`） |
| 避障把目标也躲开 | 恐龙**围着房子转圈**，永远靠不上去 | 避障射线**忽略当前目标**（`DinosaurSteering.compute` 的 `ignore`） |

攻击生效：`behave_attack` 挥嘴时除了发 `attacked` 信号，
还会对目标调 `take_damage(伤害, 攻击者)` —— 目标实现了这个方法就会掉血
（测试场里的红色建筑就是这么被啃塌的）。

## 用法

```gdscript
var trex := preload("res://components/vegetation/dinosaur/t_rex.tscn").instantiate()
trex.route = PackedVector3Array([Vector3(0, 0, 0), Vector3(10, 0, 0)])
add_child(trex)
```

路线留空 = 站着不动（当布景）。路线挂在**身体**上而不是 AI 上 ——
Godot 的场景实例化只允许覆写实例根节点的属性，AI 是子节点，属性存不进
父场景。
