class_name TerrainHeightConfig
extends Resource
## 地势（高度场）参数。
##
## 高度场由分形噪声生成，再经过平滑与 [member max_step_height] 约束。
## [member max_step_height] 是"地势要有连续高度差"的硬约束：
## 任意两个相邻格子的高差都不会超过该值，因此地面上不会出现断崖，
## 只会出现连续的缓坡/台阶。
##
## 说明：随机种子由 [RandomMap] 统一管理，不放在本资源里。

## 整张地图的相对高差（米）：最高点与最低点的最大差值。
@export_range(0.0, 100.0, 0.1) var height_variation: float = 4.0

## 噪声频率：值越大起伏越密集（以"格"为单位，1 格 = 1 个墙壁单元）。
@export_range(0.001, 1.0, 0.001) var noise_frequency: float = 0.06

## 分形噪声层数，层数越多细节越丰富。
@export_range(1, 6, 1) var noise_octaves: int = 3

## 生成后额外平滑的次数，让坡面更自然。
@export_range(0, 8, 1) var smoothing_passes: int = 1

## 相邻格子之间允许的最大高差（米）。这是连续性约束，必须 > 0。
@export_range(0.05, 4.0, 0.05) var max_step_height: float = 0.5

## 出入口与中心目标周围压平的半径（单位：格），保证进出与目标区域平缓。
@export_range(0, 8, 1) var anchor_flat_radius: int = 1

## 是否把最低点归零，使整张地图坐落在 y = 0 之上。
@export var normalize_to_zero: bool = true
