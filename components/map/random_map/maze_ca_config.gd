class_name MazeCAConfig
extends Resource
## 元胞自动机（Cellular Automata）生成参数。
##
## 这些参数决定迷宫墙壁的疏密与形态：
## - [member wall_fill_ratio] 控制初始随机墙壁密度；
## - [member birth_limit] / [member death_limit] 是 CA 的生长/存活规则（Moore 邻域）：
##   空地周围的墙壁邻居数达到 [member birth_limit] 时变成墙壁，
##   墙壁周围的墙壁邻居数低于 [member death_limit] 时被掏空；
## - [member split_big_blocks] 系列参数用于消除 CA 天然的"大块"倾向——
##   CA 收敛后会留下大块实心墙体和大块空房间，这两个后处理分别把它们
##   打散成走廊 / 拆分成小房间，让整张地图保持"迷宫般"的细碎质感。
##
## 说明：随机种子由 [RandomMap] 统一管理，不放在本资源里，
## 这样一张地图的墙壁与地势可以共用同一个种子。

## 初始随机填充时墙壁所占的比例。
@export_range(0.0, 1.0, 0.01, "suffix:%") var wall_fill_ratio: float = 0.5

## 元胞自动机平滑（演化）迭代次数，次数越多结构越规整。
@export_range(0, 20, 1) var smoothing_iterations: int = 3

## 生长阈值：空地周围的墙壁邻居数 >= 该值时，下一轮变成墙壁。
## 值越小墙壁越多、通道越窄。
@export_range(0, 8, 1) var birth_limit: int = 3

## 存活阈值：墙壁周围的墙壁邻居数 >= 该值时保持为墙壁，否则被掏空。
## 值越大越倾向于留下"细长的墙线"，地图会呈现迷宫般的通道结构。
@export_range(0, 8, 1) var death_limit: int = 6

## 地图外圈强制墙壁的厚度（单位：格）。出入口会在之后从外圈上被打通。
@export_range(0, 4, 1) var border_thickness: int = 1

## 是否用走廊把互不连通的空地区域连接起来，保证整张地图可以走通。
@export var connect_regions: bool = true

## 小于该格数的独立空地区域会被直接填成墙壁，避免产生零碎的小空间。
@export_range(0, 512, 1) var min_region_size: int = 6


## ---------------- 防大块后处理 ----------------

## 是否打散大块实心墙体：距离空地超过 [member max_wall_thickness] 步的
## "墙芯"会被开凿成走廊，避免出现大块实心墙。
@export var split_wall_chunks: bool = true

## 墙体允许的最大厚度（单位：格）。距离空地超过该步数的墙芯会被开凿。
## 1 表示墙最多 3 格厚（墙芯两侧各有 1 格空地）；设 0 可禁用该后处理。
@export_range(0, 8, 1) var max_wall_thickness: int = 1

## 是否拆分大块空房间：出现 (max_open_room+1)x(max_open_room+1) 的整块
## 空地时，在中心加一根柱子，避免出现大块空房间。
@export var split_open_rooms: bool = true

## 空房间允许的最大边长（单位：格）。超过该边长的整块空地会被拆分。
## 3 表示最多允许 3x3 的空房间，4x4 以上会被加柱子拆分。
@export_range(1, 16, 1) var max_open_room: int = 3
