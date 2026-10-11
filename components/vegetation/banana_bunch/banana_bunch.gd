@tool
class_name BananaBunch
extends Node3D
## 一把香蕉（bunch）：把 [member banana_count] 根香蕉在果轴上排成若干圈。
##
## 单根香蕉是独立资产（[code]assets/models/banana/banana.glb[/code]），本组件只负责
## [b]组装[/b]：一把几根、分几圈、张开多大、整体缩放，全部由导出参数控制。
## 改任何参数都会立即重建，不需要重新建模。
##
## 使用方式：
## [codeblock]
## var bunch: BananaBunch = $BananaBunch
## bunch.banana_count = 9
## bunch.rows = 3
## bunch.rebuild()
## [/codeblock]
##
## 局部坐标约定：果轴沿 -Y 向下，原点在果轴顶端（也就是与树相连的那一端）。
## 这样把它挂到树的任意位置、朝任意方向倾，都能得到"从树上垂下来"的效果。
##
## 香蕉自身资产的原点是蒂、向 -Y 生长并朝 +X 弯曲（见 banana.py 的朝向约定），
## 本组件用一组正交基把每根香蕉摆成"沿半径朝外、再往下垂"的姿态。

## 重建完成后发出，参数为本次实际生成的香蕉根数。
signal bunch_built(banana_count: int)

## 子节点容器名称。
const CONTAINER_BANANAS: StringName = &"Bananas"
const CONTAINER_RACHIS: StringName = &"Rachis"
const CONTAINER_NAMES: Array[StringName] = [CONTAINER_BANANAS, CONTAINER_RACHIS]

## 果轴（连接各根香蕉的主梗）颜色，与香蕉树假茎同一色系。
const RACHIS_COLOR: Color = Color(0.36, 0.40, 0.14)
## 蕉蕾（果串末端的紫红花苞）颜色。
const FLOWER_COLOR: Color = Color(0.55, 0.20, 0.35)

@export_group("基本单元")
## 单根香蕉场景（PackedScene）。默认使用独立的香蕉资产。
@export var banana_scene: PackedScene = preload("res://assets/models/banana/banana.glb")

@export_group("数量与排布")
## 一把香蕉有几根。这是"一把"的核心参数。
@export_range(1, 40, 1) var banana_count: int = 7:
	set(value):
		banana_count = maxi(value, 1)
		_on_param_changed()
## 分几圈绕果轴排布。圈数越多越"厚实"；1 圈就是一个平面上的手。
@export_range(1, 8, 1) var rows: int = 3:
	set(value):
		rows = maxi(value, 1)
		_on_param_changed()
## 起始方位角（度）。用来让同一棵树上的几把香蕉错开朝向。
@export_range(0.0, 360.0, 1.0) var azimuth_offset_degrees: float = 0.0:
	set(value):
		azimuth_offset_degrees = value
		_on_param_changed()
## 果轴总长（米）。香蕉沿这段长度一层层挂下去。
@export_range(0.05, 3.0, 0.01) var bunch_length: float = 0.42:
	set(value):
		bunch_length = maxf(value, 0.05)
		_on_param_changed()
## 每根香蕉相对果轴的张开角（度）。0 = 贴着果轴竖直下垂，90 = 完全水平朝外。
## 取 38 度左右：既张开成一把，又明显是往下垂的。
## 调到 60 度以上会变成"喷泉"，整把香蕉几乎横着飞出去，不像果串。
@export_range(0.0, 90.0, 1.0) var spread_degrees: float = 38.0:
	set(value):
		spread_degrees = clampf(value, 0.0, 90.0)
		_on_param_changed()
## 香蕉蒂距果轴中心线的距离（米）。
@export_range(0.0, 0.5, 0.005) var attach_radius: float = 0.055:
	set(value):
		attach_radius = maxf(value, 0.0)
		_on_param_changed()

@export_group("果轴与蕉蕾")
## 是否生成中间的果轴。关掉就只剩一把"悬空"的香蕉。
@export var show_rachis: bool = true:
	set(value):
		show_rachis = value
		_on_param_changed()
## 果轴超出最下一层香蕉的长度比例。>1 才会在末端露出一小截用来挂蕉蕾。
@export_range(0.5, 2.0, 0.01) var rachis_overhang: float = 1.18:
	set(value):
		rachis_overhang = maxf(value, 0.5)
		_on_param_changed()
## 是否在果轴末端挂一个紫红色的蕉蕾。
@export var show_flower: bool = true:
	set(value):
		show_flower = value
		_on_param_changed()
## 蕉蕾大小倍率。
@export_range(0.2, 3.0, 0.05) var flower_scale: float = 1.0:
	set(value):
		flower_scale = maxf(value, 0.2)
		_on_param_changed()

@export_group("变化")
## 整体缩放倍率。树上不同位置的果串常需要不同大小。
@export_range(0.1, 5.0, 0.05) var bunch_scale: float = 1.0:
	set(value):
		bunch_scale = maxf(value, 0.1)
		_on_param_changed()
## 每根香蕉的大小随机浮动比例，避免一整把看起来像复制粘贴。
@export_range(0.0, 0.5, 0.01) var scale_variation: float = 0.12:
	set(value):
		scale_variation = clampf(value, 0.0, 0.5)
		_on_param_changed()
## 随机种子。固定种子保证每次生成同一把香蕉。
@export var random_seed: int = 7:
	set(value):
		random_seed = value
		_on_param_changed()

@export_group("生成")
## 进入场景树时是否自动生成一次。
@export var auto_generate: bool = true

## 最近一次生成实际摆出的香蕉根数。
var _built_count: int = 0


func _ready() -> void:
	if auto_generate:
		rebuild()


## 按当前参数重建这一把香蕉。参数变化时会自动调用，也可手动调用。
func rebuild() -> void:
	if banana_scene == null:
		push_warning("BananaBunch: banana_scene 未设置，无法生成。")
		return
	_ensure_containers()
	_clear()
	_build_bananas()
	_build_rachis()
	# 整体缩放统一加在容器上：单根香蕉的随机抖动与"整把大小"是两个独立概念
	var scaled := Vector3.ONE * bunch_scale
	_container(CONTAINER_BANANAS).scale = scaled
	_container(CONTAINER_RACHIS).scale = scaled
	_built_count = banana_count
	bunch_built.emit(_built_count)


## 清空已生成的香蕉。
func clear() -> void:
	_clear()
	_built_count = 0


## 最近一次生成实际摆出的香蕉根数。
func get_banana_count() -> int:
	return _built_count


## 这一把香蕉在本地坐标下的包围盒，便于外部判断挂载位置是否合适。
func get_bunch_aabb() -> AABB:
	var result := AABB()
	var first := true
	for child in get_children():
		if not (child is Node3D):
			continue
		for grandchild in child.get_children():
			if grandchild is VisualInstance3D:
				var box: AABB = (grandchild as VisualInstance3D).get_aabb()
				box = (grandchild as Node3D).transform * box
				result = box if first else result.merge(box)
				first = false
	return result


## ---------------- 内部实现 ----------------

func _on_param_changed() -> void:
	if not is_inside_tree() or not is_node_ready() or not auto_generate:
		return
	rebuild()


func _ensure_containers() -> void:
	for container_name in CONTAINER_NAMES:
		if get_node_or_null(NodePath(container_name)) == null:
			var container := Node3D.new()
			container.name = container_name
			add_child(container)


func _container(container_name: StringName) -> Node3D:
	var node := get_node_or_null(NodePath(container_name)) as Node3D
	if node == null:
		_ensure_containers()
		node = get_node_or_null(NodePath(container_name)) as Node3D
	return node


func _clear() -> void:
	for container_name in CONTAINER_NAMES:
		var container := get_node_or_null(NodePath(container_name))
		if container == null:
			continue
		for child in container.get_children():
			container.remove_child(child)
			child.queue_free()


## 摆出这一把的全部香蕉。
##
## 排布规则：把 [member banana_count] 根香蕉按 [member rows] 圈均分，
## 第 tier 圈排在第 tier 圈的位置上（沿果轴往下走），同一圈里按方位角均分。
## 每根香蕉的姿态 = 沿半径朝外张开 [member spread_degrees] 度后再往下垂，
## 用一组正交基构造，避免多个欧拉角叠加时方向跑偏。
func _build_bananas() -> void:
	var container := _container(CONTAINER_BANANAS)
	if container == null:
		return
	var rng := RandomNumberGenerator.new()
	rng.seed = random_seed

	var per_row: int = ceili(float(banana_count) / float(rows))
	var spread: float = deg_to_rad(spread_degrees)
	var outward_amount: float = sin(spread)
	var downward_amount: float = cos(spread)

	for index in banana_count:
		var tier: int = index / per_row
		var slot: int = index % per_row
		if tier >= rows:
			tier = rows - 1

		# 沿果轴的高度（0 = 顶端，1 = 末端）与其在圈内的方位角
		var t: float = (float(tier) + 0.5) / float(rows)
		var azimuth: float = (
			TAU * (float(slot) + 0.37 * float(tier)) / float(per_row)
			+ deg_to_rad(azimuth_offset_degrees)
		)
		var outward := Vector3(sin(azimuth), 0.0, cos(azimuth))

		# 香蕉蒂的位置：果轴上该点 + 沿半径外推
		var attach := Vector3(0.0, -bunch_length * t, 0.0) + outward * attach_radius

		# 香蕉的悬挂方向：从"正下方"朝"半径外侧"偏转 spread 角
		var hang := (outward * outward_amount + Vector3.DOWN * downward_amount).normalized()
		var y_axis := -hang
		# 与半径垂直的切向，正好也垂直于悬挂方向，用作香蕉的弯曲方向
		var x_axis := Vector3(cos(azimuth), 0.0, -sin(azimuth)).normalized()
		# 香蕉资产向 +X 弯曲；这里翻一下符号，让香蕉尖端朝外上方翘起
		x_axis = -x_axis
		var z_axis := x_axis.cross(y_axis)
		var basis := Basis(x_axis, y_axis, z_axis)

		var instance := banana_scene.instantiate() as Node3D
		if instance == null:
			push_warning("BananaBunch: banana_scene 的根节点必须是 Node3D。")
			return
		instance.name = "Banana_%02d" % index
		var jitter: float = 1.0 + rng.randf_range(-scale_variation, scale_variation)
		instance.transform = Transform3D(basis.scaled(Vector3.ONE * jitter), attach)
		container.add_child(instance)


## 果轴与末端的蕉蕾。
func _build_rachis() -> void:
	var container := _container(CONTAINER_RACHIS)
	if container == null:
		return
	if not show_rachis and not show_flower:
		return
	var length: float = bunch_length * rachis_overhang

	if show_rachis:
		var mesh := CylinderMesh.new()
		mesh.top_radius = 0.075
		mesh.bottom_radius = 0.045
		mesh.height = length
		mesh.radial_segments = 5
		mesh.rings = 1
		var rachis := MeshInstance3D.new()
		rachis.name = "Stem"
		rachis.mesh = mesh
		rachis.material_override = _flat_material(RACHIS_COLOR)
		# CylinderMesh 沿 +Y，果轴要从原点往 -Y 长
		rachis.position = Vector3(0.0, -length * 0.5, 0.0)
		container.add_child(rachis)

	if show_flower:
		var radius: float = 0.13 * flower_scale
		var height: float = 0.34 * flower_scale
		var mesh := CylinderMesh.new()
		mesh.top_radius = 0.0
		mesh.bottom_radius = radius
		mesh.height = height
		mesh.radial_segments = 6
		var flower := MeshInstance3D.new()
		flower.name = "Flower"
		flower.mesh = mesh
		flower.material_override = _flat_material(FLOWER_COLOR)
		# 蕉蕾挂在果轴末端，尖端朝下
		flower.position = Vector3(0.0, -length - height * 0.35, 0.0)
		container.add_child(flower)


## 统一的 low-poly 硬边材质（关闭平滑，保持和模型一致的硬折面观感）。
func _flat_material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.9
	return material