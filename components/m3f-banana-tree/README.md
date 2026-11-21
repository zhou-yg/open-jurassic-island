# m3f-banana-tree —— 新香蕉树的可采集组件（树 / 果串分离）

用 `assets/models/m3f-banana/` 的新资产（照参考图复刻的低多边形香蕉树）做的
**可采集香蕉树**组件，和 `components/banana-tree/` 那套**并存、互不影响**。

| 文件 | 作用 |
| --- | --- |
| `m3f_gatherable_banana_tree.tscn` | 组件本体：一棵树（树体 + 果串 + 标签 + 碰撞 + 采集范围） |
| `m3f_gatherable_banana_tree.gd` | 组件脚本（`class_name M3FGatherableBananaTree`，`@tool`） |
| `m3f_gatherable_banana_tree_test.tscn` | 测试场：一排 11 棵树（香蕉数 0 ~ 10）+ `Player` + HUD |
| `m3f_gatherable_banana_tree_test.gd` | 测试场脚本（HUD + `R` 键重置） |
| [GATHERING.md](GATHERING.md) | **采集逻辑说明**：按键 → 减一根 → 记账的完整流程（改这块前先看） |

## 场景结构

```
M3FGatherableBananaTree (Node3D, 脚本)
├── Tree            ← m3f_banana_tree.glb   （假茎 + 18 片叶 + 根部草被）
├── Bunch           ← m3f_banana_bunch.glb  （果柄 + 16 根香蕉，每根一个网格节点）
│                      位置：树体局部 (0.06, 1.45, 0) —— 果柄根部埋进假茎侧面
│                      （果柄是一段弧：先往外甩再往下垂，所以果串挂在树干外侧）
├── CountLabel      ← Label3D，写"香蕉 × N"，挂在树顶
├── InteractArea    ← Area3D（mask = 16 creature），球形采集范围（默认半径 2.8 m）
└── Trunk           ← StaticBody3D（layer = 2 vegetation），圆柱碰撞（假茎）
```

## 采集是怎么工作的

> 完整的实现流程（谁监听、什么时候监听、一次按键怎么只落到一棵树上、
> "少一根"怎么变成画面上真的少一根、记账写到哪儿）见
> **[GATHERING.md](GATHERING.md)**。下面是要点。

1. 玩家走进 `InteractArea` → 这棵树才**醒来**开始收 `_unhandled_input`
   （大世界里几千棵树，不这么弄太浪费）。这只是**粗筛**。
2. 按 **E**（输入动作 `interact`）→ 目标由**准星射线**决定：
   从相机沿视线打一条射线（长度 = `interact_radius`），命中的是这棵树的碰撞体
   才算 —— **站着近没用，得看着它**。射线只可能命中一棵树，
   所以一次按键只掉一根。
3. `harvest()`：默认**一次采 1 根**（`harvest_all_at_once = false` / `harvest_amount = 1`），
   数量 −1 → `banana_count` 的 setter → `_sync_fruits()` → **把第 N 根香蕉的
   `visible` 关掉** → 标签数字同步 −1。
4. 记账：`ResourcesConfig.add_collected_bananas(taken)`（`res://config/resources.gd`）
   → 全局采集统计 +1，并同步到全局资源池 `autoloads/data/resources.gd` 的 "banana"。

> **香蕉不是脚本生成的**：果串模型里 16 根香蕉本来就是 16 个独立网格节点
> （`M3FBanana_Fruit_01` … `M3FBanana_Fruit_16`），脚本只切 `visible`。
> 所以"少一根"就是**真的少一个节点**，不换贴图、不重新生成、不掉帧。

## 参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `banana_count` | 0 | 树上剩多少根香蕉（0 ~ 16）。改动会立刻同步果串和标签 |
| `regrow_seconds` | 0 | 采空后多少秒长回一根。0 = 不长（测试场里保持确定） |
| `interact_radius` | 2.8 | 采集距离（米）= **准星射线的长度**。目标判定靠射线，不靠距离 |
| `harvest_all_at_once` | false | 一次采完 vs 只采 `harvest_amount` 根 |
| `harvest_amount` | 1 | 一次采几根 |
| `show_count_label` | **false** | 数量标签。**默认关** —— 游戏里的树不该顶着"香蕉 × N"的牌子，只有测试场才打开 |
| `label_prefix` / `label_height_offset` / `hide_label_when_empty` | — | 标签的文字 / 高度 / 空树时是否藏 |

## 测试场

`m3f_gatherable_banana_tree_test.tscn` —— 一排 **11 棵树**，香蕉数量 **0 ~ 10**
（间距 4 m），每棵树都把 `show_count_label` 打开（树顶显示"香蕉 × N"），一个 `Player`，HUD 显示：
全局采集数（`config/resources.gd`）、全局资源池 banana（`autoloads/data/resources.gd`）、
每棵树当前的数量。

| 键 | 干什么 |
| --- | --- |
| `WASD` / 鼠标 | 移动 / 转视角 |
| `E` | 采集（一次一根） |
| `R` | 重置整场：每棵树恢复初始数量 + 全局采集数清零 |

**交互提示**：准星**指着**一棵**还有货**的香蕉树时，屏幕下方中间会浮出
**"按 E 采集"**；准星转开、或那棵树被采空了，提示就消失。
提示用的是**和采集同一条射线**（`find_aimed_tree()`），所以不会出现
"提示亮了但按 E 没反应"。测试场 HUD 里还有一个 `Crosshair`（屏幕正中的"+"）——
射线判定需要准星。

（提示和准星都是[b]测试场[/b]的 HUD 元素，不在组件里 —— 组件本身只有树和数量标签。）

## 在 Godot 里用

```gdscript
var tree := preload("res://components/m3f-banana-tree/m3f_gatherable_banana_tree.tscn").instantiate()
tree.banana_count = 8       # 这棵树上有 8 根香蕉
add_child(tree)
```

⚠️ **不要用 Godot 侧 `scale` 调大小** —— 模型已经是 1:1 米制（树高 2.81 m）。
⚠️ 这套**没有接进大世界**；要替换 `banana-tree-tall/short`，得先同步改
`components/vegetation/banana_tree/banana_tree.gd` 里写死的 `tree_height`。

资产细节（尺寸 / 配色 / 节点名 / 做法）见 `assets/AGENTS.md` §2.13。
