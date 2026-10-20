# 低模岛组件

`components/island/island.tscn` — 一座可直接实例化的 low-poly 漂浮岛：
岛中央一座台地山，绿色草毯覆盖岛面，岛缘和山体上散落着石头，草丛成簇分布。

![3/4 预览](island_preview.png)

![顶视布局](island_top_preview.png)

![山脚过渡](island_foot_preview.png)

## 节点结构

```
Island (Node3D, island.gd)
├── WorldEnvironment      程序化天空 + 雾 + Filmic 色调
├── Sun                   主光（带阴影）
├── FillLight             冷色补光（无阴影）
├── BounceLight           从下方来的云海反光（无阴影）
├── PreviewCamera         当前相机，用于单独打开场景时取景
├── IslandBase            sky-island-basic.glb，scale 13，台面刚好落在 y = 0
│   └── SkyIsland
├── Ground                plain_terrain.glb × 116，多尺度拼成连续草毯
├── Mountain              low_poly_nest_mountain.glb，scale 0.3，位于原点
│   └── NestMountain
└── Scatter
    ├── Rocks             66 块 low_poly_rock
    │   ├── RimBoulders   岛缘大石
    │   ├── FieldBoulders 草地上的石头与前景石组
    │   ├── MountainFoot  山脚碎石
    │   └── MountainBoulders 山腰台地上的石头
    └── Grass             922 丛 grass_tuft / grass_clump
        ├── IslandGrass
        └── MountainGrass
```

## 关键尺度

| 元素 | 值 | 说明 |
| --- | --- | --- |
| 岛屿本体 | scale **13** | glb 台面局部高度 0.71 → 缩放后 9.23 m，节点 y = −9.23，台面落到 **y = 0** |
| 岛屿台面 | 半径约 **29.5–34.5 m** | 棕色岩台，外圈只留 1–3 m 薄岩唇，其余用草块和边缘碎块盖住 |
| 山体 | scale **0.30**，yaw −18° | 山脚半径约 **11–16 m**，峰顶约 **15.6 m**；含水下裙边总高约 18.6 m |
| 草地地形块 | 10 m 模型，**五种尺度** | 大块 scale 1.7–2.45 / 中块 1.0–1.6 / 小块 0.55–0.95 / 补缝块 0.7–1.2 / 岛缘碎块 0.55–1.1 |
| 山脚过渡 | 20 块抬升地形 | 只叠在草毯上（不互相堆叠），把山脚埋进缓坡里 |
| 石头 | 2.9 m 模型，scale 0.20–1.7 | 岛缘大石、草地石、山脚碎石、山腰石四档 |
| 草 | 0.41–0.77 m 模型，scale 0.7–1.7 | 约 100 个草簇，岛面 + 山腰台地 |

所有变换都已烘进 `.tscn`（静态摆放，无运行时随机）。同一份场景每次打开的位置完全一致。

## 四个比例 / 层次问题的处理

1. **山与岛的比例**：岛体从 scale 11 放大到 13（台面直径约 62 m），山体保持 scale 0.30
   （峰顶约 15.6 m、山脚宽约 26 m），山不再占掉半个岛，草毯和石头有足够的空间。
2. **岛缘裸面**：草块分五档尺度铺，外圈再补两圈岛缘碎块；覆盖检测会优先填掉
   绿色草毯里的空洞，最后只剩一圈很薄的棕色岩唇。
3. **地形不机械**：大/中/小/补缝/岛缘五档随机尺寸，高度缩放 0.8–1.8 不等；
   大块负责大起伏，小块负责坡脚和缝隙，不再是一圈同样大的圆垫子。
4. **山脚过渡**：山脚周围 20 块抬升地形是从“纯草毯表面”向上叠的，不会互相堆成
   悬空的绿板；地形先抬到 1–2 m 的缓坡，山体再落进去，所以看不到垂直的墙。

## 光照 / 氛围

- 左前上方暖色主光拉出长阴影，冷色补光把暗面提亮，下方反光模拟云海反射。
- 程序化天空 + 很淡的雾 + Filmic + 饱和度 / 对比度调整，保持 low-poly 的高饱和面感。
- `PreviewCamera` 已设为 current，直接按 F6 就能看到预览图的角度。

## 碰撞

`island.gd` 在 `_ready()` 里给 `Ground`、`Mountain`、`Scatter/Rocks` 下的每个
`MeshInstance3D` 动态补一个 `StaticBody3D + CollisionShape3D`（三角面碰撞）。
草地不参与碰撞。岛屿台面本身由 `sky-island-basic.glb` 里名字带 `-col` 的节点
自带一个碰撞体，不需要脚本再处理。

如果只想要视觉、不想要碰撞，把 `Island.build_collision` 设为 `false` 即可。

## 展示版 / 地形版

- **`island.tscn`**：完整展示版，包含 WorldEnvironment、三盏灯、PreviewCamera、
  922 丛草和 66 块石头（已合并成 MultiMesh，见 `ground_scatter/`），适合单独打开预览。
- **`island_terrain.tscn`**：主场景用的地形版，只保留 `IslandBase` / `Ground` /
  `Mountain` 和 `island.gd`，没有展示节点和巨型草石。文件 27 KB。

主场景 `scenes-3d/jurassic-island/jurassic-island.tscn` 实例化的是地形版，
再实例化烘焙好的 `local_scatter.tscn`（720 草 + 180 石，静态节点）。
主场景本身没有运行时脚本；地形/山体碰撞仍由 `island.gd` 在组件内补齐，
本地草石碰撞已经烘进 `local_scatter.tscn`。

完整展示版的 `show_presentation` / `show_scatter` 导出开关保留，
其他场景如果直接实例化 `island.tscn` 可以用它们隐藏展示节点和草石。

## 园区入口 `ParkPerimeter`

`island.tscn` 里挂了一个 `ParkPerimeter` 节点：**沿岛缘内缩一圈的断续围墙 + 大门**，
围住全岛 **63%**（2192 / 3504 m²），山体偏心坐在里面。

```
ParkPerimeter                   ← 整体可挪动（改半径/跨度要重跑烘焙，见下）
  ├─ Gate                       ← 大门（components/island/park_gate/）
  ├─ Walls/                     ← 40 段残墙（2.9 m/段，长短不一的连续段之间是塌口）
  └─ Debris/                    ← 碎石堆（塌口/门墩/围内散落）+ 4 段倒伏墙
```

![入口预览](park_perimeter/park_perimeter_preview.png)

### 布局规则

| 项 | 值 | 说明 |
| --- | --- | --- |
| 围墙走向 | **沿岛缘内缩 5 m** | 每个角度射线量岛缘半径（30–36 m），墙不会挂在崖坡上 |
| 覆盖角度 | 门 **±140°** | 背后留 80° 豁口 |
| 围住面积 | **2192 m² = 63%** | 岛面实测 3504 m² |
| 山体偏移 | **12 m**（朝 280°） | 约可用进深的 75%，不再是对称同心圆 |
| 单段墙长 | 2.90 m | 与 `ruined_wall` 资产一致，段内接缝严丝合缝 |
| 连续段长度 | 1–5 段（2.9–14.5 m） | **长短不一**，每段之后必是塌口 |
| 塌口长度 | 1.2–3.6 m | 塌口处丢碎石，部分再倒一段墙 |
| 贴地 | 逐段射线取地面高度 | 相邻 2.9 m 高差 > 0.42 m 就强制断开；外侧 2.5 m 陡降 > 1.2 m 也断开（崖边塌口） |

破败感不是靠贴图，靠三件事：**断续**（长短不一的残段 + 塌口）、**沉降**
（每段独立贴地 + 28% 的段额外下沉，墙头高低不齐）、**碎片**（塌口碎石、倒伏墙、门口撞击堆）。

### 改布局 = 改参数 + 重跑烘焙

场景是**烘出来的静态节点**，不是运行时生成：墙要贴在真实地面高度上，而地面碰撞是
`island.gd` 运行时才补的，编辑器里量不到。所以参数改完要重烘：

```bash
cd /Users/zhouyunge/Documents/godot/open-jurassic-island
/Applications/Godot.app/Contents/MacOS/Godot --path . \
  --script res://components/island/park_perimeter/bake_perimeter.gd -- \
  res://components/island/park_perimeter/park_perimeter.tscn
```

参数都在 `bake_perimeter.gd` 顶部（`RING_R` / `SPAN_DEG` / `RUN_MAX` / `GAP_*` /
`STEP_BREAK` / `SINK_VARIANCE` …），末尾可再传一个随机种子换一套破败分布。
**必须带真实渲染器跑**（不要 `--headless`）：headless 的渲染与物理都是 dummy，
射线打不到地面、实例变换也存不下来。

> ⚠️ **别把 `ParkPerimeter` 挪进 `Island` 节点下面**。主场景 `jurassic-island.tscn` 给
> `Island` 加了 `Transform3D(32.258, 0, 0, 0, 20.9677, 0, 0, 0, 32.258, ...)` ——
> **32 倍、而且 Y 轴非等比**，大门进去会被拉成 340 m 宽的假门楼。
> 要放进主场景，请摆在 `Island` 的**兄弟位置**（1:1 米制）。

## 草石现在是 MultiMesh

`Scatter` 不再是上千个道具节点，而是实例化了
`components/island/ground_scatter/island_scatter.tscn`：

```
Scatter                        ← MultiMesh 散布（17 个节点 / 988 个实例 / 8 个 draw call）
  ├─ Grass
  │   ├─ IslandGrass           ← 分组容器（保留原来的层级语义）
  │   │   ├─ GrassTuft         ← MultiMeshInstance3D（564 实例）
  │   │   └─ GrassClump        ← MultiMeshInstance3D（314 实例）
  │   └─ MountainGrass
  │       ├─ GrassTuft / GrassClump
  ├─ Rocks
  │   ├─ RimBoulders / FieldBoulders / MountainFoot / MountainBoulders
  │       └─ Rock              ← MultiMeshInstance3D
  └─ RockCollision             ← 运行时生成：1 个 StaticBody3D + 66 个共享凸包形状
```

- 草的 MultiMesh 关掉了投影（`cast_shadow = 0`），上千棵草的阴影是纯浪费。
- 石头碰撞由 `ground_scatter.gd` 在运行时补，形状资源共享，所以 66 块石头只占一份形状数据。
- 位置数据的源是 `ground_scatter/island_scatter.json`，改完要重跑
  `bake_scatter.gd`。细节和踩过的坑见 `ground_scatter/README.md`。
- `island.gd` 的 `collision_groups` 里**不再包含** `Scatter/Rocks`：MultiMesh 不是
  `MeshInstance3D`，三角面补碰撞那套扫不到它，石头碰撞改由散布组件自己负责。
