extends Node
## **世界尺度**（2000 m 岛）的香蕉树林 + 恐龙烘焙脚本。
##
## ## 为什么另起一份
##
## `components/island/vegetation/bake_vegetation.gd` 烘的是 **62 m 的组件岛**：
## 树高 2.66 / 4.77 m，恐龙体长 2.2~17 m，10 只恐龙在 62 m 的岛上转圈。
##
## 主场景 `scenes-3d/jurassic-island/jurassic-island.tscn` 用的是**同一个岛组件**，
## 但水平放大 **32.258 倍**、竖直放大 **20.968 倍**（62 m → 2000 m），
## 玩家、园区大门、本地草石全是 **1:1 米制**。
##
## 所以组件里那份烘焙**不能**直接用：
## - 树乘 32 倍会变成 150 m 高的巨树；
## - 恐龙乘 32 倍会变成 350 m 长；
## - 62 m 尺度上的 10 只恐龙放在 2000 m 的岛上，一辈子遇不到一只。
##
## 这份脚本按 **1:1 米制**重新烘一套：树还是 2.66 / 4.77 m（放大一倍当"大树"，
## 因为 2 km 的岛上 5 m 的树看着像灌木），恐龙还是 2.2~17 m，
## 但数量、分布、巡逻领 地全都按大世界来。
##
## ## 尺度对照
##
## | | 组件岛（62 m） | 世界岛（2000 m） |
## | --- | --- | --- |
## | 岛半径 | ~31 m | ~1000 m |
## | 山高 | 17.8 m | 372 m |
## | 树 | 220 棵 | 1200 棵（成片的林子） |
## | 恐龙 | 10 只 | 24 只（各有领地） |
##
## ## 用法
##
## **必须带真实渲染器，不要加 `--headless`** —— headless 的 dummy 渲染器
## 会把 MultiMesh 的实例变换全丢掉，烘出来是一堆零矩阵：
## [codeblock]
## godot --path . --script res://scenes-3d/jurassic-island/bake_world_vegetation.gd
## [/codeblock]
##
## 产出（都在 `scenes-3d/jurassic-island/`）：
## - `world_vegetation.json` —— **源**（树逐实例变换）
## - `world_vegetation.tscn` —— 烘出来的树（2 个 MultiMesh）
## - `world_vegetation_*_trees.res` —— MultiMesh 二进制（构建产物）

# --- 岛的世界变换 -------------------------------------------------------------
## 岛整体缩小的系数（2026-11）：**面积减半** → 线性 × 1/√2。
## 2000 m 的岛变成约 1414 m。
##
## 主场景 `jurassic-island.tscn` 的 `Island` 节点必须**完全一致**。
const ISLAND_SHRINK := 0.70710678
const WORLD_SCALE := Vector3(32.258, 20.9677, 32.258) * ISLAND_SHRINK
const WORLD_ORIGIN := Vector3(0.0, -0.5, 0.0)
## 组件实例自己的变换（同样照抄主场景）。
const INNER_SCALE := Vector3(1.0000007, 1.0, 1.0000007)
const INNER_ORIGIN := Vector3(0.0, 0.59046715, 0.0)

## 借地形用的场景（只取它的草地 / 山体做射线探测）。
const ISLAND_SCENE := "res://components/island/terrain.tscn"
## 矮款香蕉树（2.66 m）—— **减面版（LOD）**。
##
## 大世界里要放几千棵 1:1 米制的香蕉树，原版一棵树 2600~3100 面，
## 几千棵就是上千万面，GPU 扛不住。减面版 491 面（高 3.4 倍的差距），
## 整树高度和假茎剖面完全一致，远看跟原版没区别。
const TREE_SHORT := "res://assets/models/banana-tree-short/low_poly_banana_tree_lod.glb"
## 高款香蕉树（4.77 m）—— 减面版（LOD），571 面。
const TREE_TALL := "res://assets/models/banana-tree-tall/low_poly_banana_tree_lod.glb"
## 运行时脚本（补树干碰撞）。
const VEGETATION_SCRIPT := "res://components/island/vegetation/vegetation.gd"

const OUT_DIR := "res://scenes-3d/jurassic-island"
const OUT_JSON := "res://scenes-3d/jurassic-island/world_vegetation.json"
const OUT_TSCN := "res://scenes-3d/jurassic-island/world_vegetation.tscn"
const RES_SHORT := "res://scenes-3d/jurassic-island/world_vegetation_short_trees.res"
const RES_TALL := "res://scenes-3d/jurassic-island/world_vegetation_tall_trees.res"

# --- 布局参数 ----------------------------------------------------------------
## 候选网格间距（米）。
##
## 树改成 1:1 之后，一棵树占的"视觉面积"只有之前的四分之一 ——
## 想让林子看起来还是那么密，棵数就得翻两番，所以候选网格从 8 m 收到 5 m。
const CELL := 5.0
## 采样半径（米）：比岛的实际半径大一点，留余量。
const GRID_R := 1150.0 * ISLAND_SHRINK
## 树离岛缘留多少余量（米）。
const EDGE_MARGIN := 10.0 * ISLAND_SHRINK
## 两棵树之间的最小间距（米）。
##
## 1:1 米制下，4.77 m 的高款树树冠约 3.4 m 宽 —— 间距 4.5 m 刚好树冠相接，
## 看着才是一片连着的香蕉林。
const MIN_TREE_GAP := 6.0
## 树的整体缩放。
##
## **1.0 = 1:1 米制**（矮款 2.66 m / 高款 4.77 m）—— 跟模型原始尺寸一致，
## 也就是"玩家 1.5 m 眼高"下的正常比例（树是人的 1.8~3.2 倍高）。
## 之前这里放大到 2.0（5.3 / 9.5 m），那是六层楼高的树，比人还夸张。
const TREE_SCALE := 1.45
## 树的随机缩放范围（在这个基础上再抖一点）。
const TREE_SCALE_JITTER := 0.18
## 树的随机倾斜（度）。
const TREE_TILT_DEG := 2.2
## 树干埋进地里的深度（米）。
const TREE_SINK := 0.25
## 量坡度的基线长度（米）。
const SLOPE_BASELINE := 12.0 * ISLAND_SHRINK
## 坡度上限（米/米）。
const MAX_SLOPE := 0.45
## 台面高度（世界坐标）：岛体自带的台面，**光秃秃的岩盘**。
##
## 2026-11：原先岛面盖着一层草毯（草毯顶比台面高 15.7 m），树只长在草毯上。
## 草毯移除之后，岛面就是台面本身 —— 树直接种在岩盘上，这层过滤因此没了。
const BASE_Y := WORLD_ORIGIN.y + WORLD_SCALE.y * INNER_ORIGIN.y
## 雪线：高于这个高度不种树（山顶保持裸岩）。
##
## 2026-11：岛面改成岛体自带的台面之后，世界地面的高度从 **27.9 m** 降到
## **11.9 m**（草毯那层没了）。雪线是**相对地面**的，所以跟着一起下移，
## 树还是长到山腰同样的高度。
const SNOW_LINE := BASE_Y + 77.0 * ISLAND_SHRINK
## 恐龙的领地不能爬太高（世界坐标）。
##
## 也是**相对地面**的：地面在 BASE_Y，领地最高到地面以上 35 m（山腰）。
## 玩家出生点附近留一片空地（米）—— 出生点要看得见东西，别一睁眼就在树里。
const SPAWN := Vector3(0.0, 0.0, 77.85 * ISLAND_SHRINK)
## 出生点周围的空地半径（米）—— **不跟岛一起缩**。
##
## 这是玩法距离（玩家一睁眼要看得见东西），不是岛的相对尺寸。
const SPAWN_CLEAR := 30.0

# --- 噪声 --------------------------------------------------------------------
## 林子场：决定哪里是成片的林子、哪里是空地。
const GROVE_FREQ := 1.0 / (260.0 * ISLAND_SHRINK)
const GROVE_OCTAVES := 3
## 款式场：决定这一棵是高款还是矮款。
const VARIANT_FREQ := 1.0 / (55.0 * ISLAND_SHRINK)
## 林子占全岛面积的比例（按分位数取林线）。
##
## 0.45 —— 2026-11 跑起来看是"一大片空地 + 几丛树"，太旷了。
## 林子从四分之一扩到近一半，树也放大到 1.45 倍（4~7 m，像片真林子）。
const GROVE_COVERAGE := 0.45
## 林子中心的树密度上限（0~1）。
const GROVE_DENSITY := 0.92
## 位置哈希的"盐"：每种随机取值换一个盐，免得都长一样。
const SALT_JITTER := 11
const SALT_PATH := 23
const SALT_ACCEPT := 37
const SALT_SCALE := 53
const SALT_YAW := 67
const SALT_TILT := 79

# --- 恐龙参数 ----------------------------------------------------------------
## 恐龙清单：[名称, 场景, 数量, 体长（米）, 胶囊半径（米）]。
##
## 跟组件那份一样，每种恐龙一个自己的场景（模型 / 体型 / 碰撞 / AI 都在里面），
## 这里只负责"放哪只、放哪、巡哪条线"。
## 巡逻路线的路点数。
## 恐龙领地的半径范围（米）：大个子占大地方，小个子占小地方。
##
## 2000 m 的岛（可用面积约 2.9 km²）要装 100 只恐龙 → 每只分到
## 约 29,000 m²，也就是半径 ~96 m 的一圈。领地半径给 80~150 m，
## 边界上互相有点重叠没关系。
## 恐龙之间至少隔多远（米）。
##
## 2000 m 的岛要放 100 只：格子边长就是它，每格一只 —— 铺得开、也挤不爆。
## 恐龙跟玩家出生点至少隔多远（米）。
## 恐龙跟岛缘至少隔多远（米）。
## 恐龙脚底埋进地里的深度（米）。
## 最粗的树干半径（米）：树干半径 × 缩放。
## 路线两侧除了"恐龙身体 + 树干"之外还要留多少余量（米）。
## 恐龙边界围栏离岛缘多远（米）。
## 边界围栏的段数。

## 等物理服务器稳定的最小物理帧数。
const MIN_PHYSICS_FRAMES := 240
## 收敛检查最多打几轮探针。
const SETTLE_MAX_PASSES := 16

var _rng := RandomNumberGenerator.new()
## 放不下而跳过的恐龙数量（诊断用）。
var _grove_noise := FastNoiseLite.new()
var _variant_noise := FastNoiseLite.new()
var _terrain: Node3D
var _frames := 0
var _done := false
## 物理服务器收敛了没有（同一批探针连续两轮量出来的地面高度一样）。
var _settled := false
## 收敛警告只报一次，别刷屏。
var _settle_warned := false
var _seed_value := 20261107

## 岛缘半径剖面（每个角度的最外沿地面半径，世界坐标）。
var _edge := PackedFloat32Array()
var _edge_samples := 180
## 山体在 XZ 平面上的矩形占地范围（世界坐标）。
##
## 大世界的山有 372 m 高、占地几百米，山脚是一圈陡坎 ——
## 恐龙的领地和巡逻路线不能贴着它走。
var _mountain_center := Vector2.ZERO
var _mountain_min := Vector2.ZERO
var _mountain_max := Vector2.ZERO
var _mountain_has := false
## 路线离山体至少留多远（米）。
const MOUNTAIN_MARGIN := 4.0


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 1:
		_seed_value = int(args[1])

	_rng.seed = _seed_value + 31
	_grove_noise.seed = _seed_value
	_grove_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_grove_noise.frequency = GROVE_FREQ
	_grove_noise.fractal_octaves = GROVE_OCTAVES
	_grove_noise.fractal_gain = 0.5

	_variant_noise.seed = _seed_value + 7919
	_variant_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_variant_noise.frequency = VARIANT_FREQ
	_variant_noise.fractal_octaves = 2

	# 借地形：`terrain.tscn` 只有岩台 + 山体，别的什么都没有。
	_terrain = load(ISLAND_SCENE).instantiate() as Node3D
	_terrain.transform = _world_transform()
	# 延后一帧挂：此刻 root 正在"设置子节点"，直接 add_child 会被拒。
	get_tree().root.add_child.call_deferred(_terrain)


## 组件岛 → 世界坐标的变换（跟主场景一模一样）。
func _world_transform() -> Transform3D:
	return Transform3D(Basis.from_scale(WORLD_SCALE), WORLD_ORIGIN) \
		* Transform3D(Basis.from_scale(INNER_SCALE), INNER_ORIGIN)


func _process(_dt: float) -> void:
	if _done:
		return
	_frames += 1
	# 等**物理帧**：island.gd 在 _ready() 里补碰撞，碰撞体要等物理服务器
	# 下一次同步才真正存在。启动阶段渲染帧可能比物理帧快得多，只数渲染帧
	# 的话射线有时打在还没同步好的地形上，量出来的地面高度会飘。
	if _frames < 4 or Engine.get_physics_frames() < MIN_PHYSICS_FRAMES:
		return
	# 再等物理服务器**收敛**：同一批探针连续两轮量出来的地面高度完全一样
	# 才算稳。光等帧数不保险 —— 实测同样等 240 帧，量出来的地面高度还是会飘。
	if not _settled:
		if not _physics_settled():
			return
		_settled = true
	_done = true
	_generate()
	_bake_from_json()
	get_tree().quit()


# ==============================================================================
# 一、生成布局
# ==============================================================================

func _generate() -> void:
	_build_edge_profile()
	_measure_mountain()
	if _mountain_has:
		print("  山体：中心 (%.0f, %.0f)，占地 x[%.0f, %.0f] z[%.0f, %.0f]" % [
			_mountain_center.x, _mountain_center.y,
			_mountain_min.x, _mountain_max.x, _mountain_min.y, _mountain_max.y])
	var edge_lo := INF
	var edge_hi := -INF
	for r in _edge:
		edge_lo = minf(edge_lo, r)
		edge_hi = maxf(edge_hi, r)
	print("世界岛缘半径 %.0f–%.0f m" % [edge_lo, edge_hi])

	# 恐龙**不再烘**：改由 `components/dinosaurs/` 组件在运行时放进去，
	# 巡逻路线按地形现算（见 DinosaurPatrol）。这里只烘树。
	var trees := _generate_trees()

	var data := {
		"seed": _seed_value,
		"generator": "bake_world_vegetation.gd",
		"scale": TREE_SCALE,
		"trees": trees,
	}
	_write_json(OUT_JSON, data)
	var n_short: int = (trees["short"] as Array).size()
	var n_tall: int = (trees["tall"] as Array).size()
	print("GENERATED %s" % OUT_JSON)
	print("  树 %d 棵（矮 %d / 高 %d）" % [n_short + n_tall, n_short, n_tall])


## 量每个角度的岛缘半径并平滑。岛缘是许多块地形拼出来的，
## 不平滑的话林子会抖成锯齿。
func _build_edge_profile() -> void:
	_edge.resize(_edge_samples)
	for i in _edge_samples:
		var a := TAU * i / _edge_samples
		var last := 0.0
		var rr := 20.0
		while rr < 1400.0:
			if _ground(cos(a) * rr, sin(a) * rr) != -INF:
				last = rr
			rr += 4.0
		_edge[i] = last
	var smooth := _edge.duplicate()
	for i in _edge_samples:
		var s := 0.0
		for k in [-1, 0, 1]:
			s += _edge[(i + k + _edge_samples) % _edge_samples]
		smooth[i] = s / 3.0
	_edge = smooth


## 量山体在 XZ 平面上的矩形范围（世界坐标）。
func _measure_mountain() -> void:
	var mountain := _terrain.get_node_or_null("Island/Mountain")
	if mountain == null:
		mountain = _terrain.get_node_or_null("Mountain")
	if mountain == null:
		return
	# LowMountain 是实例节点（Node3D），网格在它下面
	var mesh: MeshInstance3D = null
	var meshes := mountain.find_children("*", "MeshInstance3D", true, false)
	if meshes.size() > 0:
		mesh = meshes[0]
	if mesh == null or mesh.mesh == null:
		push_warning("量不到山体的网格，巡逻路线会贴着山脚走")
		return
	_mountain_center = Vector2(mountain.global_position.x, mountain.global_position.z)
	var box := mesh.get_aabb()
	var xf := mesh.global_transform
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	for i in 8:
		var corner := Vector3(
			box.position.x if (i & 1) == 0 else box.end.x,
			box.position.y if (i & 2) == 0 else box.end.y,
			box.position.z if (i & 4) == 0 else box.end.z)
		var w := xf * corner
		lo.x = minf(lo.x, w.x)
		lo.y = minf(lo.y, w.z)
		hi.x = maxf(hi.x, w.x)
		hi.y = maxf(hi.y, w.z)
	_mountain_min = lo
	_mountain_max = hi
	_mountain_has = true


## 这个点是不是在山体（含余量）里面。
func _in_mountain(p: Vector2, margin: float) -> bool:
	if not _mountain_has:
		return false
	return p.x >= _mountain_min.x - margin and p.x <= _mountain_max.x + margin \
		and p.y >= _mountain_min.y - margin and p.y <= _mountain_max.y + margin


## 把点推到山体外面（沿"离山心最远"的方向推，绕山走才不会折线）。
func _push_from_mountain(p: Vector2) -> Vector2:
	if not _mountain_has or not _in_mountain(p, MOUNTAIN_MARGIN):
		return p
	var dir := p - _mountain_center
	if dir.length() < 0.001:
		dir = Vector2(0.0, 1.0)
	dir = dir.normalized()
	var start := _mountain_center.distance_to(p)
	for i in 400:
		var q := _mountain_center + dir * (start + float(i) * 2.0)
		if not _in_mountain(q, MOUNTAIN_MARGIN):
			return q
	return p


func _edge_at(angle: float) -> float:
	var t := fposmod(angle, TAU) / TAU * _edge_samples
	var i := int(t) % _edge_samples
	var j := (i + 1) % _edge_samples
	return lerpf(_edge[i], _edge[j], t - floor(t))


## 按噪声采样出每棵树的位置。
##
## 流程：抖动网格给候选点 → 岛内？→ 在草地上？→ 坡度够缓？→ 雪线以下？
## → 林子里？（按分位数取林线）→ 跟恐龙路线挨太近就丢掉。
##
## 整个过程**没有随机数流**：抖动、抽签都用位置哈希，
## 改一个参数不会把整片林子重新洗牌。
func _generate_trees() -> Dictionary:
	var short: Array = []
	var tall: Array = []
	var placed: Array[Vector2] = []

	# ---- 第一遍：收候选点 ----
	var candidates: Array = []
	var densities := PackedFloat32Array()
	var cell_count := int(ceil(GRID_R * 2.0 / CELL))
	for gz in range(-cell_count, cell_count):
		for gx in range(-cell_count, cell_count):
			var x := (gx + _hash_rand(gx, gz, SALT_JITTER)) * CELL
			var z := (gz + _hash_rand(gx, gz, SALT_JITTER + 1)) * CELL
			var p := Vector2(x, z)
			var r := p.length()
			if r > GRID_R:
				continue
			# 岛缘以内才种树
			if r > _edge_at(atan2(z, x)) - EDGE_MARGIN:
				continue
			# 贴地
			var y := _ground(x, z)
			if y == -INF:
				continue
			# 雪线以上不长树（山顶保持裸岩）
			if y > SNOW_LINE:
				continue
			# 坡度
			if _slope_at(x, z) > MAX_SLOPE:
				continue
			# 玩家出生点周围留一片空地
			if p.distance_to(Vector2(SPAWN.x, SPAWN.z)) < SPAWN_CLEAR:
				continue
			candidates.append([p, y])
			densities.append(_grove_at(x, z))

	if candidates.is_empty():
		return {"short": short, "tall": tall}

	# ---- 林线：按分位数取 ----
	var sorted := densities.duplicate()
	sorted.sort()
	var idx := clampi(int(floor((1.0 - GROVE_COVERAGE) * float(sorted.size()))),
		0, sorted.size() - 1)
	var floor_value := sorted[idx]

	# ---- 第二遍：林线以内按密度从浓到稀种树 ----
	var order: Array = []
	for i in candidates.size():
		order.append(i)
	order.sort_custom(func(a: int, b: int) -> bool:
		return densities[a] > densities[b])
	for i in order:
		var entry: Array = candidates[i]
		var p: Vector2 = entry[0]
		var y: float = entry[1]
		var density := densities[i]
		if density < floor_value:
			continue
		# 林子中心更密：密度越高越容易种下
		var w := (density - floor_value) / maxf(0.0001, 1.0 - floor_value)
		if _hash_rand(int(p.x * 16.0), int(p.y * 16.0), SALT_ACCEPT) > GROVE_DENSITY * w:
			continue
		# 跟别的树别贴太近
		var too_close := false
		for q in placed:
			if p.distance_squared_to(q) < MIN_TREE_GAP * MIN_TREE_GAP:
				too_close = true
				break
		if too_close:
			continue
		placed.append(p)

		# 高矮：款式噪声决定，两种树成片交错
		var is_tall := _variant_noise.get_noise_2d(p.x, p.y) > 0.0
		var hx := int(p.x * 16.0)
		var hz := int(p.y * 16.0)
		var scale := TREE_SCALE * (1.0 + (_hash_rand(hx, hz, SALT_SCALE) * 2.0 - 1.0)
			* TREE_SCALE_JITTER)
		var yaw := _hash_rand(hx, hz, SALT_YAW) * TAU
		var tilt := deg_to_rad(TREE_TILT_DEG)
		var basis := Basis(Vector3.UP, yaw) \
			* Basis(Vector3.RIGHT, (_hash_rand(hx, hz, SALT_TILT) * 2.0 - 1.0) * tilt) \
			* Basis(Vector3.FORWARD, (_hash_rand(hx, hz, SALT_TILT + 1) * 2.0 - 1.0) * tilt) \
			* Basis.from_scale(Vector3(scale, scale, scale))
		var xf := Transform3D(basis, Vector3(p.x, y - TREE_SINK, p.y))
		if is_tall:
			tall.append(_to_array(xf))
		else:
			short.append(_to_array(xf))

	print("  候选 %d，林线=%.3f，树 %d 棵" % [
		candidates.size(), floor_value, placed.size()])
	return {"short": short, "tall": tall}


## 位置哈希 → 0..1 的伪随机数。
##
## 用它代替随机数流：同一个格子永远得到同一个抖动、同一个抽签结果，
## 所以改一个参数不会把整片林子重新洗牌。
func _hash_rand(ix: int, iz: int, salt: int) -> float:
	var h := (ix * 73856093) ^ (iz * 19349663) ^ (salt * 83492791)
	h = (h ^ (h >> 13)) * 1274126177
	h = h ^ (h >> 16)
	return float(h & 0xFFFFFF) / float(0xFFFFFF)


## 林子场：0（空地）– 1（最密的林子）。
func _grove_at(x: float, z: float) -> float:
	var v := (_grove_noise.get_noise_2d(x, z) + 1.0) * 0.5
	var fine := (_grove_noise.get_noise_2d(x * 3.3 + 41.0, z * 3.3 - 17.0) + 1.0) * 0.5
	v = v * 0.78 + fine * 0.22
	return clampf((v - 0.30) / 0.34, 0.0, 1.0)




func _bake_from_json() -> void:
	var data = JSON.parse_string(FileAccess.get_file_as_string(OUT_JSON))
	if data == null or not data.has("trees"):
		push_error("JSON 读不出来或缺少 trees: " + OUT_JSON)
		get_tree().quit(1)
		return
	var trees: Dictionary = data["trees"]

	var short_mesh := _merge_tree_mesh(TREE_SHORT)
	var tall_mesh := _merge_tree_mesh(TREE_TALL)
	if short_mesh == null or tall_mesh == null:
		push_error("取不到树的网格")
		get_tree().quit(1)
		return

	var mm_short := _build_multimesh(short_mesh, trees.get("short", []))
	var mm_tall := _build_multimesh(tall_mesh, trees.get("tall", []))
	ResourceSaver.save(mm_short, RES_SHORT)
	ResourceSaver.save(mm_tall, RES_TALL)

	var root_node := Node3D.new()
	root_node.name = "WorldVegetation"
	root_node.set_script(load(VEGETATION_SCRIPT))
	# 树干碰撞按**放大后**的尺寸来（树放大 2 倍）
	root_node.set("short_trunk_radius", 0.30 * TREE_SCALE)
	root_node.set("short_trunk_height", 1.69 * TREE_SCALE)
	root_node.set("tall_trunk_radius", 0.36 * TREE_SCALE)
	root_node.set("tall_trunk_height", 3.26 * TREE_SCALE)
	# 几千棵树：用物理服务器直接挂形状，不生成几千个 CollisionShape3D 节点
	root_node.set("collision_via_physics_server", true)

	var trees_node := Node3D.new()
	trees_node.name = "Trees"
	root_node.add_child(trees_node)
	trees_node.owner = root_node

	var mmi_short := MultiMeshInstance3D.new()
	mmi_short.name = "ShortTrees"
	mmi_short.multimesh = load(RES_SHORT)
	mmi_short.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	# 上千棵树的阴影是纯浪费（跟本地草石一个道理）
	mmi_short.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	trees_node.add_child(mmi_short)
	mmi_short.owner = root_node

	var mmi_tall := MultiMeshInstance3D.new()
	mmi_tall.name = "TallTrees"
	mmi_tall.multimesh = load(RES_TALL)
	mmi_tall.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	mmi_tall.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	trees_node.add_child(mmi_tall)
	mmi_tall.owner = root_node

	var ps := PackedScene.new()
	if ps.pack(root_node) != OK:
		push_error("pack 失败")
		get_tree().quit(1)
		return
	if ResourceSaver.save(ps, OUT_TSCN) != OK:
		push_error("保存场景失败: " + OUT_TSCN)
		get_tree().quit(1)
		return

	print("BAKED %s" % OUT_TSCN)
	print("  矮树 %d 棵 / 高树 %d 棵（draw call: 2 个 MultiMesh）" % [
		mm_short.instance_count, mm_tall.instance_count])
	print("  恐龙不再烘 —— 由 components/dinosaurs/ 组件在运行时放进去")


func _merge_tree_mesh(glb_path: String) -> Mesh:
	var inst: Node = (load(glb_path) as PackedScene).instantiate()
	var merged := ArrayMesh.new()
	for node in _mesh_instances(inst):
		var mi := node as MeshInstance3D
		if mi.mesh == null:
			continue
		var to_root := _transform_to_root(mi, inst)
		for s in mi.mesh.get_surface_count():
			var arrays := mi.mesh.surface_get_arrays(s)
			if arrays.is_empty():
				continue
			arrays = arrays.duplicate()
			arrays[Mesh.ARRAY_VERTEX] = _transform_verts(arrays[Mesh.ARRAY_VERTEX], to_root)
			arrays[Mesh.ARRAY_NORMAL] = _transform_normals(arrays[Mesh.ARRAY_NORMAL], to_root)
			merged.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
			merged.surface_set_material(merged.get_surface_count() - 1,
				mi.mesh.surface_get_material(s))
	inst.free()
	return merged


func _build_multimesh(mesh: Mesh, transforms: Array) -> MultiMesh:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.instance_count = transforms.size()
	for i in transforms.size():
		mm.set_instance_transform(i, _to_transform(transforms[i]))
	mm.mesh = mesh
	# 手动给一个足够大的包围盒：MultiMesh 的自动 AABB 在"先写变换、后挂网格"
	# 的顺序下不一定算得全，宁可给大一点，也不要整片林子被视锥剔掉。
	if "custom_aabb" in mm:
		mm.custom_aabb = AABB(Vector3(-1250.0, -30.0, -1250.0), Vector3(2500.0, 500.0, 2500.0))
	return mm


# ==============================================================================
# 三、工具
# ==============================================================================

## 物理服务器是不是**收敛**了：同一批探针连续两轮量出来的地面高度完全一样。
##
## 为什么要这个：地形碰撞是 116 块共享同一份三角面的 [CollisionShape3D]，
## 物理服务器第一次查询时才建 BVH，早到的射线会漏掉一部分地形 ——
## 量出来的地面高度偏低，树的棵数、恐龙的落点全都会跟着飘。
func _physics_settled() -> bool:
	var points := PackedVector2Array()
	for i in 96:
		var a := TAU * i / 96.0
		# 探针半径跟着岛缩（岛小一半 → 最外圈探针要收进来，
		# 否则大半探针落在岛外，永远等不到"物理收敛"）
		for r0 in [40.0, 120.0, 260.0, 450.0, 650.0, 850.0]:
			var r: float = r0 * ISLAND_SHRINK
			points.append(Vector2(cos(a) * float(r), sin(a) * float(r)))
	var prev := PackedFloat32Array()
	var prev_miss := -1
	for p in SETTLE_MAX_PASSES:
		var cur := PackedFloat32Array()
		var miss := 0
		for pt in points:
			var y := _ground(pt.x, pt.y)
			if y == -INF:
				miss += 1
			cur.append(y)
		# 大量探针**打不到地面** = 地形还没补齐（116 块地形里有几块的碰撞
		# 还没进物理服务器）。这种状态是"稳定的坏"，光比两轮相等发现不了，
		# 必须显式排除掉 —— 否则树的棵数能差一倍。
		#
		# 留 5% 的余量：个别探针本来就该打空（比如落在岛缘外面）。
		if float(miss) / float(points.size()) > 0.05:
			prev = cur
			prev_miss = miss
			continue
		if p > 0 and cur == prev and miss == prev_miss:
			return true
		prev = cur
		prev_miss = miss
	if not _settle_warned:
		_settle_warned = true
		push_warning("物理状态在 %d 轮内没有收敛，继续等" % SETTLE_MAX_PASSES)
	return false


## 某点正下方的地面高度；打不到返回 -INF。
func _ground(x: float, z: float) -> float:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, 900.0, z), Vector3(x, -300.0, z))
	q.collision_mask = 1       # LAYER_WORLD
	var hit := get_tree().root.world_3d.direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y


## 某点的坡度（**米/米**）：用前后左右各 [constant SLOPE_BASELINE] m 的地面高度差。
##
## ⚠️ 高度差要**除以基线**才是坡度。以前这里直接返回高度差，
## 而大世界的基线是 12 m —— 于是"坡度上限 1.0"其实只有 0.083 m/m，
## 整座岛都被当成陡坡，恐龙没地方站、草也不长。
func _slope_at(x: float, z: float) -> float:
	var h0 := _ground(x, z)
	if h0 == -INF:
		return 99.0
	var hx := _ground(x + SLOPE_BASELINE, z)
	var hz := _ground(x, z + SLOPE_BASELINE)
	var s := 0.0
	if hx != -INF:
		s = maxf(s, absf(hx - h0) / SLOPE_BASELINE)
	if hz != -INF:
		s = maxf(s, absf(hz - h0) / SLOPE_BASELINE)
	return s


func _mesh_instances(node: Node) -> Array[Node]:
	var out: Array[Node] = []
	if node is MeshInstance3D:
		out.append(node)
	for child in node.get_children():
		out.append_array(_mesh_instances(child))
	return out


## node 相对 ancestor 的变换（不依赖节点在场景树里）。
func _transform_to_root(node: Node3D, ancestor: Node) -> Transform3D:
	var t := Transform3D()
	var n: Node = node
	while n != null and n != ancestor:
		t = (n as Node3D).transform * t
		n = n.get_parent()
	return t


func _transform_verts(verts: PackedVector3Array, xf: Transform3D) -> PackedVector3Array:
	var out := verts.duplicate()
	for i in out.size():
		out[i] = xf * out[i]
	return out


func _transform_normals(normals: PackedVector3Array, xf: Transform3D) -> PackedVector3Array:
	var out := normals.duplicate()
	var basis := xf.basis.orthonormalized()
	for i in out.size():
		out[i] = (basis * out[i]).normalized()
	return out


## 路线 → JSON 里的 [[x, y, z], ...]。
func _route_to_array(route: PackedVector3Array) -> Array:
	var out: Array = []
	for p in route:
		out.append([p.x, p.y, p.z])
	return out


## JSON 里的 [[x, y, z], ...] → 路线。
func _route_from_array(data: Array) -> PackedVector3Array:
	var out := PackedVector3Array()
	for entry in data:
		var v: Array = entry
		out.append(Vector3(v[0], v[1], v[2]))
	return out


## 一行 12 个 float：basis.x, basis.y, basis.z, origin（与其它组件的 JSON 一致）。
func _to_array(t: Transform3D) -> Array:
	return [t.basis.x.x, t.basis.x.y, t.basis.x.z,
		t.basis.y.x, t.basis.y.y, t.basis.y.z,
		t.basis.z.x, t.basis.z.y, t.basis.z.z,
		t.origin.x, t.origin.y, t.origin.z]


func _to_transform(v: Array) -> Transform3D:
	return Transform3D(
		Vector3(v[0], v[1], v[2]),
		Vector3(v[3], v[4], v[5]),
		Vector3(v[6], v[7], v[8]),
		Vector3(v[9], v[10], v[11]))


func _write_json(path: String, data: Dictionary) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		push_error("JSON 写不进去: " + path)
		return
	f.store_string(JSON.stringify(data, "  ", false, true) + "\n")
	f.close()
