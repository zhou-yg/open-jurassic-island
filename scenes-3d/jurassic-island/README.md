# Jurassic-island 主场景

`scenes-3d/jurassic-island/jurassic-island.tscn` 是游戏的 3D 世界场景
（`Scenes` 的 `"world"` 别名就指向它，主菜单的「开始」按钮会加载这里）。

实现见 `requirements/scenes/juraasic-main.md` 与 `requirements/components/jurassic-island.md`。

## 三个组成部分

| 部分 | 使用的组件 | 场景中的节点 |
| --- | --- | --- |
| 1. 随机地图 | `components/map/random_map/random_map.tscn` | `RandomMap` |
| ↳ 地图的墙 | `components/map/random_map/tree-wall-unit.tscn` | `RandomMap.wall_scene` |
| 2. 岛屿 | `assets/island/sky-island-basic.glb` | `Island/sky-island-basic` |
| 3. 海 | `components/sea/sea.tscn` | `Sea` |
| 补白 | `components/map/random_map/tree-walls.tscn` | `TreeWalls` |

此外还有 `Sun`（平行光）、`WorldEnvironment`（天空 / 雾）、`Player`（第一人称玩家）
和 `HUDLayer/TopBar`（战争迷雾风格的顶部资源 / 时间条）。

## 为什么需要 TreeWalls

随机地图生成的是一个规整的矩形，而 `sky-island-basic.glb` 是一块不规则的台地：
矩形之外还露出一圈光秃秃的岩石，两者形状对不上。

`TreeWalls` 用来补上这部分——它按固定间隔在岛屿台地上打网格，逐点向下打射线，
只保留落在台面高度上的格点，跳过随机地图所占的矩形，其余格点各摆一个地板单元
和一棵树。坡度大的岩壁与悬崖会被射线判定自动舍弃，所以填充范围正好贴着岛屿的
真实轮廓。

它必须放在 [RandomMap] 之后（`maze_path` 指向它）才能读到地图的实际范围。

## 关键参数

| 参数 | 值 | 说明 |
| --- | --- | --- |
| `Island` 缩放 | 20 | glb 原始直径约 5m，放大后台地直径约 104m |
| `Island` 位置 y | -12.96 | 把台面压到接近海平面的高度 |
| `RandomMap.cell_size` | 2m x 2m | 与 0.5m 半径的玩家胶囊匹配，保证通道可走 |
| `RandomMap.map_length` / `map_width` | 64m | 占满台地中央的方形区域 |
| `RandomMap.entrance_count` / `exit_count` | 8 / 2 | 八个边缘入口，两个中心出口 |
| 树木单元缩放 | 0.4 | 树高约 2.3m，比 2m 的格子略高，形成树墙 |
| `TreeWalls.spacing` | 3m | 唯一的疏密参数；略大于树冠（约 1.8m），既有森林感又留得出缝隙 |
| `TreeWalls.maze_margin` | 2m | 填充区与迷宫墙之间留的空隙 |

`jurassic-island.gd` 只做三件事：把随机地图与 `TreeWalls` 一起对齐到岛屿台面上、
在入口处生成玩家（并让它面朝地图中心）、打印一次生成摘要。

> 岛屿 glb 的顶面是一块平整的台地，本地高度 y = 0.71。`island_plateau_local_height`
> 记录这个值，随机地图与树墙都会跟着岛屿的位置与缩放对齐——调整岛屿缩放时不需要
> 手改它们的高度。

## 自检

```bash
/Applications/Godot.app/Contents/MacOS/Godot --headless \
  --script res://scenes-3d/jurassic-island/tests/verify_jurassic_island.gd
```

28 项检查全部通过，覆盖：三部分组件齐全（岛屿带网格与碰撞、海面足够大、
地图墙使用树木单元且带碰撞体）、地图与岛屿台面精确对齐、地图四角都不悬空
（射线打到的都是岛屿台面而不是海面）、玩家出生点可站立且不在墙里，
以及 `TreeWalls` 确实铺满了剩余部分（地板与树数量一致、没有一棵树长进随机地图
矩形里、抽查的填充格都踩在岛屿台面上）。