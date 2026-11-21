# 采集逻辑说明（`m3f-banana-tree`）

这篇文档讲清楚**"走近一棵树按 E" 这件事在代码里到底发生了什么**：
谁在监听、什么时候开始监听、一次按键怎么只落到一棵树上、"少一根香蕉"是怎么变成
**画面上真的少一根**的、以及采到的数量最后写到哪儿去了。

配套阅读：[README.md](README.md)（组件用法）、[../../AGENTS.md](../../AGENTS.md)（项目结构）。

---

## 0. 一句话概括

> 玩家**看着**某棵树（准星打在树干上）→ 按 `E` → **准星指着的那棵**树少一根香蕉
> （果串里真的少一个网格节点可见）→ 树顶标签数字 −1 → 全局采集统计 +1
> → 全局资源池的 "banana" +1 → 测试场 HUD 刷新。
>
> 站着近**没用**，得看着它 —— 目标是**射线**定的，不是距离。

涉及的三个文件：

| 文件 | 角色 |
| --- | --- |
| [m3f_gatherable_banana_tree.gd](m3f_gatherable_banana_tree.gd) | 树本体：监听按键、减数量、切可见性、记账 |
| [m3f_gatherable_banana_tree.tscn](m3f_gatherable_banana_tree.tscn) | 一棵树的场景（模型 + 标签 + 采集范围 + 树干碰撞） |
| [m3f_gatherable_banana_tree_test.gd](m3f_gatherable_banana_tree_test.gd) | 测试场：HUD 数值、交互提示、重置 |

---

## 1. 场景里有哪些零件

`m3f_gatherable_banana_tree.tscn` 的节点树：

```
M3FGatherableBananaTree (Node3D, 挂 m3f_gatherable_banana_tree.gd)
├── Tree          ← m3f_banana_tree.glb   假茎 + 18 片叶 + 根部草被（只是模型，没有逻辑）
├── Bunch         ← m3f_banana_bunch.glb  果柄 + 16 根香蕉
│                                     每根香蕉 = 一个独立 MeshInstance3D
│                                     名字 M3FBanana_Fruit_01 … _16
├── CountLabel    ← Label3D              树顶的"香蕉 × N"（默认关，见 §5）
├── InteractArea  ← Area3D               **粗筛**：玩家在附近就把这棵树唤醒（省开销）
│                                     collision_mask = 16（creature 层）
│   └── CollisionShape3D ← SphereShape3D  半径 = interact_radius（默认 2.8 m）
└── Trunk         ← StaticBody3D         树干碰撞，collision_layer = 2（vegetation 层）
    └── CollisionShape3D ← CylinderShape3D  半径 0.16、高 1.7
```

**香蕉是模型里的固定节点，不是脚本生成的。** 果串 GLB 里每根香蕉本来就是独立的
网格节点，脚本一个也不新建、一个也不删除，**只切 `visible`**（§3.1）。

---

## 2. 运行时流程

```
                  ┌──────────────────────────────────────────┐
   玩家走进范围 ──▶│ Area3D.body_entered                      │
                  │   → set_process_unhandled_input(true)     │  ← 这棵树开始收按键
                  └──────────────────────────────────────────┘
                                     │
   玩家按 E ─────────────────────────▶│ _unhandled_input(event)
                  （只有"被唤醒的树"才收得到这个事件）        │
                                     ▼
                  ┌──────────────────────────────────────────┐
                  │ _try_interact()                          │
                  │   is_aimed_at()：                        │
                  │   从相机沿视线打一条射线，                │
                  │   命中的是"我"吗？                       │
                  │   → 是才执行 harvest()                   │  ← 目标 = 准星指着的那棵
                  └──────────────────────────────────────────┘
                                     ▼
                  ┌──────────────────────────────────────────┐
                  │ harvest()                                │
                  │   taken = 1（默认一次一根）               │
                  │   banana_count -= taken                   │
                  │   ├─ setter → _sync_fruits()  切香蕉 visible │
                  │   │            → _update_label() 改标签   │
                  │   ├─ ResourcesConfig.add_collected_bananas(taken) │
                  │   ├─ emit bananas_collected(taken)              │
                  │   └─ emit harvested(self, taken)                │
                  └──────────────────────────────────────────┘
                                     ▼
                  ┌──────────────────────────────────────────┐
                  │ 测试场 HUD：Stats 面板 + 底部 Message     │
                  │ + "按 E 采集" 提示重新判定               │
                  └──────────────────────────────────────────┘
```

### Step 0 · 初始化 —— `_ready()`

```gdscript
add_to_group(GROUP)              # 进组 "gatherable_banana_tree"（外部脚本遍历/查询用）
_update_area_shape()             # 把采集范围的球半径同步成 interact_radius
_sync_fruits()                   # 按 banana_count 把前 N 根香蕉显示出来
_update_label()                  # 刷新树顶标签
_update_ticks()                   # 只在 regrow_seconds > 0 时才开 _process
area.body_entered.connect(...)    # 连上"进范围 / 出范围"
set_process_unhandled_input(false)   # ★ 关键：先不收按键
```

### Step 1 · 进范围 —— `_on_area_body_entered()`

`Area3D` 只认 `collision_mask = 16`（creature 层），所以只有玩家（`components/player/player.tscn`
里的胶囊 `collision_layer = 16`、组名 `player`）会触发。

```gdscript
func _on_area_body_entered(body: Node3D) -> void:
    if body != null and body.is_in_group(PLAYER_GROUP):
        set_process_unhandled_input(true)     # 这棵树现在开始收 _unhandled_input
```

出范围时 `_on_area_body_exited()` 会确认**范围内确实没有玩家了**（`_player_in_range() == null`）
才关掉 —— 两个人在范围里交替走动时不会误关。

### Step 2 · 按 E —— `_unhandled_input()`

```gdscript
func _unhandled_input(event: InputEvent) -> void:
    if Engine.is_editor_hint():
        return
    if not event.is_action_pressed("interact"):   # "interact" = E（project.godot 里定义）
        return
    _try_interact()
```

### Step 3 · 目标由**准星射线**决定 —— `_try_interact()`

```gdscript
func _try_interact() -> void:
    # 目标由**准星射线**决定：射线打到谁就是谁
    if not is_aimed_at():
        return
    harvest()
```

判定在 `get_aimed_tree()` 里（静态方法，任何脚本都能用）：

```gdscript
static func get_aimed_tree(scope: Node, reach: float) -> M3FGatherableBananaTree:
    var cam: Camera3D = scope.get_viewport().get_camera_3d()
    var world: World3D = scope.get_world_3d()
    var from := cam.global_position
    var to := from + (-cam.global_transform.basis.z).normalized() * maxf(reach, 0.1)
    var params := PhysicsRayQueryParameters3D.create(from, to)
    params.collision_mask = RAY_MASK          # world(1) + vegetation(2)
    params.collide_with_bodies = true
    params.collide_with_areas = false
    # 排除玩家自己（相机就在玩家胶囊里）
    var exclude: Array[RID] = []
    for node in scope.get_tree().get_nodes_in_group(PLAYER_GROUP):
        if node is CollisionObject3D:
            exclude.append((node as CollisionObject3D).get_rid())
    params.exclude = exclude
    var hit: Dictionary = world.direct_space_state.intersect_ray(params)
    if hit.is_empty():
        return null
    # 从命中的碰撞体往上找，找到那棵树
    var node := hit.get("collider") as Node
    while node != null:
        if node is M3FGatherableBananaTree:
            return node as M3FGatherableBananaTree
        node = node.get_parent()
    return null
```

要点：

- **射线从相机出发、沿视线方向**（`camera.global_transform.basis.z` 的反向），
  长度 = `interact_radius`（默认 2.8 m）—— 这就是"隔着多远能采到"。
- 射线打的是**碰撞体**：树干的 `Trunk`（layer = vegetation）。所以**要看着树干**，
  光站在树旁边没用。
- **玩家自己被排除**（相机在玩家的胶囊里，不排除的话射线会先打中自己）。
- 一条射线只可能命中一棵树 → **天然不会出现"一次按键采好几棵"**，
  不需要再算"最近的那棵"。
- 地面也在射线层里（world），所以低头看地时射线打中地面 → 没有目标。

### Step 4 · 真正采 —— `harvest()`

```gdscript
func harvest() -> int:
    if banana_count <= 0:
        return 0
    var taken: int = banana_count if harvest_all_at_once else mini(harvest_amount, banana_count)
    banana_count -= taken            # ★ 数量减 1（一次一根）
    _regrow_timer = 0.0
    _sync_fruits()                   # 画面上少一根
    _update_label()                  # 标签数字跟着减
    ResourcesConfigRef.add_collected_bananas(taken)   # 记账
    bananas_collected.emit(taken)
    harvested.emit(self, taken)      # 测试场 HUD 靠这个信号刷新
    return taken
```

### Step 5 · "少一根"是怎么变成"画面上少一根"的 —— `_sync_fruits()`

```gdscript
func _sync_fruits() -> void:
    var fruits := _find_fruits()      # 递归找名字以 "M3FBanana_Fruit_" 开头的节点，按编号排
    for index in fruits.size():
        fruits[index].visible = index < banana_count   # 前 N 根显示，其余隐藏
```

`_find_fruits()` 递归遍历 `Bunch` 的子节点、收集名字前缀匹配
`M3FBanana_Fruit_` 的节点，再按名字里的编号排序（`Fruit_02` 在 `Fruit_10` 前面）。

> 所以：**采 1 根 = 把第 N 根香蕉的 `visible` 关掉**。没有换贴图、没有重新生成、
> 没有实例化/销毁节点 —— 也就不会有运行时开销。

### Step 6 · 记账 —— `config/resources.gd`

```gdscript
# res://config/resources.gd
static var collected_bananas: int = 0

static func add_collected_bananas(amount: int) -> int:
    if amount <= 0:
        return collected_bananas
    collected_bananas += amount          # ① 全局采集统计
    _sync_to_global_pool(amount)        # ② 全局资源池的 "banana"
    return collected_bananas
```

② 里是**运行期查找**自动加载 `Resources` 再 `add_amount("banana", amount)`，
而不是直接引用 —— 因为 `autoloads/data/resources.gd` 会 `preload` 本文件，
直接引用会形成循环依赖（`config/resources.gd` 里也写了同样的说明）。

### Step 7 · HUD 侧（测试场）

测试场脚本连的是树发出的 `harvested(tree, amount)` 信号：

```gdscript
tree.connect(&"harvested", _on_tree_harvested)

func _on_tree_harvested(tree: Node3D, amount: int) -> void:
    _last_message = "从 %s 采到 %d 根香蕉（还剩 %d 根）" % [...]
```

Stats 面板每 0.1 s 直接读每棵树的 `banana_count` 重画（不靠信号），
"按 E 采集" 提示也在这时重判（§3.6）。

---

## 3. 几个关键实现细节（为什么这么写）

### 3.1 香蕉是固定节点，脚本只切 `visible`

和 `components/banana-tree/` 同一套思路：**挂果位是场景里摆好的固定节点**，
脚本不生成也不摆位置。好处是：运行时零分配、采集只是改一个 bool、
Godot 侧可以直接对某个 `Fruit_0x` 节点做别的（高亮、动画、飞向玩家）。

### 3.2 目标 = 准星指着的那棵（不是"离得最近的"）

早期版本是"范围内算最近的一棵"来定目标 —— **站着不动**也能采到，
站着不走会一路被旁边的树吸干。现在改成**准星射线**：

- 站得近**没用**，得**看着**它（准星打在树干上）；
- 转开视线 → 按 E 没反应；
- 射线只可能命中一棵树 → 一次按键只掉一根，不用再算"最近的"。

被唤醒（`Area3D`）和被瞄准（射线）是**两件事**：`Area3D` 只负责把这棵树叫醒
（省掉大世界里几千棵树的输入开销），**目标判定只有射线说了算**。

### 3.3 `_unhandled_input` 按需开关

大世界里树有几千棵，每棵都常驻收 `_unhandled_input` 太浪费。
所以 `_ready()` 里先 `set_process_unhandled_input(false)`，
只有玩家真的走进采集范围才打开 —— **没被激活的树连按键事件都收不到**。

`_try_interact()` 里那句 `not tree.is_processing_unhandled_input()` 用的就是这个状态：
它同时表达了"这棵树在范围内"和"这棵树可能参与抢按键"。

### 3.4 数量 setter 是唯一的同步入口

```gdscript
@export_range(0, SLOT_COUNT, 1) var banana_count: int = 0:
    set(value):
        banana_count = clampi(value, 0, SLOT_COUNT)
        _on_param_changed()      # → _sync_fruits() + _update_label()
```

不管数量是从哪来的 —— 采集（`harvest()`）、长果（`add_bananas()`）、
编辑器里改导出参数、场景实例的 override —— **都会走同一个 setter**，
所以"数字"和"画面"永远一致，不会出现数字变了但香蕉没变的情况。

### 3.5 目标判定只有一个来源

**能不能采**、**提示显不显示**、**采的是哪棵**，全都来自**同一条准星射线**：

- `get_aimed_tree(scope, reach)` → 静态方法，射线打中谁就是谁
- `is_aimed_at()` → 这棵树自己问："射线打中的是我吗？"
- `find_aimed_tree()` → 给 HUD 用的包装（提示就靠它）

`InteractArea`（半径 = `interact_radius`）**只是粗筛**：它把玩家附近的树唤醒去收按键，
不参与目标判定。

提示（测试场）也是用 `has_player_in_range()` 判的，所以**不会出现"提示亮了但按 E 没反应"**。

### 3.6 交互提示的判定

```gdscript
# m3f_gatherable_banana_tree_test.gd
func _update_prompt() -> void:
    var target: Node3D = _aimed_tree()             # ← 和采集用的是同一条射线
    if target == null or int(target.get("banana_count")) <= 0:
        _prompt.visible = false
        return
    _prompt.visible = true
    _prompt.text = "按 E 采集"


func _aimed_tree() -> Node3D:
    for tree in _trees:
        if not tree.has_method("find_aimed_tree"):
            continue
        var hit = tree.call("find_aimed_tree")
        if hit != null:
            return hit as Node3D
    return null
```

两个条件才提示：**准星指着它** + **它还有货**。
提示用的是组件自己的射线判定（`find_aimed_tree()`），所以**和实际采集是同一套逻辑**，
不会出现"提示亮了但按 E 没反应"。

测试场的 HUD 里还有一个 `Crosshair`（屏幕正中的"+"）—— 射线判定需要准星，
没有准星玩家不知道该往哪儿看。

---

## 4. 一次采集改了哪些东西

| 对象 | 变化 | 谁改的 |
| --- | --- | --- |
| `banana_count` | −1（一次一根） | `harvest()` |
| 第 N 根香蕉节点 | `visible = false` | `_sync_fruits()`（setter 触发） |
| 树顶 `CountLabel` | 文字 −1，采空后变灰 | `_update_label()`（setter 触发） |
| `ResourcesConfig.collected_bananas` | +1 | `add_collected_bananas()` |
| 全局资源池 "banana" | +1 | `_sync_to_global_pool()` |
| 测试场 HUD | Stats / Message / 提示刷新 | `harvested` 信号 + 每 0.1 s 的 `_refresh()` |

---

## 5. 可调参数（都在组件根节点上）

| 参数 | 默认 | 作用 |
| --- | --- | --- |
| `banana_count` | 0 | 树上剩多少根（0 ~ 16）。**改动会立刻同步果串和标签** |
| `regrow_seconds` | 0 | 采空后多少秒长回一根。0 = 不长 |
| `interact_radius` | 2.8 | 采集半径（米） |
| `harvest_all_at_once` | **false** | 一次采完 vs 只采 `harvest_amount` 根 |
| `harvest_amount` | **1** | 一次采几根（默认一次一根 = 按一次 E 少一根） |
| `show_count_label` | **false** | 树顶标签。默认关，只有测试场打开 |
| `label_prefix` / `label_height_offset` / `hide_label_when_empty` | — | 标签的文字 / 高度 / 空树时是否藏 |

---

## 6. 改这套逻辑时容易踩的坑

### 6.1 ⚠️ 实例的 override 会被序列化器丢掉

场景实例里写 `banana_count = 0`，**保存时这行会被删掉** —— 因为它和脚本默认值（0）相同，
Godot 认为"没改过"。而组件场景的根节点如果写的是 `banana_count = 10`，
实例就会继承 **10**，于是"0 根那棵树"显示成 10 根。

**规矩**：想让实例的默认值和脚本默认值不同（比如空树），就把**组件场景**的
`banana_count` 写成 0（或者干脆不写），别在组件场景里写一个非默认的值。

### 6.2 ⚠️ 提示和采集必须用同一条射线

如果提示用的是"距离 < 某个数"，而采集用的是准星射线，就会出现
"提示亮了但按 E 没反应"或者"能采但没提示"。
**提示直接调组件的 `find_aimed_tree()`**，别自己算距离。

### 6.3 ⚠️ 果串挂树上时柄根必须碰到假茎

模型的果柄是一段弧（切线角 18° → 92°，长 0.66 m），根部埋在假茎侧面
（树体局部坐标 `(0.060, 1.45, 0)`）。挂点偏了就会变成"果串浮在树旁边"。

### 6.4 ⚠️ 别把提示做成组件的一部分

组件是给游戏用的：游戏里的树不该顶着一个"按 E 采集"的牌子。
提示属于**测试场/UI 层**，所以放在测试场脚本里。

---

## 7. 相关文件

| 文件 | 说明 |
| --- | --- |
| [m3f_gatherable_banana_tree.gd](m3f_gatherable_banana_tree.gd) | 树本体脚本（`class_name M3FGatherableBananaTree`，`@tool`） |
| [m3f_gatherable_banana_tree.tscn](m3f_gatherable_banana_tree.tscn) | 一棵树的场景 |
| [m3f_gatherable_banana_tree_test.gd](m3f_gatherable_banana_tree_test.gd) | 测试场脚本（HUD + 提示 + 重置） |
| [m3f_gatherable_banana_tree_test.tscn](m3f_gatherable_banana_tree_test.tscn) | 测试场（一排 11 棵树，数量 0 ~ 10） |
| [../../config/resources.gd](../../config/resources.gd) | 全局配置：`collected_bananas` + `add_collected_bananas()` |
| [../../autoloads/data/resources.gd](../../autoloads/data/resources.gd) | 全局资源池（"banana" 数量） |
| [../../assets/models/m3f-banana/](../../assets/models/m3f-banana/) | 模型（果串里 16 根香蕉是独立网格节点） |
| [../banana-tree/README.md](../banana-tree/README.md) | 旧版（单根香蕉模型）的同类组件，思路一致 |
