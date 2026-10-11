# RandomMap · 迷宫般风格随机地图

使用元胞自动机生成的迷宫般风格随机地图。
`components/` 下的独立场景组件，把 `random_map.tscn` 拖进任意 3D 场景即可使用。

## 地图特征

- **迷宫般**：通道细长、多分叉，空地约占 50%，通道宽 1~2 格。
- **较为稀疏**：墙与空地大致各半，不是密不透风的实心迷宫。
- **无大块结构**：不会出现 3x3 及以上的实心墙块，也不会出现 4x4 及以上的整块空地。
- **全图连通**：所有空地连成一片，任意入口都能走到中心出口。
- **可复现**：同一颗种子得到完全相同的墙壁与出入口。

## 组件入参

### 基本单元与尺寸

| 入参 | 默认值 | 说明 |
| --- | --- | --- |
| `wall_scene` 墙壁基本单元 | 1x1x1 盒子（带碰撞） | PackedScene，可替换为任意单元 |
| `floor_scene` 迷宫地板 | 1x1x1 盒子（带碰撞） | PackedScene |
| `cell_size` 单元长 x 宽 | 1m x 1m | |
| `wall_height` 墙壁高度 | 2m | |
| `floor_thickness` 地板厚度 | 0.2m | 地图是平的，地板由地面向下延伸此厚度 |
| `map_length` 地图总长度 | 32m | 格子数 = 总长 / 单元长（最少 5 格） |
| `map_width` 地图总宽度 | 32m | 格子数 = 总宽 / 单元宽（最少 5 格） |

> 地图以节点原点为中心，占地范围为 ±总长度/2 x ±总宽度/2。
> 也可用 `set_map_size_in_cells()` 直接按格子数指定大小。

### 出入口

| 入参 | 默认值 | 说明 |
| --- | --- | --- |
| `entrance_count` 入口数量 | 4 | 轮流分配到四条边 |
| `exit_count` 出口数量 | 1 | 全部在中心房间内，第一个在正中心 |

### 元胞自动机参数（`ca_config`）

| 入参 | 默认值 | 说明 |
| --- | --- | --- |
| `wall_fill_ratio` 初始墙壁密度 | 0.5 | 越大墙越多 |
| `smoothing_iterations` 平滑次数 | 3 | 越大结构越收敛 |
| `birth_limit` / `death_limit` 平滑阈值 | 3 / 6 | 决定墙更多还是通道更细 |
| `border_thickness` 外圈墙壁厚度 | 1 | 出入口会从外圈上打通 |
| `max_wall_thickness` 墙体最大厚度 | 1 | 1 = 最厚约 3 格；越大允许越厚的实心墙 |
| `max_open_room` 空房间最大边长 | 3 | 3 = 最大 3x3；更大的空地会被立柱拆分 |
| `split_wall_chunks` / `split_open_rooms` 大块打散 | 开 | 关闭后允许出现大块墙 / 大块空房（旧行为） |

## 约束与保证

- **地图平整**：所有格子地面高度都是 0，没有起伏，也没有断崖。
- **多个入口在矩形边缘**：轮流分布在四条边上，笔直向内接通；
  除入口外边缘完全封闭，没有其它缺口。
- **出口目标在中心**：中心保证存在一块房间，第一个出口永远是地图正中心。

## 使用

- **编辑器**：把 `random_map.tscn` 拖进场景，运行时自动生成。
- **代码**：`generate_with_seed(seed)` 固定种子生成、`generate()` 随机生成、
  `clear()` 清空；生成完成后发出 `map_generated` 信号，
  出入口 / 中心位置用 `get_entrance_positions()`、`get_goal_position()` 等查询。
- **演示**：`random_map_demo.tscn` 俯视演示，按 `R` 换随机种子重新生成。

## 自检

```bash
/Applications/Godot.app/Contents/MacOS/Godot --headless \
  --script res://components/map/random_map/tests/verify_random_map.gd
```

316 项检查全部通过，覆盖：全图连通、入口在边缘且边缘无其它缺口、
每个入口都能走到中心、出口在中心房间、地图平整（地面高度恒为 0）、
同种子可复现、不同尺寸、无 3x3 及以上实心墙块、无 4x4 及以上整块空地、
关闭大块打散后可复现旧行为等。

## 在主场景中的用法

侏罗纪岛主场景（`scenes-3d/jurassic-island/jurassic-island.tscn`）就是本组件的一个用法示例：

- `wall_scene` 指向 `tree-wall-unit.tscn`，于是地图里的每一面墙都是一棵树，
  整座岛因此长满树木；
- `cell_size` 设为 2m x 2m，配合 0.5m 半径的玩家胶囊，保证 1 格宽的通道可以走通；
- `map_length` / `map_width` = 44m，正好铺满岛屿顶部的平整台面。

> 注意：`tree-wall-unit.tscn` 自带一根树干碰撞体。自定义墙壁场景若要真正挡人，
> 必须像它一样在自己的场景里放好 `CollisionShape3D`——`RandomMap` 不会替
> `wall_scene` 生成碰撞。

## TreeWalls · 填充岛屿剩余部分

`random_map.tscn` 生成的是规整矩形，而岛屿是不规则形状，矩形之外会露出一圈
光秃秃的岩石。`tree-walls.tscn`（`class_name TreeWalls`）用来补上这部分：

- 以自身原点为基准，在 `fill_extent` 范围内按 `spacing` 打网格；
- 每个格点向下打射线，只保留落在"本节点所在高度"附近、且四角同样平整的地面
  （坡度大的岩壁与悬崖会被自动舍弃，所以填充范围贴着岛屿真实轮廓）；
- 跳过 `maze_path` 指向的随机地图实际占用的矩形（外扩 `maze_margin`）；
- 其余格点各摆一个 `floor_unit.tscn` + 一棵 `tree-wall-unit.tscn`。

| 入参 | 默认值 | 说明 |
| --- | --- | --- |
| `tree_scene` / `floor_scene` | 复用随机地图的树 / 地板单元 | PackedScene |
| `spacing` | 3m | 唯一的疏密参数，越小越密 |
| `fill_extent` | 120m x 120m | 以本节点为中心的铺设范围 |
| `maze_path` | 空 | 指向 `RandomMap`，自动读取它的实际矩形并跳过 |
| `maze_margin` | 1m | 跳过区域额外外扩的边距 |
| `ground_tolerance` | 0.1m | 允许的地面高度误差，超出即视为非台地 |
| `edge_check` | 开 | 检查格子四角，避免地板探出崖边 |
| `jitter` / `random_rotation` | 0.18 / 开 | 位置抖动与随机朝向，破掉网格感 |
| `fill_seed` | 0 | 固定种子可复现 |

> 本组件放在 `RandomMap` 之后、并以同一高度对齐即可工作；主场景
> `scenes-3d/jurassic-island/jurassic-island.tscn` 就是这么用的。
