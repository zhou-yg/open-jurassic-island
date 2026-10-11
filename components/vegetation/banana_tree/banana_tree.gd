@tool
class_name BananaTree
extends Node3D
## 香蕉树：在树的模型上挂若干把 [BananaBunch] 香蕉。
##
## 树模型本身（[code]assets/models/banana-tree-tall|short/low_poly_banana_tree.glb[/code]）
## [b]只含假茎与叶片，不含香蕉[/b]；果实由本组件按参数挂载，因此
## "一棵树挂几把、每把几根"都能在编辑器里直接调，不需要重新建模。
##
## 树的模型约定：原点在根部（y = 0），假茎沿 +Y 向上，整棵树高约
## [member tree_height] 米。组件按"高度比例"来分布果串，换高矮款式时
## 只需改 [member tree_height]，果串位置会自动跟着变。
##
## 使用方式：
## [codeblock]
## var tree: BananaTree = $BananaTree
## tree.bunch_count = 3          # 这棵树挂 3 把
## tree.bananas_per_bunch = 8    # 每把 8 根
## tree.rebuild()
## [/codeblock]
##
## 也可以直接换款式：[code]tree.tree_scene = load("res://.../short/....glb")[/code]

## 重建完成后发出，参数为 (果串把数, 香蕉总根数)。
signal tree_built(bunch_count: int, total_bananas: int)

## 子节点容器名称。
const CONTAINER_TREE: StringName = &"Tree"
const CONTAINER_BUNCHES: StringName = &"Bunches"
const CONTAINER_NAMES: Array[StringName] = [CONTAINER_TREE, CONTAINER_BUNCHES]

## 果串默认使用的一把香蕉场景。
const DEFAULT_BUNCH_SCENE: PackedScene = preload(
	"res://components/vegetation/banana_bunch/banana_bunch.tscn"
)
## 果柄 / 果轴的颜色，与假茎同一色系。
const RACHIS_COLOR: Color = Color(0.36, 0.40, 0.14)
## 默认的高款树模型。
const DEFAULT_TREE_SCENE: PackedScene = preload(
	"res://assets/models/banana-tree-tall/low_poly_banana_tree.glb"
)
## 矮款树模型，便于一键切换。
const SHORT_TREE_SCENE: PackedScene = preload(
	"res://assets/models/banana-tree-short/low_poly_banana_tree.glb"
)

@export_group("模型")
## 香蕉树模型（PackedScene）。默认高款；换成 [constant SHORT_TREE_SCENE] 即矮款。
@export var tree_scene: PackedScene = DEFAULT_TREE_SCENE:
	set(value):
		tree_scene = value
		_on_param_changed()
## 这把香蕉的场景（PackedScene），由本组件为每一把实例化。
@export var bunch_scene: PackedScene = DEFAULT_BUNCH_SCENE:
	set(value):
		bunch_scene = value
		_on_param_changed()
## 树的高度（米）。果串按高度比例挂载，所以换款式时改这里即可。
## 高款约 4.77，矮款约 2.66（与模型实际高度一致）。
@export_range(0.5, 20.0, 0.05) var tree_height: float = 4.77:
	set(value):
		tree_height = maxf(value, 0.5)
		_on_param_changed()

@export_group("果串数量")
## 这棵树挂几把香蕉。这是"一棵树有多少把"的核心参数。
@export_range(0, 16, 1) var bunch_count: int = 3:
	set(value):
		bunch_count = maxi(value, 0)
		_on_param_changed()
## 每一把香蕉有几根。会写入每一把的 [member BananaBunch.banana_count]。
@export_range(1, 40, 1) var bananas_per_bunch: int = 7:
	set(value):
		bananas_per_bunch = maxi(value, 1)
		_on_param_changed()
## 每一把香蕉分几圈。会写入每一把的 [member BananaBunch.rows]。
@export_range(1, 8, 1) var rows_per_bunch: int = 3:
	set(value):
		rows_per_bunch = maxi(value, 1)
		_on_param_changed()

@export_group("果串分布")
## 最上面一把香蕉挂在树高的百分之几处（0~1）。假茎顶端是 1.0。
@export_range(0.0, 1.0, 0.01) var first_bunch_height_ratio: float = 0.86:
	set(value):
		first_bunch_height_ratio = clampf(value, 0.0, 1.0)
		_on_param_changed()
## 相邻两把之间在高度上的间隔比例（0 = 全挤在同一高度）。
@export_range(0.0, 1.0, 0.01) var bunch_height_step_ratio: float = 0.13:
	set(value):
		bunch_height_step_ratio = clampf(value, 0.0, 1.0)
		_on_param_changed()
## 相邻两把之间的方位角间隔（度）。默认接近半圈，让果串分居两侧不重叠。
@export_range(0.0, 360.0, 1.0) var bunch_azimuth_step_degrees: float = 165.0:
	set(value):
		bunch_azimuth_step_degrees = value
		_on_param_changed()
## 每把香蕉的缩放。上面的把会略小于下面的把，用 [member bunch_scale_falloff] 控制。
@export_range(0.1, 5.0, 0.05) var bunch_scale: float = 1.0:
	set(value):
		bunch_scale = maxf(value, 0.1)
		_on_param_changed()
## 每往下一把缩小多少比例（0 = 都一样大）。
@export_range(0.0, 0.5, 0.01) var bunch_scale_falloff: float = 0.15:
	set(value):
		bunch_scale_falloff = clampf(value, 0.0, 0.5)
		_on_param_changed()
## 果串从假茎[b]中轴[/b]往外推的距离（米）。
## 要让整把香蕉都在假茎外面，这个值必须大于
## [code]假茎半径 + 果串自身的横向半径[/code]。
## 高款的假茎半径约 0.24~0.32 m、一把 7 根香蕉的横向半径约 0.30 m，
## 所以取 0.62 m。调小了靠内侧的香蕉会插进假茎（自检脚本 [11] 项会报出来）。
@export_range(0.0, 1.0, 0.01) var bunch_outset: float = 0.62:
	set(value):
		bunch_outset = maxf(value, 0.0)
		_on_param_changed()
## 果串的倾斜角（度）：0 = 垂直下垂，正值让果串朝外张开。
@export_range(0.0, 60.0, 1.0) var bunch_tilt_degrees: float = 0.0:
	set(value):
		bunch_tilt_degrees = clampf(value, 0.0, 60.0)
		_on_param_changed()
## 是否在假茎与果串之间补一段果柄，把两者连起来。
## 果串为了避免插进假茎会被推得比较远，没有果柄就会"悬空"飘在树干旁边。
@export var show_peduncle: bool = true:
	set(value):
		show_peduncle = value
		_on_param_changed()
## 果柄粗细（米）。
@export_range(0.01, 0.3, 0.005) var peduncle_radius: float = 0.055:
	set(value):
		peduncle_radius = maxf(value, 0.01)
		_on_param_changed()
## 果柄在假茎那一端往内插进多少比例（0 = 刚好贴表面，0.2 = 插进去 20% 半径）。
## 稍微插进去一点，避免果柄与假茎之间出现缝。
@export_range(0.0, 0.6, 0.01) var peduncle_inset: float = 0.18:
	set(value):
		peduncle_inset = clampf(value, 0.0, 0.6)
		_on_param_changed()

## 果串绕轴随机旋转的最大角度（度），让几把不显得整齐划一。
@export_range(0.0, 180.0, 1.0) var bunch_random_yaw_degrees: float = 14.0:
	set(value):
		bunch_random_yaw_degrees = clampf(value, 0.0, 180.0)
		_on_param_changed()

@export_group("生成")
## 随机种子。固定种子保证同一棵树每次长一样。
@export var random_seed: int = 7:
	set(value):
		random_seed = value
		_on_param_changed()
## 进入场景树时是否自动生成一次。
@export var auto_generate: bool = true

## 最近一次生成实际摆出的果串把数。
var _built_bunches: int = 0
## 最近一次生成实际摆出的香蕉总根数。
var _built_bananas: int = 0
## 当前实例化的树模型，用来读取假茎半径（果柄要从假茎表面长出来）。
var _tree_model: Node3D = null
## 假茎半径剖面缓存 {y: radius}，随树模型一起重建。
var _stalk_profile: Dictionary = {}


func _ready() -> void:
	if auto_generate:
		rebuild()


## 按当前参数重建整棵树（树模型 + 全部果串）。
func rebuild() -> void:
	_ensure_containers()
	_clear()
	_build_tree()
	_build_bunches()
	tree_built.emit(_built_bunches, _built_bananas)


## 只清空已生成的果串，保留树模型。
func clear_bunches() -> void:
	_clear_container(CONTAINER_BUNCHES)
	_built_bunches = 0
	_built_bananas = 0


## 当前挂着的果串节点（只读，便于外部查询每把的位置）。
func get_bunches() -> Array[BananaBunch]:
	var result: Array[BananaBunch] = []
	var container := get_node_or_null(NodePath(CONTAINER_BUNCHES))
	if container == null:
		return result
	for child in container.get_children():
		if child is BananaBunch:
			result.append(child as BananaBunch)
	return result


## 最近一次生成实际摆出的果串把数。
func get_bunch_count() -> int:
	return _built_bunches


## 最近一次生成实际摆出的香蕉总根数。
func get_total_banana_count() -> int:
	return _built_bananas


## 切换树款式（高 / 矮）并按对应高度自动更新 [member tree_height]。
func set_style(is_tall: bool) -> void:
	tree_scene = DEFAULT_TREE_SCENE if is_tall else SHORT_TREE_SCENE
	tree_height = 4.77 if is_tall else 2.66
	rebuild()


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
		_clear_container(container_name)
	_tree_model = null
	_stalk_profile = {}


func _clear_container(container_name: StringName) -> void:
	var container := get_node_or_null(NodePath(container_name))
	if container == null:
		return
	for child in container.get_children():
		container.remove_child(child)
		child.queue_free()


## 实例化树模型。模型原点已在根部，直接放在原点即可。
func _build_tree() -> void:
	var container := _container(CONTAINER_TREE)
	if container == null or tree_scene == null:
		if tree_scene == null:
			push_warning("BananaTree: tree_scene 未设置，只生成果串。")
		return
	var instance := tree_scene.instantiate() as Node3D
	if instance == null:
		push_warning("BananaTree: tree_scene 的根节点必须是 Node3D。")
		return
	instance.name = "TreeModel"
	container.add_child(instance)
	_tree_model = instance
	_stalk_profile = _build_stalk_profile(instance)


## 按参数在树上一把把地挂香蕉。
##
## 每把香蕉的局部坐标是"果轴沿 -Y 向下、原点在果轴顶端"，所以这里
## 只需要把原点摆到假茎表面的挂点上，再按方位角绕 Y 轴旋转、
## 按 [member bunch_tilt_degrees] 向外倾一点即可。
func _build_bunches() -> void:
	var container := _container(CONTAINER_BUNCHES)
	if container == null or bunch_scene == null:
		return
	_built_bunches = 0
	_built_bananas = 0
	if bunch_count <= 0:
		return

	var rng := RandomNumberGenerator.new()
	rng.seed = random_seed
	var tilt: float = deg_to_rad(bunch_tilt_degrees)

	for index in bunch_count:
		var instance := bunch_scene.instantiate() as BananaBunch
		if instance == null:
			push_warning("BananaBunch: bunch_scene 的根节点必须是 BananaBunch。")
			return

		# 高度：最上面一把在 first_bunch_height_ratio，往下每把再降一档
		var ratio: float = first_bunch_height_ratio - float(index) * bunch_height_step_ratio
		ratio = clampf(ratio, 0.05, 1.0)
		var height: float = tree_height * ratio

		# 方位角：相邻两把错开，再加一点随机
		var azimuth: float = (
			deg_to_rad(bunch_azimuth_step_degrees * float(index))
			+ deg_to_rad(rng.randf_range(-bunch_random_yaw_degrees, bunch_random_yaw_degrees))
		)
		var outward := Vector3(sin(azimuth), 0.0, cos(azimuth))

		instance.name = "Bunch_%02d" % index
		instance.position = Vector3(0.0, height, 0.0) + outward * bunch_outset

		var scale: float = bunch_scale * pow(1.0 - bunch_scale_falloff, float(index))
		instance.bunch_scale = maxf(scale, 0.05)
		instance.banana_count = bananas_per_bunch
		instance.rows = rows_per_bunch
		instance.azimuth_offset_degrees = rad_to_deg(azimuth)
		instance.random_seed = random_seed + index
		# 果轴本来朝下，这里绕"半径切向"转 tilt 让整把往外张开
		instance.rotation = Vector3(0.0, azimuth, 0.0)
		if not is_zero_approx(tilt):
			instance.rotate(Vector3(cos(azimuth), 0.0, -sin(azimuth)), tilt)

		container.add_child(instance)
		# 子节点 _ready 早于父节点，所以这里主动让它按上面的参数生成
		instance.rebuild()
		if show_peduncle:
			_add_peduncle(container, index, height, outward)
		_built_bunches += 1
		_built_bananas += instance.get_banana_count()


## 从假茎表面往外伸一小段果柄，把果串和树干连起来。
## 长度按"假茎实际半径"算，所以换高矮款式也自动贴合。
func _add_peduncle(container: Node3D, index: int, height: float, outward: Vector3) -> void:
	var stalk_radius: float = _stalk_radius_at(height)
	if stalk_radius <= 0.0:
		return
	var inner := Vector3(0.0, height, 0.0) + outward * (stalk_radius * (1.0 - peduncle_inset))
	var tip := Vector3(0.0, height, 0.0) + outward * bunch_outset
	var span := tip - inner
	var length: float = span.length()
	if length <= 0.001:
		return
	var mesh := CylinderMesh.new()
	mesh.top_radius = peduncle_radius * 0.85
	mesh.bottom_radius = peduncle_radius
	mesh.height = length
	mesh.radial_segments = 5
	mesh.rings = 1
	var node := MeshInstance3D.new()
	node.name = "Peduncle_%02d" % index
	node.mesh = mesh
	node.material_override = _flat_material(RACHIS_COLOR)
	node.position = inner + span * 0.5
	# CylinderMesh 沿 +Y，这里把它转到 span 的方向上
	var up := span.normalized()
	var reference := Vector3.UP if absf(up.dot(Vector3.UP)) < 0.99 else Vector3.RIGHT
	var right := reference.cross(up).normalized()
	var forward := right.cross(up)
	node.transform = Transform3D(Basis(right, up, forward), node.position)
	container.add_child(node)


## 扫描树模型里的假茎网格，得到"每个高度上的最大半径"剖面。
## 只认名字里含 stalk 的节点（建模脚本导出的假茎节点就叫 Stalk）。
func _build_stalk_profile(model: Node3D) -> Dictionary:
	var profile := {}
	for node in _collect_mesh_instances(model):
		var mesh_instance := node as MeshInstance3D
		if not mesh_instance.name.to_lower().contains("stalk"):
			continue
		var mesh: Mesh = mesh_instance.mesh
		if mesh == null:
			continue
		var to_local := model.global_transform.affine_inverse() * mesh_instance.global_transform
		for surface in mesh.get_surface_count():
			var arrays := mesh.surface_get_arrays(surface)
			var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			for v in verts:
				var local := to_local * v
				var radius := sqrt(local.x * local.x + local.z * local.z)
				var key := snappedf(local.y, 0.02)
				if not profile.has(key) or profile[key] < radius:
					profile[key] = radius
	return profile


## 某个高度上的假茎半径；超出假茎高度范围返回 0。
func _stalk_radius_at(y: float) -> float:
	if _stalk_profile.is_empty():
		return 0.0
	var keys := _stalk_profile.keys()
	keys.sort()
	if y < float(keys[0]) - 0.05 or y > float(keys[keys.size() - 1]) + 0.05:
		return 0.0
	var best_key: float = keys[0]
	for key in keys:
		if absf(float(key) - y) < absf(best_key - y):
			best_key = key
	return _stalk_profile[best_key]


## 收集一个节点下所有 MeshInstance3D。
func _collect_mesh_instances(node: Node) -> Array[Node]:
	var result: Array[Node] = []
	if node is MeshInstance3D:
		result.append(node)
	for child in node.get_children():
		result.append_array(_collect_mesh_instances(child))
	return result


## 统一的 low-poly 硬边材质。
func _flat_material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.9
	return material