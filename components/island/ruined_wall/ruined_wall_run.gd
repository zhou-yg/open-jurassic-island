@tool
extends Node3D
## 破败石墙 —— 可任意拼接加长的模块化组件。
##
## 模型：`assets/models/ruined-wall/low_poly_ruined_wall.glb`
##   单段 **2.90 × 0.99 × 2.25 m**（长 × 厚 × 高），原点在**单段中心**、地面 y=0。
##   墙厚 / 墙高 / 基座 / 压顶 / 砖模数在 Blender 端由 `assets/models/_shared/ruin_kit.py`
##   统一生成，和入口大门两翼的矮墙是**同一份几何**，所以怼在门上继续加长也是齐的。
##
## 为什么接缝看不出来（改模型前先读）：
##   1. 单段长 2.90 m，是砖模数 0.48 m 的整数倍附近，两端都不会留半块砖；
##   2. 两个端头都**强制满高**，压顶端片取固定满厚度 → 两段端面完全重合；
##   3. 基座与压顶在 X 方向不外扩 → 相邻两段正好对接成一条连续的基座。
##   Blender 端 `verify_seams()` 会数值校验这三点，不过就直接报错。
##
## 用法：
##   把本组件拖进场景，调 [member segments] 就会自动往 +X 方向拼 [code]segments[/code] 段；
##   想让墙朝别的方向，旋转父节点即可（墙是沿本地 +X 铺开的）。
##
## 想手工逐段摆也行：直接摆 [code]ruined_wall.tscn[/code]（单段场景），
## 相邻两段沿 X 间隔 **2.90 m** 就是无缝的。

const WALL_SCENE := preload("res://assets/models/ruined-wall/low_poly_ruined_wall.glb")

## 单段长度（米）。必须与 Blender 里的 WALL_LEN_M 一致，否则接缝会错位。
const SEGMENT_LENGTH := 2.90

## 拼几段。1 = 只有一段。
@export_range(1, 40, 1) var segments: int = 4:
	set(value):
		segments = maxi(1, value)
		if is_inside_tree():
			_rebuild()

## 相邻段交替镜像。镜像是绕单段自身中心翻的，两个端面本来就一样，
## 所以**不会**破坏接缝，但能让苔藓 / 塌口的位置错开，长墙看起来不重复。
@export var mirror_alternate: bool = true:
	set(value):
		mirror_alternate = value
		if is_inside_tree():
			_rebuild()

## 是否给墙挂三角面碰撞（玩家撞墙用）。
@export var build_collision: bool = true:
	set(value):
		build_collision = value
		if is_inside_tree():
			_rebuild()

var _pieces: Array[Node3D] = []


func _ready() -> void:
	_rebuild()


## 墙的总长度（米）。
func total_length() -> float:
	return segments * SEGMENT_LENGTH


func _rebuild() -> void:
	for piece in _pieces:
		if is_instance_valid(piece):
			piece.queue_free()
	_pieces.clear()

	for i in segments:
		# 单段原点在自身中心 → 第 i 段的中心 = (i + 0.5) * 段长，
		# 于是整段墙从本节点的原点（x=0）开始往 +X 长，锚点就是"墙的起点"。
		var piece := Node3D.new()
		piece.name = "Piece_%02d" % i
		piece.position = Vector3((i + 0.5) * SEGMENT_LENGTH, 0.0, 0.0)
		if mirror_alternate and i % 2 == 1:
			piece.scale = Vector3(-1.0, 1.0, 1.0)
		add_child(piece)
		_pieces.append(piece)

		var model := WALL_SCENE.instantiate()
		piece.add_child(model)

		if build_collision and not Engine.is_editor_hint():
			_add_collision(model)


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
