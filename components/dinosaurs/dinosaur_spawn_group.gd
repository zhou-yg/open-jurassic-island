class_name DinosaurSpawnGroup
extends Resource
## 恐龙的一处**聚居地**（出生点组）。
##
## 组件入参支持**多个组**：每组 = 一个中心 + 一个半径，组件把恐龙按权重
## 分配到各组，组内再按间距摊开。恐龙出生之后就在自己这块地里巡逻
## （领地半径由体型决定，见 [DinosaurPatrol]）。
##
## 组的中心写的是**世界坐标**。组件落点时会用射线把它贴到地面上，
## 所以中心给个大概位置就行（不用自己算地表高度）。

## 显示名（调试 / 统计用）。
@export var display_name: String = ""
## 聚居地中心（世界坐标）。
@export var center: Vector3 = Vector3.ZERO
## 聚居地半径（米）：恐龙在这个圆里随机落点。
@export var radius: float = 160.0
## 分到多少只恐龙（相对权重）。0 = 这一组不放恐龙。
@export var weight: float = 1.0
## 组内恐龙至少隔多远（米）。0 = 用组件的默认值。
@export var min_spacing: float = 0.0
