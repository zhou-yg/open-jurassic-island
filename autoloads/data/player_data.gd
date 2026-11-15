extends Node

## 玩家的出生点（**3D 世界坐标**，单位：米）。
##
## 默认值跟主场景 `scenes-3d/jurassic-island/jurassic-island.tscn` 里
## `Player` 节点的初始位置一致（`(0, 30, 78)`，落在出生点附近的地面上）。
var spawn_location : Vector3 = Vector3(0.0, 30.0, 78.0)


func serialize(file : FileAccess) -> void:
	file.store_32(spawn_location.x)
	file.store_32(spawn_location.y)
	file.store_32(spawn_location.z)


func deserialize(file : FileAccess) -> void:
	spawn_location.x = file.get_32()
	spawn_location.y = file.get_32()
	spawn_location.z = file.get_32()
