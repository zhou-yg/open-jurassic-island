@tool
extends Node3D
## 单段破败石墙 —— 手工逐段拼接时用这个（想自动拼多段用 ruined_wall_run.tscn）。
##
## 模型 `assets/models/ruined-wall/low_poly_ruined_wall.glb`：**2.90 × 0.99 × 2.25 m**，
## 原点在单段中心、地面 y=0。相邻两段沿本地 X 间隔 **2.90 m** 即为无缝拼接；
## 两个端面在 Blender 端已数值校验过完全重合（`verify_seams()`），
## 所以也可以交替做 x 轴镜像来错开苔藓 / 塌口，接缝一样是齐的。

## 挂三角面碰撞。
@export var build_collision: bool = true


func _ready() -> void:
	if Engine.is_editor_hint() or not build_collision:
		return
	_add_collision(self)


func _add_collision(root: Node) -> void:
	for child in root.get_children():
		if child is MeshInstance3D and child.mesh != null:
			var body := StaticBody3D.new()
			body.name = "Body"
			var col := CollisionShape3D.new()
			col.name = "Shape"
			col.shape = child.mesh.create_trimesh_shape()
			body.add_child(col)
			child.add_child(body)
		_add_collision(child)
