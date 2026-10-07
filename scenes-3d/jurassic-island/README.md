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

此外还有 `Sun`（平行光）、`WorldEnvironment`（天空 / 雾）、`Player`（第一人称玩家）
和 `HUDLayer/TopBar`（战争迷雾风格的顶部资源 / 时间条）。

## 关键参数

| 参数 | 值 | 说明 |
| --- | --- | --- |
| `Island` 缩放 | 14 | glb 原始直径约 5m，放大后岛屿直径约 70m |
| `RandomMap.cell_size` | 2m x 2m | 与 0.5m 半径的玩家胶囊匹配，保证通道可走 |
| `RandomMap.map_length` / `map_width` | 44m | 铺满岛屿顶部的平整台面 |
| `RandomMap.entrance_count` / `exit_count` | 8 / 2 | 八个边缘入口，两个中心出口 |
| 树木单元缩放 | 0.4 | 树高约 2.3m，比 2m 的格子略高，形成树墙 |

`jurassic-island.gd` 只做三件事：把随机地图对齐到岛屿台面上、在入口处生成玩家
（并让它面朝地图中心）、打印一次生成摘要。

> 岛屿 glb 的顶面是一块平整整的台地，本地高度 y = 0.71。`island_plateau_local_height`
> 记录这个值，随机地图会自动跟着岛屿的位置与缩放对齐——调整岛屿缩放时不需要手改地图高度。

## 自检

```bash
/Applications/Godot.app/Contents/MacOS/Godot --headless \
  --script res://scenes-3d/jurassic-island/tests/verify_jurassic_island.gd
```

20 项检查全部通过，覆盖：三部分组件齐全（岛屿带网格与碰撞、海面足够大、
地图墙使用树木单元且带碰撞体）、地图与岛屿台面精确对齐、地图四角都不悬空
（射线打到的都是岛屿台面而不是海面）、玩家出生点可站立且不在墙里。