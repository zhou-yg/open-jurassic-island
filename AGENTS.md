# 侏罗纪岛

godot 开发的独立游戏，第一人称，生存，建造，冒险游戏

游戏简介：
在几十分钟的限定时间内，建造工具，抵御恐龙，最后通过救援直升机逃出恐龙岛

low-poly 风格

## 模型规范

涉及建模时看 ./assets/AGENTs.md

### 工作方式

- **建模 / 素材类任务不要擅自启动 Godot**（编辑器、运行时都不行）。
  只有任务明确涉及**改 `.tscn` 场景**，或明确要求"在游戏里跑一下"时才启动；
  需要在 Godot 里验证的，**先说明理由并征求同意**。
- 资产侧的验证一律用 Blender headless + 直接读 `.glb` 的 JSON（动画片段、通道数、
  材质色、包围盒）+ 脚本末尾的自检输出，**不靠 Godot 导入来验**。
  详见 `assets/AGENTS.md` §0。


## 核心项目结构

assets/models
- 3d模型

components
- 核心场景组件，基于模型构建的最基础逻辑单元

components/island
- 核心岛屿。**地形**在 `terrain.tscn`（岩台 + 山体，唯一真源）；
  `island.tscn` 是**展示岛**（地形 + 环境/灯光/相机 + 草石 + 围墙 + 香蕉林 + 恐龙），
  大世界只实例化 `terrain.tscn`
- 以前靠 `show_presentation/show_scatter/...` 开关在**运行时**隐藏展示内容 ——
  脚本不是 `@tool`，编辑器里开关不生效，于是"编辑器里一堆巨树、跑起来全没了"。
  拆成两个场景之后，编辑器看到的和跑起来的一致，也不需要隐藏逻辑了

components/island-grass/
- **岛屿植被地面**组件（底板 + 铺满的草 + 摇曳），细节见
  `components/island-grass/README.md`
- 底板 `assets/models/grass/island_grass_base.glb` 的上表面**和岛面同形**
  （轮廓直接抄自 `sky-island-basic.glb` 的 `Cubo_44-col` 台面，56 个点，
  实测偏差 0.85 mm）—— 一根草都不会长到岛外
- **宽可设、长按固定比例**：`长度 = 宽 × 1.03645`（岛面自己的长宽比）。
  改宽时整块底板**等比**缩放，"和岛面同形"永远成立
- 草用**减面版**（`grass_tuft_lod` 48 面 / `grass_clump_lod` 60 面，
  原版 266 / 260），两种草**不混个体**：按"片"分配类型，
  每片全是同一种草、片与片棋盘式交错
- 摇曳走 `components/island-grass/grass_sway.gdshader`（顶点位移 + 每株独立相位）
- 测试场：`components/island-grass/island_grass_test.tscn`（岛 + 底板 + 草 + 公共相机 + HUD），
  `1~4` 切宽度预设、`Z`/`X` 调密度、`R` 换种子、`G` 染色看交错、`C` 摇曳、`T` 地形

components/common/god_viewport/
- **公共测试视口**：所有测试场共用的"管理员视角"（自由飞行 + 环顾 + 鼠标锁定）
- `god_viewport_camera.tscn` —— 相机（`class_name GodViewportCamera`），
  `↑↓←→` 前后左右 / `Space` `Ctrl` 升降 / `Shift` 加速 / 右键拖动转视角 / `F` 锁鼠标
- `god_viewport_capture_button.gd` —— HUD 上的「锁定鼠标 (F)」按钮，
  挂上就自动和相机联动（**不用写接线**）；准星节点名必须叫 `Crosshair`
- 相机启动会进 `god_viewport_camera` 组，按钮靠组找它
- 现在谁在用：`components/dinosaurs/dinosaurs_test.tscn`、
  `components/island-grass/island_grass_test.tscn`
- ⚠️ 改公共组件前先看这两个测试场 —— 改坏了两个都跑不起来

components/dinosaurs
- **恐龙群组件**：按数量把恐龙放进场景，巡逻路线按碰撞 + 习性**运行时算**
- 入参：`initial_count`（数量）、`pool`（内置池）、`spawn_groups`（多个出生点组）
- `add_dinosaur(species_index, spawn_point)`：不传出生点就按配置的聚居地出现
- 细节见 `components/dinosaurs/README.md`

components/vegetation
- 植被组件：`banana_tree`（香蕉树 + 果串）、`dinosaur`（恐龙的身体 + 模型）
  - 恐龙：**每种一个 .tscn**（`t_rex.tscn` / `triceratops.tscn` / …），
    每个场景里带模型、体型、胶囊和 AI 节点

components/ai/dinosaur
- 恐龙的**独立 AI 模块**：感官 → 黑板 → **行为树决策** → 转向 → 身体
  - `dinosaur_perception.gd` 视听（**视线会被树挡住**，玩家能躲树）
  - `dinosaur_blackboard.gd` 共享记忆
  - `dinosaur_behavior.gd` **决策树本体**（濒死 / 脱困 / 逃跑 / 攻击 / 追击 /
    调查 / 休息 / 觅食 / 巡逻 九条分支，每帧从上往下试，第一条走通的就是这帧的行为）
  - `dinosaur_ai.gd` AI 主控（跑行为树、发信号）
  - `dinosaur_state_machine.gd` **只记账**——记住当前是哪个状态
    （PATROL / INVESTIGATE / CHASE / ATTACK / FLEE / REST / …），
    真正的决策在行为树里，状态机不做选择
  - `dinosaur_steering.gd` 转向 / 避障 / 群体分离
  - `dinosaur_body.gd` 身体的契约 + 执行器
  - `dinosaur_ai_config.gd` 每种恐龙的调参表
  - 改行为改这里，不要改岛屿组件

components/ai/behavior_tree
- 通用行为树框架（`BehaviorTree` / `BtNode` / `BtComposite` / `BtLeaf` /
  `BtDecorator`），**被恐龙的行为树用着**，不是死代码
  （`BtDecorator` 目前零调用，是留给以后加反转 / 冷却 / 重复的扩展点）

## 碰撞层约定（3D）

`project.godot` 的 `layer_names` 里命名了 5 层：

| 层 | 名字 | 谁在上面 |
| --- | --- | --- |
| 1 | world | 地形、山体、岛体 |
| 2 | vegetation | 香蕉树的树干 |
| 3 | structure | 园区围墙、大门 |
| 4 | prop | 石头、碎石 |
| 5 | creature | 玩家、恐龙 |
| 6 | boundary | 岛缘的隐形围栏（只挡恐龙） |

**恐龙勾 world + vegetation + structure + creature + boundary**（**不勾 prop**）：
树和墙都挡得住它（恐龙是实心的），石头不挡（石头最高 5 m，
恐龙跨得过去，非要撞只会把巡逻卡住）。
**视线**照样会被树挡住 —— 玩家能躲树。
巡逻的连续性由「路线两侧清出走廊 + 软避让 + 卡住看门狗」保证。
细节见 `components/ai/dinosaur/README.md`。

scenes-3d/jurassic-island/
- 游戏主场景
- jurassic-island.tscn 入口
- `bake_world_vegetation.gd`：**大世界**的植被 + 恐龙烘焙脚本
  （组件里那份是 62 m 尺度的，不能直接放大 32 倍用）
- 主场景里的 `Sky3D` 节点（`addons/sky_3d/`）负责大气 + 日月循环，
  **24 现实分钟一天**（Warcraft III 默认），顶栏时钟由它驱动

## 尺度基准（1414 m 大世界）

> 这一节是**唯一的尺寸事实来源**。改任何模型 / 场景尺寸前先看这里，
> 改完回来更新这里的数字（数字都是从资产和烘焙产物里量出来的，不是估的）。

### 基准：玩家眼高 1.5 m

`components/player/player.tscn`：胶囊 r0.4 h1.8（角色总高 1.8 m），
身体原点 y=0.9 + Head y=0.6 → **相机在 1.5 m**。
下面所有倍数都是相对这 1.5 m 算的。

### 一切道具都是 1:1 米制（**只有岛是缩放的**）

| 东西 | 实际尺寸 | = 玩家眼高 | 备注 |
| --- | --- | --- | --- |
| 香蕉树 矮 | 2.66 m 高 / 2.23 m 宽 | 1.8× | `banana-tree-short` |
| 香蕉树 高 | 4.77 m 高 / 3.40 m 宽 | 3.2× | `banana-tree-tall` |
| 草丛 | 0.77 m 高（×0.85~1.55 缩放） | 0.5× | 齐腰 |
| 草簇 | 0.41 m 高 | 0.3× | 贴地 |
| 石头 | 2.92 × 1.34 × 2.55 m | 0.9× | 齐胸的大石头 |
| 残墙 | 2.90 × 2.25 × 1.54 m | 1.5× | 一段 2.9 m（厚度**含墙脚碎石堆**） |
| 园区大门 | 6.34 × 3.74 m | 4.2× | 原模型 10.56 × 6.24 m，**缩到 60%** |
| 碎石 | 1.82 × 0.46 × 1.90 m | 0.3× | 塌口碎石 |
| 霸王龙 | 11 m 长 / 胶囊 r1.1 | 7.3× | `t_rex.tscn` |
| 蜥脚龙 | 17 m 长 / 胶囊 r0.9 | 11.3× | `apatosaurus.tscn` |
| 三角龙 | 8 m / 胶囊 r0.9 | 5.3× | |
| 剑龙 | 8.5 m / 胶囊 r0.85 | 5.7× | |
| 副栉龙 | 6 m / 胶囊 r0.45 | 4.0× | |
| 迅猛龙 | 2.2 m / 胶囊 r0.22 | 1.5× | 跟人差不多高 |

**岛**是唯一的例外：`components/island/island.tscn`（62 m 的组件）被
`scenes-3d/jurassic-island/jurassic-island.tscn` 的 `Island` 节点放大
**水平 22.8085 倍 / 竖直 14.8261 倍** → **约 1414 m × 1414 m**，山高约 266 m。
竖直只有水平的 0.65 倍，所以大世界的坡度比组件**缓 35%**。

> 2026-11：岛**缩小了一半**（面积减半 → 线性 × 1/√2）：2000 m → 1414 m。
> 「一半」指的是**面积**：走一遍岛从 6.7 分钟变成 4.7 分钟。
> 缩放写在主场景的 `Island` 节点和 `bake_world_vegetation_core.gd` 的
> `ISLAND_SHRINK` 里（两边必须一致），**随岛缩放的常量都乘一遍这个系数**：
> 岛缘半径、领地半径、恐龙间距、噪声频率……（树本身的尺寸**不缩**，还是 1:1 米制）。

### 岛面：就是一整块岩台

**组件岛（62 m）**：岛面就是模型 `sky-island-basic.glb` 自带的**平顶岩盘**
（节点名带 `-col`，导入即 `StaticBody3D`，碰撞也是它给的），y = 0，半径 29.25–34.5 m。

**大世界（1414 m）**：同样只有**岩台**（2026-11 把世界自己烘的那层绿色地表层
`WorldGround` 删掉了 —— 709 块放大压扁的 `plain_terrain`，跟岩台只差 0.5 m，
但多一层碰撞 + 一层绘制，收益不值）。树 / 草 / 石 / 恐龙 / 玩家直接站在岩台上。

| | 值 |
| --- | --- |
| 岩台高度 | y = **0 m**（组件）→ **8.26 m**（世界）= 唯一地面 |
| 岛缘半径 | **672–781 m**（世界） |
| 岛面上有没有坡 | **没有**（平的；只有山体有坡） |

> 组件原先带一层烘出来的草毯（`Ground/Terrain`），它比岩台大一圈
> （最外沿 r ≈ 36.7 m vs 岩台 29.25–34.5 m），草毯外圈那圈树和石头
> **有一半悬在岛外** —— 2026-11 连同 `components/island/ground/` 的烘焙管线一起删了。
> 世界短暂地跑过一版自己的绿色地表层（709 块 `plain_terrain`），也因为
> "跟岩台只差 0.5 m、却多一层碰撞 + 一层绘制"删掉了。
> **现在岛面就只有岩台**，树 / 草 / 石 / 恐龙 / 玩家都直接站在上面。

**（2026-11 新增）可选的植被地面层**：`components/island-grass/island-grass-base.tscn`
是一块**和岛面同形**的绿色底板 + 铺满的草（带摇曳）。
它**不改地形**、**不自带碰撞**（碰撞还是岩台那份），只是"长草的那层土"——
和当年删掉的旧草毯不一样，它的轮廓是**逐点抄岩台**的（56 点，偏差 0.85 mm），
所以不会再出现"草长到岛外"的问题。
它**没有**被实例化进 `island.tscn` / `terrain.tscn`，要用自己拖进去。
细节见 `components/island-grass/README.md`。

**改地面之后必须重烘的东西**（全都在地面上摆着）：

| 要重烘的 | 脚本 |
| --- | --- |
| 散布的石头 / 草 | `ground_scatter/resnap_scatter.gd`（贴地 + 收回岛缘）+ `bake_scatter.gd`（烘） |
| 组件岛的树 / 恐龙 | `components/island/vegetation/bake_vegetation.gd` |
| 组件岛的围墙 + 大门 | `components/island/park_perimeter/bake_perimeter.gd` |
| 大世界的树 / 恐龙 | `scenes-3d/jurassic-island/bake_world_vegetation.gd` |
| 大世界的本地草石 | `scenes-3d/jurassic-island/bake_local_grass.gd` |
| 1:1 米制的园区入口 | `components/island/park_perimeter/bake_entrance_local.gd` |

> ⚠️ 贴地靠**射线**，射线打的是岛体自带的台面碰撞 —— 所以烘焙脚本
> 必须等物理服务器收敛（同一批探针连续两轮量出来的地面高度一样）。
> 落在岛外的道具（草毯时代留下的）要用 `resnap_scatter.gd` 的 `project`
> 模式**收回岛缘**：它会沿"从岛心指向它"的方向往里找第一个还有地面的位置。

### 岛上的数量关系

| | 值 |
| --- | --- |
| 岛 | 1414 × 1414 m（= 943 个玩家高），岛缘半径 672–781 m |
| 恐龙 | **100 只**（霸王龙 18 / 三角龙 18 / 剑龙 14 / 副栉龙 18 / 迅猛龙 20 / 蜥脚龙 12） |
| 每只的领地 | 半径 57~106 m 的不规则圈 |
| 恐龙起点间距 | ≥ 53 m（按 78 m 的格子铺开） |
| 香蕉树 | **5715 棵**（矮 2889 / 高 2826），林子覆盖约 45% 的岛面；树放大到 **1.45 倍**（4~7 m） |
| 树间距 | ≥ 4.5 m（林内实际最近邻 ≈ 6 m） |
| 草丛 / 草簇 | **12000 丛 + 6000 簇**（1:1 米制，撒满全岛）；石头 180 块 |
| 岛面高度 | 岩台 y = **8.26 m**（世界）；玩家出生在 **(0, 9.2, 55)** |
| 雪线 | 63 m（世界，高于地面 54 m；以上是裸岩） |
| 种树坡度上限 | 0.45 m/m（≈24°） |

**性能**：5715 棵树 + 18000 丛草 + 100 只恐龙 → **70 fps**（第一人称），
空中俯瞰（整座岛全在视野里）**77 fps**（M4 Pro）。
树用减面版（LOD）：`assets/models/banana-tree-*/low_poly_banana_tree_lod.glb`
（**491 / 571 面**，原版 1725 / 2014 面，高度和假茎剖面完全一致）——
几千棵用原版面数 GPU 扛不住。改树模要改
`assets/models/banana-tree-*/low_poly_banana_tree.py`（`-- lod` 生成减面版）。

加上全岛草丛 + 加密的林子之后实测 **70 fps**（第一人称）。

### 日月循环（Sky3D）

主场景用 `addons/sky_3d/` 的 Sky3D 做大气和日月：

| | 值 |
| --- | --- |
| 一天多长 | **24 现实分钟**（`TimeOfDay.minutes_per_day = 24`）= **1 游戏分钟 = 1 现实分钟**，Warcraft III 默认 |
| 开局时刻 | **08:00**（早上，白天）—— 从午夜开局的话，一进游戏天是黑的，什么都看不见 |
| 跟系统时钟 | `TimeOfDay.system_sync = false`。开着的话游戏时间是**跟着你电脑的钟走**的：晚上打开游戏就是黑夜（而且不是从 08:00 开始） |
| 白天 / 黑夜 | 顶栏 `DAY_START = 6.0` / `DAY_END = 18.0` |
| 节点 | `Sky3D`（WorldEnvironment）+ `SunLight` + `MoonLight` + `SkyDome` + `TimeOfDay`，**名字不能改**——插件靠名字找这四个子节点 |
| 更新频率 | `update_interval = 0.1`（10 Hz；24 分钟一天不需要 60 Hz） |
| 雾 | Sky3D 的屏幕空间雾 **关**（`SkyDome.fog_visible = false`），只留 Godot 深度雾 0.0005 —— 两层雾会叠糊远景 |

**顶栏时钟不自走**：`TopBar.auto_advance_time = false`，改由
`TimeOfDay.time_changed` → `TopBar.set_time_of_day()` 驱动（信号写在 `.tscn` 里）。
HUD 和天空共用一个时钟，**永远不会走偏**。主菜单里是另一份顶栏实例，自己按
`day_length_seconds = 1440` 走表；进主场景时时钟重置回 00:00。

> ⚠️ 原来的 `FillLight` / `BounceLight` 已删 —— 固定方向的补光在夜里会露出一盏
> 「不动的太阳」。夜里的亮度归 `MoonLight` + 环境光管
> （`night_sky_contribution = 0.35`）。

### 两条烘焙线，别搞混

| | 组件岛（展示用） | 大世界（游戏里） |
| --- | --- | --- |
| 场景 | `components/island/island.tscn` | `scenes-3d/jurassic-island/jurassic-island.tscn` |
| 岛宽 | 62 m | 1414 m |
| 烘焙脚本 | `components/island/vegetation/bake_vegetation_core.gd` | `scenes-3d/jurassic-island/bake_world_vegetation_core.gd` |
| 树 | 1:1，327 棵（矮 174 / 高 153），间距 ≥0.8 m | 减面版 ×1.45（4~7 m），5715 棵 |
| 恐龙 | 10 只（TRex 2 / Triceratops 2 / Parasaurolophus 2 / Velociraptor 2 / Apatosaurus 1 / Stegosaurus 1），双环 + 四辐条 6 个回路（**烘死**） | 100 只，**运行时由 `components/dinosaurs/` 放进去**，巡逻现算 |
| 树模 | 原版（1725 / 2014 面） | 减面版（LOD） |
| 树干碰撞 | 每棵一个 `CollisionShape3D` 节点 | **物理服务器直接挂**（几千个节点太重） |

### 改尺寸时最容易踩的三个坑

1. **朝向是 -Z**：Godot 的前方是 `-basis.z`，而 `atan2(x, z)` 算的是 **+Z**。
   写错恐龙就会**倒着开**，一路离开自己的巡逻路线。身体转向用
   `atan2(-dir.x, -dir.z)`，烘焙里的初始朝向用 `atan2(dir.x, dir.z) + PI`。
2. **斜率要除以基线**：坡度函数返回的是**高度差**不是坡度。基线 12 m 时，
   "上限 1.0"实际只有 0.083 m/m —— 整座岛会被判成陡坡。
   阈值一律按 m/m 填（组件基线 2 m → 0.5，大世界基线 12 m → 0.45）。
3. **烘焙要等物理收敛**：地形碰撞是运行时补的，早到的射线会漏掉一部分地形，
   量出来的地面高度能差 10 m（实测大门直接埋进地里）。
   同一批探针连续两轮量出来的高度完全一样，才算稳（`_physics_settled()`）。



## @tool 政策

**默认不开 `@tool`**。组件脚本只在"编辑器里必须预览"时才开：

| 开着的（有编辑器预览的必要） | 干什么 |
| --- | --- |
| `components/vegetation/banana_tree/banana_tree.gd` | 编辑器里把果串挂上去，看得到整棵树 |
| `components/vegetation/banana_bunch/banana_bunch.gd` | 同上 |
| `components/island/ruined_wall/ruined_wall_run.gd` | 按 `segments` 在编辑器里拼出整段墙 |

**不开的**（运行时才需要，编辑器里本来就不干活）：`ground_scatter.gd` /
`vegetation.gd` / `park_perimeter.gd` / `park_gate.gd` /
`ruined_wall_single.gd`。它们原来带着 `@tool` + `Engine.is_editor_hint()`
守卫 —— 编辑器里什么都不做，纯粹是开销。

> 隐藏 / 显示这类需求**不要用 `@tool` + 运行时开关**去解决：
> 开关在编辑器里不生效，会直接造成"编辑器预览 ≠ 游戏画面"。
> 正确做法是**把场景拆开**（例如 `terrain.tscn` 和 `island.tscn`），
> 谁需要什么就实例化什么。

真正需要 Godot 的场景（改 .tscn、跑游戏验证）按这个顺序：

改 .tscn → 用 godot-runtime 的 add_node / set_node_properties / attach_script，不开编辑器，不弹窗
改完先 validate（headless 语法 + 场景结构检查），不通过就不用启动
需要跑起来看效果 → run_project(background=True) + take_screenshot，你该干嘛干嘛
只有需要你本人肉眼在编辑器里调（动画曲线、导入设置、手动摆场景）时，才 launch_editor