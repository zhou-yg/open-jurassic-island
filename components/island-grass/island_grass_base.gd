extends Node3D
## **岛屿植被地面**组件 —— 底板 + 铺满的草 + 轻微摇曳。
##
## 底板（`Ground`）就是 `assets/models/grass/island_grass_base.glb`：
## 上表面**和岛屿台面完全同形**（轮廓直接抄自
## `assets/models/island/sky-island-basic.glb` 里那块 `-col` 平顶岩盘），
## 所以一根草都不会长到岛外 —— 这正是 2026-11 删掉旧草毯的原因
## （旧草毯比岩台大一圈，外圈那圈树和石头有一半悬在岛外）。
##
## ## 尺寸：宽度可设，长度按固定比例
##
## 岛面是个不规则的圆盘，不是矩形。组件把它的**长宽比固定**成岛面自己的比例：
##
## ```
## 长度 = 宽度 × 1.03645      （64.688 m / 62.413 m，抄自岛面轮廓）
## ```
##
## 改 `width` 时整块底板等比缩放，轮廓形状一点不变（和岛面同形这件事永远成立）。
## 底板自带尺寸（= 组件岛 62 m 的那一套）：
##
## | | 值 |
## | --- | --- |
## | 底板宽（X） | **62.413 m** |
## | 底板长（Z） | **64.688 m** |
## | 长宽比 | **1.03645**（固定） |
## | 岛面半径 | 29.5 ~ 34.7 m |
## | 岛面面积 | ≈ 3000 m² |
##
## ## 草
##
## 两种草（`grass_tuft_lod` 尖叶草墩 / `grass_clump_lod` 圆润灌木草），
## 都是**减面版**（48 / 60 三角面，原版 266 / 260）。
## 减面版还把**根摊开了 1.55 倍** —— 叶片少了以后全挤在一小圈里互相叠着，
## 摊开之后同样的实例数能盖住大一倍的地面（默认参数下**地面完全被盖住，不露底板**）。
##
## 摆放规则：**不混个体，各自聚成一团，团与团互相交错**——
## 草地按网格铺开（每格一团，团内几株挤在一起），
## 再按 **3×3 团为一片**分配类型，片与片棋盘式交错 + 每片 25% 随机翻转，
## 于是两种草各自成团、两团的边界犬牙交错，不会出现"这一片全是 A、那片全是 B"的硬边。
##
## ## 摇曳
##
## 草用 `components/island-grass/grass_sway.gdshader`：顶点按高度平方往风向下压，
## 每株草有自己的相位（`INSTANCE_CUSTOM`），所以是一片一阵地晃。
##
## 用法：在场景里实例化 `components/island-grass/island-grass-base.tscn`，
## 然后改 `width`（地面宽）和 `clump_density`（草多密）就行。

const SWAY_SHADER: Shader = preload("res://components/island-grass/grass_sway.gdshader")

## 底板自带的宽度（米）—— 和组件岛（62 m）同一尺度
const BASE_WIDTH := 62.413
## 底板自带的长度（米）
const BASE_LENGTH := 64.688
## **固定比例**：长度 = 宽度 × 这个数（抄自岛面轮廓本身，不给改）
const ISLAND_RATIO := BASE_LENGTH / BASE_WIDTH      # 1.03645

@export_group("地面")
## 地面矩形宽（X 方向，米）。**长度 = 宽度 × 1.03645**（固定比例）。
@export_range(1.0, 4000.0, 0.01) var width: float = BASE_WIDTH:
	set(value):
		width = maxf(1.0, value)
		_refresh_scale()
## 地面顶面相对岛面抬高多少（米）—— 避免和岩台面 z-fighting
@export_range(0.0, 0.5, 0.005) var base_lift: float = 0.03:
	set(value):
		base_lift = maxf(0.0, value)
		_refresh_scale()

@export_group("草")
## 每平方米撒几团草。
## **默认值是"刚好铺满"**：减面草的根摊开了 1.55 倍，一团占地 ≈0.45 m²，
## 2 团/m² 就能盖住地面（再稀就露底板了）。
@export_range(0.05, 20.0, 0.05) var clump_density: float = 2.0:
	set(value):
		clump_density = maxf(0.01, value)
		_refresh_grass()
## 每团几株草
@export_range(1, 24, 1) var blades_per_clump: int = 10:
	set(value):
		blades_per_clump = maxi(1, value)
		_refresh_grass()
## 草团半径（米）—— 团内几株草散开的范围（小 = 一簇挤在一起）
@export_range(0.05, 3.0, 0.05) var clump_radius: float = 0.45:
	set(value):
		clump_radius = maxf(0.02, value)
		_refresh_grass()
## **几团草合成一片同类型的区域**（以"团"为单位）。
## 1 = 每一团都是一种类型（两种草逐团交错）；
## 3 = 每 3×3 团是同一种类型，两种草各自成片、片与片犬牙交错。
@export_range(1, 12, 1) var patch_ratio: int = 3:
	set(value):
		patch_ratio = maxi(1, value)
		_refresh_grass()
## 草的随机缩放下限（1 = 模型原尺寸）
@export_range(0.2, 3.0, 0.05) var grass_scale_min: float = 0.8:
	set(value):
		grass_scale_min = maxf(0.05, value)
		_refresh_grass()
## 草的随机缩放上限
@export_range(0.2, 3.0, 0.05) var grass_scale_max: float = 1.35:
	set(value):
		grass_scale_max = maxf(grass_scale_min, value)
		_refresh_grass()
## 随机种子（同一个种子 → 同一片草地）
@export var seed: int = 20260915:
	set(value):
		seed = value
		_refresh_grass()
## 草株数量上限（保险丝）—— 地面特别大时自动降密度，
## 免得一次生成几十万株把游戏卡住（会打警告说明降到了多少）。
## 默认 62 m 的岛要 6 万株，所以保险丝放在 12 万（够铺满还有余量）。
@export_range(1000, 500000, 1000) var max_instances: int = 120000
## 不种草的矩形区域（组件局部 XZ 坐标）—— 比如山体脚下
@export var exclude_areas: Array[Rect2] = []

@export_group("摇曳")
## 顶端最大摆动（米）—— 0.03~0.08 属于"轻微"
@export_range(0.0, 0.5, 0.005) var sway_strength: float = 0.06:
	set(value):
		sway_strength = maxf(0.0, value)
		_refresh_material()
## 摆动速度（弧度/秒）
@export_range(0.0, 6.0, 0.05) var sway_speed: float = 1.2:
	set(value):
		sway_speed = maxf(0.0, value)
		_refresh_material()
## 世界风向（XZ 平面）
@export var wind_direction: Vector2 = Vector2(1.0, 0.35):
	set(value):
		wind_direction = value
		_refresh_material()
## 风力总开关
@export_range(0.0, 3.0, 0.05) var wind_strength: float = 1.0:
	set(value):
		wind_strength = maxf(0.0, value)
		_refresh_material()

@onready var _ground_root: Node3D = $Ground
@onready var _ground: MeshInstance3D = _find_mesh(_ground_root)
@onready var _grass_root: Node3D = $Grass
@onready var _tuft_root: Node3D = $TuftSource
@onready var _tuft_source: MeshInstance3D = _find_mesh(_tuft_root)
@onready var _clump_root: Node3D = $ClumpSource
@onready var _clump_source: MeshInstance3D = _find_mesh(_clump_root)
@onready var _tuft_mmi: MultiMeshInstance3D = $Grass/GrassTuft
@onready var _clump_mmi: MultiMeshInstance3D = $Grass/GrassClump


## GLB 导入后是「一个 Node3D 根 + 一个 MeshInstance3D 子节点」，
## 所以网格要从子节点里找。
static func _find_mesh(root: Node) -> MeshInstance3D:
	if root == null:
		return null
	if root is MeshInstance3D:
		return root as MeshInstance3D
	for child in root.get_children():
		var found := _find_mesh(child)
		if found != null:
			return found
	return null

## 底板轮廓（组件局部 XZ，Godot 坐标）
var _outline: PackedVector2Array = PackedVector2Array()
## 草的统计，最后一次生成的结果
var _stats := {"tuft": 0, "clump": 0, "clumps": 0}


func _ready() -> void:
	_refresh_scale()
	_build_grass()


# ======================================================================
#  底板
# ======================================================================
## 底板缩放：等比（长宽比固定），所以轮廓形状永远和岛面同形。
func _refresh_scale() -> void:
	if not is_instance_valid(_ground):
		return
	var s := width / BASE_WIDTH
	_ground.scale = Vector3(s, 1.0, s)
	_ground.position.y = base_lift
	# 草站在底板顶面上（不是岩台上），所以整棵草的根要抬到同一高度
	if is_instance_valid(_grass_root):
		_grass_root.position.y = base_lift
	if is_inside_tree() and _outline.size() > 0:
		_build_grass()


## 地面长边（米）—— 宽度 × 固定比例
func get_length() -> float:
	return width * ISLAND_RATIO


# ======================================================================
#  草
# ======================================================================
func _refresh_grass() -> void:
	if is_inside_tree():
		_build_grass()


func _refresh_material() -> void:
	for mmi in [_tuft_mmi, _clump_mmi]:
		if is_instance_valid(mmi) and mmi.material_override is ShaderMaterial:
			_apply_sway_params(mmi.material_override as ShaderMaterial)


func _build_grass() -> void:
	if not is_inside_tree():
		return
	if not is_instance_valid(_ground):
		return
	var ground_mesh := _ground.mesh
	if ground_mesh == null:
		return
	_outline = _extract_top_ring(ground_mesh)
	if _outline.size() < 3:
		push_warning("[IslandGrassBase] 底板轮廓提取失败，草没有生成")
		return

	# 底板缩放后的轮廓（草摆在组件局部空间 = 缩放后的世界空间）
	var s := width / BASE_WIDTH
	var poly := PackedVector2Array()
	for p in _outline:
		poly.append(p * s)

	var rng := RandomNumberGenerator.new()
	rng.seed = seed

	var tuft_xforms: Array[Transform3D] = []
	var clump_xforms: Array[Transform3D] = []
	var tuft_data: Array[Color] = []
	var clump_data: Array[Color] = []

	# --- 按网格铺开：相邻格子强制换类型 → 两团互相交错 ---
	var cell := 1.0 / sqrt(clump_density)
	# 保险丝：地面特别大时自动降密度（否则一次生成几十万株会卡住）
	var area := _polygon_area(poly)
	var est := area / (cell * cell) * float(blades_per_clump)
	if est > float(max_instances):
		var k := float(max_instances) / est
		cell = cell / sqrt(k)
		push_warning("[IslandGrassBase] 草量上限 %d：密度降到 %.2f 团/m²"
			% [max_instances, 1.0 / (cell * cell)])
	var min_x := poly[0].x
	var max_x := poly[0].x
	var min_z := poly[0].y
	var max_z := poly[0].y
	for p in poly:
		min_x = minf(min_x, p.x)
		max_x = maxf(max_x, p.x)
		min_z = minf(min_z, p.y)
		max_z = maxf(max_z, p.y)

	var gx0 := int(floor(min_x / cell))
	var gx1 := int(ceil(max_x / cell))
	var gz0 := int(floor(min_z / cell))
	var gz1 := int(ceil(max_z / cell))

	var clumps := 0
	for gz in range(gz0, gz1 + 1):
		for gx in range(gx0, gx1 + 1):
			# 格子中心 + 抖动（抖动不许跑出格子，类型区域才不会糊）
			var cx := (float(gx) + 0.5) * cell + rng.randf_range(-0.34, 0.34) * cell
			var cz := (float(gz) + 0.5) * cell + rng.randf_range(-0.34, 0.34) * cell
			if not _point_in_polygon(Vector2(cx, cz), poly):
				continue
			if _is_excluded(cx, cz):
				continue

			# 类型：**按"片"分配**，片与片棋盘式交错、片内全是同一种草
			# → 两种草各自聚成一团团，团的边界犬牙交错，不会个体混杂
			var patch_x := int(floor(float(gx) / float(patch_ratio)))
			var patch_z := int(floor(float(gz) / float(patch_ratio)))
			var is_clump := ((patch_x + patch_z) % 2) == 0
			if _cell_flip(patch_x, patch_z):
				is_clump = not is_clump

			clumps += 1
			for k in blades_per_clump:
				var px := cx + rng.randf_range(-clump_radius, clump_radius)
				var pz := cz + rng.randf_range(-clump_radius, clump_radius)
				if not _point_in_polygon(Vector2(px, pz), poly):
					continue
				if _is_excluded(px, pz):
					continue

				var rot := rng.randf_range(0.0, TAU)
				var sc := rng.randf_range(grass_scale_min, grass_scale_max)
				var xform := Transform3D(Basis(Vector3.UP, rot).scaled(Vector3(sc, sc, sc)),
					Vector3(px, 0.0, pz))
				# INSTANCE_CUSTOM：相位 + 实例转角（shader 用它把世界风向转回本地）
				var phase := rng.randf_range(0.0, TAU)
				var data := Color(phase, cos(rot), sin(rot), 0.0)
				if is_clump:
					clump_xforms.append(xform)
					clump_data.append(data)
				else:
					tuft_xforms.append(xform)
					tuft_data.append(data)

	_fill_multimesh(_tuft_mmi, _tuft_source.mesh, tuft_xforms, tuft_data, 0.76)
	_fill_multimesh(_clump_mmi, _clump_source.mesh, clump_xforms, clump_data, 0.40)

	_stats = {"tuft": tuft_xforms.size(), "clump": clump_xforms.size(), "clumps": clumps}
	print("[IslandGrassBase] 宽 %.2f m × 长 %.2f m（比例 %.5f）｜ 草团 %d，草丛 %d，草簇 %d"
		% [width, get_length(), ISLAND_RATIO, clumps,
			tuft_xforms.size(), clump_xforms.size()])


func _fill_multimesh(mmi: MultiMeshInstance3D, mesh: Mesh,
		xforms: Array[Transform3D], data: Array[Color], plant_height: float) -> void:
	if not is_instance_valid(mmi):
		return
	if mesh == null or xforms.is_empty():
		mmi.multimesh = null
		return
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = mesh
	mm.instance_count = xforms.size()
	for i in xforms.size():
		mm.set_instance_transform(i, xforms[i])
		mm.set_instance_custom_data(i, data[i])
	mmi.multimesh = mm
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	var mat := ShaderMaterial.new()
	mat.shader = SWAY_SHADER
	mat.set_shader_parameter("plant_height", plant_height)
	_apply_sway_params(mat)
	mmi.material_override = mat


func _apply_sway_params(mat: ShaderMaterial) -> void:
	mat.set_shader_parameter("sway_strength", sway_strength)
	mat.set_shader_parameter("sway_speed", sway_speed)
	mat.set_shader_parameter("wind_direction", wind_direction)
	mat.set_shader_parameter("wind_strength", wind_strength)


## 每个格子要不要把类型翻过来（固定哈希 → 同一个 seed 同一片草地）
func _cell_flip(gx: int, gz: int) -> bool:
	var h := (gx * 73856093) ^ (gz * 19349663) ^ (seed * 83492791)
	h = (h ^ (h >> 13)) & 0x7FFFFFFF
	return float(h % 1000) < 250.0


func _is_excluded(x: float, z: float) -> bool:
	for r in exclude_areas:
		if r.has_point(Vector2(x, z)):
			return true
	return false


# ======================================================================
#  轮廓提取（底板顶面的一圈点）
# ======================================================================
## 从底板网格里抠出**顶面那一圈边界点**（顺时针/逆时针都无所谓）。
##
## 底板是个封闭的板子（上下都有面），所以不能靠"用了几次的边 = 边界"来找环：
## 顶面那一圈边同时被顶面和侧壁用，各一次。所以改成
## **只取顶面（y = 最高）的三角形**，在它们内部再数边。
##
## 顶点在导入后是按面拆开的（同一个位置有好多份），所以先按位置焊接。
static func _extract_top_ring(mesh: Mesh) -> PackedVector2Array:
	var arrays := mesh.surface_get_arrays(0)
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
	if verts.is_empty():
		return PackedVector2Array()
	if idx.is_empty():
		idx = PackedInt32Array()
		idx.resize(verts.size())
		for i in verts.size():
			idx[i] = i

	# 顶面高度（Godot 是 Y 向上，岛面在 **XZ 平面**上）
	var top_y := -INF
	for v in verts:
		top_y = maxf(top_y, v.y)

	# 按位置焊接（XZ 平面上的位置）
	var weld := {}
	var wpos: Array[Vector2] = []
	var remap := PackedInt32Array()
	remap.resize(verts.size())
	for i in verts.size():
		var key := Vector2i(int(round(verts[i].x * 1000.0)), int(round(verts[i].z * 1000.0)))
		if not weld.has(key):
			weld[key] = wpos.size()
			wpos.append(Vector2(verts[i].x, verts[i].z))
		remap[i] = weld[key]

	# 只留顶面三角形
	var top_tris: Array[Vector3i] = []
	for t in range(0, idx.size() - 2, 3):
		var a := idx[t]
		var b := idx[t + 1]
		var c := idx[t + 2]
		if verts[a].y >= top_y - 0.001 and verts[b].y >= top_y - 0.001 \
				and verts[c].y >= top_y - 0.001:
			top_tris.append(Vector3i(remap[a], remap[b], remap[c]))
	if top_tris.is_empty():
		return PackedVector2Array()

	# 边计数（只数顶面内部的边）
	var edge_count := {}
	for tri in top_tris:
		for e in 3:
			var a: int = tri[e]
			var b: int = tri[(e + 1) % 3]
			var key := Vector2i(mini(a, b), maxi(a, b))
			edge_count[key] = int(edge_count.get(key, 0)) + 1

	# 邻接表（只留用了一次的边 = 边界）
	var adj := {}
	for key in edge_count:
		if int(edge_count[key]) != 1:
			continue
		var a: int = key.x
		var b: int = key.y
		if not adj.has(a):
			adj[a] = PackedInt32Array()
		if not adj.has(b):
			adj[b] = PackedInt32Array()
		adj[a].append(b)
		adj[b].append(a)
	if adj.is_empty():
		return PackedVector2Array()

	# 顺着走一圈
	var start := 0
	for k in adj.keys():
		start = k
		break
	var ring := PackedVector2Array()
	var visited := {}
	var prev := -1
	var cur := start
	while cur != -1 and not visited.has(cur):
		visited[cur] = true
		ring.append(wpos[cur])
		var nxt := -1
		for cand in adj[cur]:
			if cand != prev:
				nxt = cand
				break
		prev = cur
		cur = nxt
	return ring


## 射线法：点在多边形内吗
static func _point_in_polygon(p: Vector2, poly: PackedVector2Array) -> bool:
	var inside := false
	var n := poly.size()
	var j := n - 1
	for i in n:
		var a := poly[i]
		var b := poly[j]
		if (a.y > p.y) != (b.y > p.y):
			var x := (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x
			if p.x < x:
				inside = not inside
		j = i
	return inside


## 多边形面积（鞋带公式），用来估草量
static func _polygon_area(poly: PackedVector2Array) -> float:
	var a := 0.0
	var n := poly.size()
	var j := n - 1
	for i in n:
		a += poly[i].x * poly[j].y - poly[j].x * poly[i].y
		j = i
	return absf(a) * 0.5
