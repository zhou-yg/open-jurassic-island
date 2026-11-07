extends SceneTree
## 香蕉树林 + 恐龙的**烘焙**脚本。
##
## 为什么要烘：岛上要"很密"的树（几百棵）。逐棵摆成场景实例 = 几百个节点、
## 几百个 draw call、几百份网格内存；而且布局必须是**固定**的（每次打开位置
## 完全一样），不能运行时随机。烘成 MultiMesh 之后：节点 2 个、
## draw call 4 个（2 种树 × 每个 2 个表面）、网格内存 2 份。
##
## 布局全部来自 FastNoiseLite 采样：
##   - **密度场**决定哪里是林子、哪里是空地（空地留给恐龙和玩家）；
##   - **款式场**决定这一棵是高款还是矮款 —— 两种树成片交错，不会东一棵高
##     西一棵矮地乱跳，整体比例也接近对半；
##   - **道路**：一条环岛小路 + 三条支路，路面上不长树 —— 冒险者顺着路跑，
##     恐龙也能沿着路巡逻；林子里的树则可以当掩体躲开恐龙的视野。
##
## 树贴地用**垂直射线**打真实地面（草地 / 山体），所以每棵都站在坡上、
## 不会被地形穿模。恐龙同理，并且按骨架（骨骼）算出实际体型，
## 再缩到真实尺寸（霸王龙 11 m、迅猛龙 2.2 m …），脚底贴地。
##
## 用法（**必须带真实渲染器，不要加 `--headless`** —— headless 的 dummy
## 渲染器会把 MultiMesh 的实例变换全丢掉，烘出来是一堆零矩阵）：
## [codeblock]
## # 重新生成布局 + 重新烘焙（换种子 / 改参数后跑这个）
## godot --path . --script res://components/island/vegetation/bake_vegetation.gd -- all
##
## # 只按现有 JSON 重新烘 .res + .tscn（改了 JSON 之后跑这个）
## godot --path . --script res://components/island/vegetation/bake_vegetation.gd -- bake
## [/codeblock]

## 借地形用的场景（只取它的草地 / 山体做射线探测）。
const ISLAND_SCENE := "res://components/island/island.tscn"
## 矮款香蕉树（2.66 m）。
const TREE_SHORT := "res://assets/models/banana-tree-short/low_poly_banana_tree.glb"
## 高款香蕉树（4.77 m）。
const TREE_TALL := "res://assets/models/banana-tree-tall/low_poly_banana_tree.glb"
## 运行时脚本（补树干碰撞）。
const VEGETATION_SCRIPT := "res://components/island/vegetation/vegetation.gd"

## 草石散布的数据源（石头位置）。树要避开石头，别从石头里长出来。
const SCATTER_JSON := "res://components/island/ground_scatter/island_scatter.json"
const OUT_DIR := "res://components/island/vegetation"
const OUT_JSON := "res://components/island/vegetation/island_vegetation.json"
const OUT_TSCN := "res://components/island/vegetation/island_vegetation.tscn"
## 恐龙的场景**单独一个文件** —— 树和恐龙是两回事，不该挤在一个场景里。
const OUT_DINOS := "res://components/island/vegetation/island_dinosaurs.tscn"
const RES_SHORT := "res://components/island/vegetation/island_vegetation_short_trees.res"
const RES_TALL := "res://components/island/vegetation/island_vegetation_tall_trees.res"

# --- 布局参数 ----------------------------------------------------------------
## 候选网格间距（米）。格子里的点会被抖动，所以实际间距比这个略小。
const CELL := 1.15
## 采样半径（米）。岛的半径约 32 m，多留一点余量。
const GRID_R := 42.0
## 树离岛缘留多少余量（米）。
const EDGE_MARGIN := 2.0
## 两棵树之间的最小间距（米），避免叠在一起。
const MIN_TREE_GAP := 1.15
## 量坡度的基线长度（米）。
const SLOPE_BASELINE := 2.0
## 坡度上限（米/米）。超过这个坡度不种树。
## 草地是许多块圆地形拼起来的，接缝处有半米级的落差，1 m 基线上量出来
## 的坡度会比真坡度陡不少，所以这个阈值放得比较宽（≈40°）。
const MAX_SLOPE := 1.0
## 雪线：高于这个高度不种树（山顶保持裸岩）。
const SNOW_LINE := 5.0
## 树干埋进地里的深度（米），免得根部悬空。
const TREE_SINK := 0.06
## 园区围墙离岛缘多远（米）。跟 `park_perimeter/bake_perimeter.gd` 的 INSET 一致。
const WALL_INSET := 10.5
## 树干离围墙中心线至少多远（米），免得树从残墙里长出来。
const WALL_CLEAR := 1.4
## 树的随机缩放范围。
const TREE_SCALE_MIN := 0.86
const TREE_SCALE_MAX := 1.16
## 树的随机倾斜（度），免得整片林子像插在牙签上。
const TREE_TILT_DEG := 2.6

# --- 道路网参数 --------------------------------------------------------------
##
## 路线是**双环 + 四辐条**的网格：
##
## ```
##             ┌──────── 环 A（外圈，围墙外）────────┐
##             │   ╱                          ╲     │
##             │  ╱ 辐条                 辐条 ╲    │
##             └─╱────── 环 B（内圈，围墙内）──╲───┘
## ```
##
## 辐条穿过围墙，把两圈连起来 —— 于是路上有 **6 个闭合回路**
## （两圈 + 四个格子），恐龙可以各巡各的，也能从外圈走到内圈。
## 围墙在辐条穿过的地方要留门洞（见
## `components/island/park_perimeter/bake_perimeter.gd` 的 OPENING_ANGLES）。
##
## 外圈离岛缘很近（3.5 m）：它走的是围墙和崖边之间那条带子。
## 内圈在围墙里面。
const RING_OUTER_INSET := 7.5
const RING_MID_INSET := 14.0
## 环路的半宽（米）。
const RING_HALF_W := 1.5
## 辐条的半宽（米）。
const SPOKE_HALF_W := 1.3
## 辐条的角度（度，0 = +X，逆时针为正）。**必须跟围墙的门洞角度一致。**
const SPOKE_ANGLES := [30.0, 150.0, 210.0, 330.0]

# --- 恐龙参数 ----------------------------------------------------------------
## 恐龙清单：[名称, 场景, 数量, 体长（米）]。
##
## 场景在 `components/vegetation/dinosaur/`，**每种恐龙一个 .tscn**：
## 模型、缩放（真实体型）、胶囊碰撞、巡逻速度都写在场景里，
## 巡逻的行为在 `dinosaur.gd`。这里只负责"放哪只、放哪、沿哪条路巡"。
const DINOS := [
	["TRex", "res://components/vegetation/dinosaur/t_rex.tscn", 2, 11.0],
	["Triceratops", "res://components/vegetation/dinosaur/triceratops.tscn", 2, 8.0],
	["Stegosaurus", "res://components/vegetation/dinosaur/stegosaurus.tscn", 1, 8.5],
	["Parasaurolophus", "res://components/vegetation/dinosaur/parasaurolophus.tscn", 2, 6.0],
	["Velociraptor", "res://components/vegetation/dinosaur/velociraptor.tscn", 2, 2.2],
	["Apatosaurus", "res://components/vegetation/dinosaur/apatosaurus.tscn", 1, 17.0],
]
## 巡逻路线：环岛路上取多少个路点。
const PATROL_WAYPOINTS := 24
## 巡逻路线相对环岛路的横向偏移范围（米）。错开一点，几只恐龙不会走同一条线。
const PATROL_WANDER := 0.35
## 巡逻路点离岛缘至少留多远（米）。恐龙在崖边走容易掉下去。
const PATROL_EDGE_MARGIN := 7.0
## 恐龙边界围栏离岛缘多远（米）。
const BOUNDARY_INSET := 1.5
## 巡逻路线上的地面最高可以有多高（米）。山脚有抬高的过渡地形，
## 不限制的话恐龙会顺着缓坡爬到半山腰上去。
const PATROL_MAX_Y := 2.2
## 每只恐龙分到的回路（下标按"第几只恐龙"数）。
## 0 = 外圈，1 = 内圈，2..5 = 四个格子。
const DINO_CIRCUITS := [0, 1, 2, 3, 4, 5, 0, 1, 2, 3]
## 恐龙脚底埋进地里的深度（米）。
const DINO_SINK := 0.12
## 恐龙之间至少隔多远（米）。
const DINO_GAP := 9.0
## 恐龙要离**路边**多远（米）。
const DINO_PATH_CLEAR := 2.4

# --- 噪声 --------------------------------------------------------------------
## 密度噪声：决定"哪里是林子、哪里是空地"。
const DENSITY_FREQ := 0.052
const DENSITY_OCTAVES := 3
## 款式噪声：决定高款 / 矮款。
const VARIANT_FREQ := 0.105
## 高款阈值（款式噪声 > 阈值 = 高款）。略微偏矮，让矮树多一点点。
const VARIANT_THRESHOLD := 0.04
## 岛上"能长树的地"里，有多大比例算林子（按分位数取林线）。
## 0.85 = 85% 的候选点算林子，其余是空地（恐龙和玩家活动的地方）。
const FOREST_COVERAGE := 0.92
## 位置哈希的"盐"：每种随机取值换一个盐，免得都长一样。
const SALT_JITTER := 11
const SALT_PATH := 23
const SALT_ACCEPT := 37
const SALT_SCALE := 53
const SALT_YAW := 67
const SALT_TILT := 79
## 密度增益：林子里越浓的地方树越密（概率 = 密度 × 增益，截到 1）。
const DENSITY_GAIN := 3.2
## 恐龙活动区的密度上限：这个密度以下的地方一定是空地（不种树）。
const DINO_CLEARING := 0.30

var _rng := RandomNumberGenerator.new()
var _density_noise := FastNoiseLite.new()
var _variant_noise := FastNoiseLite.new()
var _terrain: Node3D
var _frames := 0
var _done := false
var _seed_value := 20261107
var _mode := "all"

## 等物理服务器稳定的最小物理帧数。
const MIN_PHYSICS_FRAMES := 60
## 收敛检查最多打几轮探针。
const SETTLE_MAX_PASSES := 16

## 岛缘半径剖面（每个角度的最外沿地面半径）。
var _edge := PackedFloat32Array()
var _edge_samples := 144

## 路面折线集合（每条是一个 Vector2 折线）。
var _paths: Array[PackedVector2Array] = []
## 路面半宽（每条路一个）。
var _path_half_w := PackedFloat32Array()
## 石头（[Vector2 位置, float 半径]）：树要避开它们。
var _rocks: Array = []


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		_mode = "all"
	else:
		_mode = String(args[0])
	if args.size() > 1:
		_seed_value = int(args[1])
	_rng.seed = _seed_value

	_density_noise.seed = _seed_value
	_density_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_density_noise.frequency = DENSITY_FREQ
	_density_noise.fractal_octaves = DENSITY_OCTAVES
	_density_noise.fractal_gain = 0.5

	_variant_noise.seed = _seed_value + 7919
	_variant_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	_variant_noise.frequency = VARIANT_FREQ
	_variant_noise.fractal_octaves = 2

	_load_rocks()

	# 借地形：只留草地和山体做射线探测。展示节点、草石、围墙全关掉 ——
	# 草石的石头有碰撞体、围墙也有，射线打在它们上面会量错地面高度。
	_terrain = load(ISLAND_SCENE).instantiate() as Node3D
	_terrain.set("show_presentation", false)
	_terrain.set("show_scatter", false)
	_terrain.set("show_perimeter", false)
	root.add_child(_terrain)


func _process(_dt: float) -> bool:
	if _done:
		return true
	_frames += 1
	# 等**物理帧**，不是等渲染帧：island.gd 在 _ready() 里补碰撞，碰撞体要等
	# 物理服务器下一次同步才真正存在。启动阶段渲染帧可能跑得比物理帧快得多
	# （一帧顶好几帧），只数渲染帧的话，射线有时打在还没同步好的地形上，
	# 量出来的地面高度会飘 —— 同一份脚本跑两次结果不一样。
	# 等 240 个物理帧，物理服务器一定已经稳定。
	if _frames < 4 or Engine.get_physics_frames() < 240:
		return false
	_done = true

	match _mode:
		"generate":
			_generate()
		"bake":
			_bake_from_json()
		_:
			_generate()
			_bake_from_json()
	quit()
	return true


# ==============================================================================
# 一、生成布局
# ==============================================================================

func _generate() -> void:
	_build_edge_profile()
	_build_paths()
	var edge_lo := INF
	var edge_hi := -INF
	for r in _edge:
		edge_lo = minf(edge_lo, r)
		edge_hi = maxf(edge_hi, r)
	print("岛缘半径 %.1f–%.1f m；道路 %d 条" % [edge_lo, edge_hi, _paths.size()])

	# 先摆恐龙、再种树：恐龙要占"空地"，所以它先选好位置，
	# 种树的时候再把恐龙周围的树让开。反过来的话恐龙永远找不到空地。
	var dinos := _place_dinosaurs()
	var trees := _generate_trees(dinos)

	var data := {
		"seed": _seed_value,
		"generator": "bake_vegetation.gd",
		"trees": trees,
		"dinosaurs": dinos,
	}
	_write_json(OUT_JSON, data)
	var n_short: int = (trees["short"] as Array).size()
	var n_tall: int = (trees["tall"] as Array).size()
	print("GENERATED %s" % OUT_JSON)
	print("  树 %d 棵（矮 %d / 高 %d，高款占 %.0f%%）" % [
		n_short + n_tall, n_short, n_tall,
		100.0 * float(n_tall) / maxf(1.0, float(n_short + n_tall))])
	print("  恐龙 %d 只" % (dinos as Array).size())


## 从草石散布的 JSON 里读出石头位置（树要避开它们）。
##
## 石头模型是 2.9 m 的，所以它的碰撞半径 ≈ 缩放 × 1.45。
func _load_rocks() -> void:
	_rocks.clear()
	var data = JSON.parse_string(FileAccess.get_file_as_string(SCATTER_JSON))
	if data == null or not (data is Dictionary):
		return
	for group in (data as Dictionary).keys():
		if not String(group).contains("Rocks"):
			continue
		var kinds: Dictionary = (data as Dictionary)[group]
		for kind in kinds.keys():
			for entry in kinds[kind]:
				var v: Array = entry
				var basis := Basis(
					Vector3(v[0], v[1], v[2]),
					Vector3(v[3], v[4], v[5]),
					Vector3(v[6], v[7], v[8]))
				var scale := basis.get_scale().x
				_rocks.append([Vector2(v[9], v[11]), scale * 1.45])


## 量每个角度的岛缘半径并平滑。岛缘是许多块地形拼出来的，不平滑的话林子会抖成锯齿。
func _build_edge_profile() -> void:
	_edge.resize(_edge_samples)
	for i in _edge_samples:
		var a := TAU * i / _edge_samples
		var last := 0.0
		var rr := 10.0
		while rr < 46.0:
			if _ground(cos(a) * rr, sin(a) * rr) != -INF:
				last = rr
			rr += 0.5
		_edge[i] = last
	var smooth := _edge.duplicate()
	for i in _edge_samples:
		var s := 0.0
		for k in [-1, 0, 1]:
			s += _edge[(i + k + _edge_samples) % _edge_samples]
		smooth[i] = s / 3.0
	_edge = smooth


func _edge_at(angle: float) -> float:
	var t := fposmod(angle, TAU) / TAU * _edge_samples
	var i := int(t) % _edge_samples
	var j := (i + 1) % _edge_samples
	return lerpf(_edge[i], _edge[j], t - floor(t))


## 铺路：一条贴着岛缘内侧的**环岛小路** + 三条通向岛心的**支路**。
##
## 环岛路跟着岛缘走（半径 = 岛缘 − RING_INSET），所以不管岛是什么形状，
## 路都稳稳待在陆地上；半径上再叠一点噪声，路缘就不会是一个死板的圆。
func _build_paths() -> void:
	_paths.clear()
	_path_half_w.clear()
	# 环 A：外圈，围墙外面那条带子
	_paths.append(_ring_path(RING_OUTER_INSET))
	_path_half_w.append(RING_HALF_W)
	# 环 B：内圈，围墙里面
	_paths.append(_ring_path(RING_MID_INSET))
	_path_half_w.append(RING_HALF_W)
	# 辐条：从外圈穿过围墙接到内圈
	for k in SPOKE_ANGLES.size():
		_paths.append(_spoke_path(float(SPOKE_ANGLES[k])))
		_path_half_w.append(SPOKE_HALF_W)


## 一整圈环路（跟着岛缘走，半径 = 岛缘 − inset，再叠一点噪声起伏）。
func _ring_path(inset: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	for i in 192:
		var a := TAU * float(i) / 192.0
		out.append(Vector2(cos(a), sin(a)) * _ring_radius(a, inset))
	return out


## 一条辐条：沿半径从外圈笔直走到内圈（穿过围墙）。
func _spoke_path(deg: float) -> PackedVector2Array:
	var a := deg_to_rad(deg)
	var r_outer := _ring_radius(a, RING_OUTER_INSET)
	var r_mid := _ring_radius(a, RING_MID_INSET)
	var out := PackedVector2Array()
	var steps := maxi(2, int(absf(r_outer - r_mid) / 0.5))
	for i in steps + 1:
		var t := float(i) / float(steps)
		out.append(Vector2(cos(a), sin(a)) * lerpf(r_outer, r_mid, t))
	return out


## 环岛路在某个角度上的半径：跟着岛缘走，再叠一点噪声起伏。
##
## 恐龙巡逻的路线也用它 —— 路和巡逻线是同一条，恐龙不会跑到没路的林子里。
func _ring_radius(angle: float, inset: float) -> float:
	var wobble := _density_noise.get_noise_2d(cos(angle) * 5.0, sin(angle) * 5.0) * 1.2
	return maxf(6.0, _edge_at(angle) - inset + wobble)


## 外圈半径（巡逻路线常用）。
func _outer_radius(angle: float) -> float:
	return _ring_radius(angle, RING_OUTER_INSET)


## 内圈半径。
func _mid_radius(angle: float) -> float:
	return _ring_radius(angle, RING_MID_INSET)


## 点到最近一条路中心线的距离，以及那条路的半宽。
func _path_distance(p: Vector2) -> float:
	var best := INF
	for path in _paths:
		for i in range(1, path.size()):
			var d := _point_segment_distance(p, path[i - 1], path[i])
			if d < best:
				best = d
	return best


## 路面半宽（取最近的一条路）。
func _path_half_width_at(p: Vector2) -> float:
	var best := INF
	var best_w := RING_HALF_W
	for idx in _paths.size():
		var path := _paths[idx]
		for i in range(1, path.size()):
			var d := _point_segment_distance(p, path[i - 1], path[i])
			if d < best:
				best = d
				best_w = _path_half_w[idx]
	return best_w


static func _point_segment_distance(p: Vector2, a: Vector2, b: Vector2) -> float:
	var ab := b - a
	var len2 := ab.length_squared()
	if len2 < 0.0001:
		return p.distance_to(a)
	var t := clampf((p - a).dot(ab) / len2, 0.0, 1.0)
	return p.distance_to(a + ab * t)


## 按噪声密度采样出每棵树的位置。
##
## 流程：抖动网格给候选点 → 岛内？→ 不在围墙 / 路上？→ 密度噪声够浓？
## → 坡度够缓？→ 雪线以下？→ 跟别的树 / 恐龙挨太近就丢掉。
##
## 密度阈值不是写死的常数，而是**按分位数算**的：先看这片岛上噪声值的
## 分布，取 [constant FOREST_COVERAGE] 这个分位当"林线"。这样不管噪声
## 分布怎么变，"岛上有多大比例是林子"都是可控的（岛小一圈、噪声换了种子，
## 树的密度不会跟着乱跳）。
##
## 整个过程**没有随机数流**：抖动、抽签都用位置哈希
## （见 [method _hash_rand]）。这样改一个参数不会把整片林子重新洗牌，
## 树的棵数也稳定可预期。
func _generate_trees(dinos: Array) -> Dictionary:
	var short: Array = []
	var tall: Array = []
	var placed: Array[Vector2] = []
	var cell_count := int(ceil(GRID_R * 2.0 / CELL))
	# 拒绝原因计数（调试用）
	var reject := {"outside": 0, "wall": 0, "path": 0, "ground": 0,
		"snow": 0, "slope": 0, "close": 0, "rock": 0, "dino": 0, "ok": 0}
	var _slopes := PackedFloat32Array()

	# ---- 第一遍：收候选点 ----
	var candidates: Array = []
	var densities := PackedFloat32Array()
	for gz in range(-cell_count, cell_count):
		for gx in range(-cell_count, cell_count):
			var x := (gx + _hash_rand(gx, gz, SALT_JITTER)) * CELL
			var z := (gz + _hash_rand(gx, gz, SALT_JITTER + 1)) * CELL
			var p := Vector2(x, z)
			var r := p.length()
			if r > GRID_R:
				continue
			# 岛缘以内才种树
			var edge_r := _edge_at(atan2(z, x))
			if r > edge_r - EDGE_MARGIN:
				reject["outside"] += 1
				continue
			# 园区围墙那一圈留出空地，别让树从残墙里长出来
			if absf(r - (edge_r - WALL_INSET)) < WALL_CLEAR:
				reject["wall"] += 1
				continue
			# 路面不长树（留一点随机余量，让路缘不是一把尺子切出来的）
			var path_d := _path_distance(p)
			if path_d < _path_half_width_at(p) + _hash_rand(gx, gz, SALT_PATH) * 0.5:
				reject["path"] += 1
				continue
			# 贴地
			var y := _ground(x, z)
			if y == -INF:
				reject["ground"] += 1
				continue
			# 雪线以上不长树
			if y > SNOW_LINE:
				reject["snow"] += 1
				continue
			# 坡度
			var slp := _slope_at(x, z)
			_slopes.append(slp)
			if slp > MAX_SLOPE:
				reject["slope"] += 1
				continue
			# 石头底下不长树
			var on_rock := false
			for rock in _rocks:
				var rp: Vector2 = rock[0]
				var rr: float = rock[1]
				if p.distance_squared_to(rp) < (rr + 0.8) * (rr + 0.8):
					on_rock = true
					break
			if on_rock:
				reject["rock"] += 1
				continue
			# 恐龙脚下 / 身边留空，别把树种在恐龙身上
			var on_dino := false
			for d in dinos:
				var dp := Vector2((d["transform"] as Array)[9], (d["transform"] as Array)[11])
				var keep_out := float(d["keep_out"])
				if p.distance_squared_to(dp) < keep_out * keep_out:
					on_dino = true
					break
			if on_dino:
				reject["dino"] += 1
				continue
			candidates.append([p, y])
			densities.append(_density_at(x, z))

	if candidates.is_empty():
		return {"short": short, "tall": tall}

	# ---- 林线：按分位数取 ----
	var sorted := densities.duplicate()
	sorted.sort()
	var idx := clampi(int(floor((1.0 - FOREST_COVERAGE) * float(sorted.size()))),
		0, sorted.size() - 1)
	# 林线不能低于恐龙活动区，否则恐龙会被种在树里
	var floor_value := maxf(sorted[idx], DINO_CLEARING)
	var span := maxf(1.0 - floor_value, 0.0001)

	# ---- 第二遍：按密度从浓到稀依次决定种不种 ----
	# 先排密度再种：浓的地方先占位，稀的地方只能填空，
	# 这样"林子中心更密、空地更疏"的层次是稳定的。
	var order: Array = []
	for i in candidates.size():
		order.append(i)
	order.sort_custom(func(a: int, b: int) -> bool:
		return densities[a] > densities[b])
	for i in order:
		var entry: Array = candidates[i]
		var p: Vector2 = entry[0]
		var y: float = entry[1]
		var density := clampf((_density_at(p.x, p.y) - floor_value) / span, 0.0, 1.0)
		if density <= 0.0:
			continue
		if _hash_rand(int(p.x * 16.0), int(p.y * 16.0), SALT_ACCEPT) > minf(1.0, density * DENSITY_GAIN):
			continue
		# 跟别的树别贴太近
		var too_close := false
		for q in placed:
			if p.distance_squared_to(q) < MIN_TREE_GAP * MIN_TREE_GAP:
				too_close = true
				break
		if too_close:
			reject["close"] += 1
			continue
		placed.append(p)
		reject["ok"] += 1

		# 高矮：款式噪声决定，两种树成片交错
		var is_tall := _variant_noise.get_noise_2d(p.x, p.y) > VARIANT_THRESHOLD
		var hx := int(p.x * 16.0)
		var hz := int(p.y * 16.0)
		var scale := lerpf(TREE_SCALE_MIN, TREE_SCALE_MAX,
			_hash_rand(hx, hz, SALT_SCALE))
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

	# 下面两行是调参用的诊断信息：候选点被谁拒了、林线在哪、坡度 / 密度分布长什么样
	print("  候选统计: ", reject, " 林线=%.3f" % floor_value)
	_slopes.sort()
	if _slopes.size() > 0:
		print("  坡度分布 p25=%.2f p50=%.2f p75=%.2f p90=%.2f max=%.2f" % [
			_slopes[int(_slopes.size() * 0.25)], _slopes[int(_slopes.size() * 0.5)],
			_slopes[int(_slopes.size() * 0.75)], _slopes[int(_slopes.size() * 0.9)],
			_slopes[_slopes.size() - 1]])
	if sorted.size() > 0:
		print("  密度分布 min=%.3f p25=%.3f p50=%.3f p75=%.3f max=%.3f" % [
			sorted[0], sorted[int(sorted.size() * 0.25)], sorted[int(sorted.size() * 0.5)],
			sorted[int(sorted.size() * 0.75)], sorted[sorted.size() - 1]])
	return {"short": short, "tall": tall}


## 位置哈希 → 0..1 的伪随机数。
##
## 用它代替随机数流：同一个格子永远得到同一个抖动、同一个抽签结果，
## 所以改一个参数不会把整片林子重新洗牌（树的棵数也就稳定了）。
func _hash_rand(ix: int, iz: int, salt: int) -> float:
	var h := (ix * 73856093) ^ (iz * 19349663) ^ (salt * 83492791)
	h = (h ^ (h >> 13)) * 1274126177
	h = h ^ (h >> 16)
	return float(h & 0xFFFFFF) / float(0xFFFFFF)


## 密度场：0（空地）– 1（最密的林子）。
##
## 噪声本身在 -1..1，先映射到 0..1，再用一个偏软的斜坡把中间段拉开 ——
## 于是岛上有大片留白的空地（恐龙和玩家活动的地方），也有几团特别密的林子。
func _density_at(x: float, z: float) -> float:
	var v := (_density_noise.get_noise_2d(x, z) + 1.0) * 0.5
	# 细噪声打散边界，避免出现一条一条的等值线
	var fine := (_density_noise.get_noise_2d(x * 3.1 + 41.0, z * 3.1 - 17.0) + 1.0) * 0.5
	v = v * 0.82 + fine * 0.18
	return clampf((v - 0.26) / 0.36, 0.0, 1.0)


## 把恐龙摆好，并给每只烘一条**巡逻路线**。
##
## 路线 = 环岛小路绕一圈（路面上不长树，恐龙走在路上没人挡），
## 中间有一处往林子里凹进去 —— 恐龙会一头扎进香蕉林巡一圈再回到路上。
##
## 每只恐龙的凹进去的位置和深度都不一样，所以几只恐龙不会挤在同一个地方。
func _place_dinosaurs() -> Array:
	var out: Array = []
	var used: Array[Vector2] = []
	var total := 0
	for spec in DINOS:
		total += int(spec[2])
	var index := 0

	for spec in DINOS:
		var dino_name := String(spec[0])
		var scene_path := String(spec[1])
		var count := int(spec[2])
		var half_len := float(spec[3]) * 0.5
		for i in count:
			# 路线相位错开：几只恐龙分布在回路的不同位置，不会叠在一起
			var phase := TAU * float(index) / float(maxi(1, total))
			var circuit := int(DINO_CIRCUITS[index % DINO_CIRCUITS.size()])
			var route := _pick_route(circuit, phase, half_len, used)
			if route.size() < 2:
				push_warning("找不到能站下的回路，跳过一只 %s" % dino_name)
				index += 1
				continue
			var start := route[0]
			used.append(Vector2(start.x, start.z))
			# 朝向 = 路线前进方向
			var dir := route[1] - route[0]
			dir.y = 0.0
			var yaw := atan2(dir.x, dir.z) if dir.length_squared() > 0.0001 else 0.0
			var xf := Transform3D(Basis(Vector3.UP, yaw), start)
			out.append({
				"name": "%s_%02d" % [dino_name, i],
				"scene": scene_path,
				"transform": _to_array(xf),
				"route": _route_to_array(route),
				# 这只恐龙周围多大的范围内不种树
				"keep_out": half_len * 0.45 + 1.2,
			})
			index += 1
	return out


## 给一只恐龙挑回路：先在指定回路上找一个"它站得下"的起点，
## 找不到就退到内圈（内圈离崖边最远，大个子也站得下）。
##
## 大个子（霸王龙、蜥脚龙）站不进外圈 —— 它们一半身子会悬在崖外。
func _pick_route(circuit: int, phase: float, half_len: float,
		used: Array[Vector2]) -> PackedVector3Array:
	for candidate: int in [circuit, 1]:
		var route := _patrol_route(candidate, phase)
		for offset in route.size():
			var spot := Vector2(route[offset].x, route[offset].z)
			if not _spot_is_ok(spot, half_len, used):
				continue
			# 从这儿起步：把路线转一圈，起点挪到 offset
			var rotated := PackedVector3Array()
			for k in route.size():
				rotated.append(route[(offset + k) % route.size()])
			return rotated
	return PackedVector3Array()


## 烘一条巡逻路线：从路网里挑一个**闭合回路**，采成路点。
##
## 回路有三种：
## - 0 = 外圈（围墙外那条带子）；
## - 1 = 内圈（围墙里面）；
## - 2..5 = 四个"格子"：外圈弧 + 辐条（穿围墙）+ 内圈弧 + 辐条回来。
##
## 每只恐龙分一条，所以它们各巡各的圈，不会挤在一条线上。
func _patrol_route(circuit: int, phase: float) -> PackedVector3Array:
	var poly := _circuit_polyline(circuit)
	if poly.size() < 4:
		return PackedVector3Array()
	# 相位错开：同一个回路上几只恐龙别在同一个地方起步
	var start_index := int(round(phase / TAU * float(poly.size()))) % poly.size()
	var pts := PackedVector3Array()
	for i in PATROL_WAYPOINTS:
		var idx := (start_index + int(round(float(i) * float(poly.size()) / float(PATROL_WAYPOINTS)))) % poly.size()
		var p := _walkable_point(poly[idx])
		# 离崖边太近就把路点往回收 —— 恐龙在崖边走容易掉下去
		var a := atan2(p.y, p.x)
		var safe_r := _edge_at(a) - PATROL_EDGE_MARGIN
		if p.length() > safe_r:
			p = Vector2(cos(a), sin(a)) * safe_r
		var y := _ground(p.x, p.y)
		if y == -INF:
			y = 0.0
		pts.append(Vector3(p.x, y, p.y))
	return pts


## 某个回路的折线（二维，首尾相接）。
func _circuit_polyline(circuit: int) -> PackedVector2Array:
	if circuit == 0:
		return _paths[0]          # 外圈
	if circuit == 1:
		return _paths[1]          # 内圈
	return _cell_loop((circuit - 2) % SPOKE_ANGLES.size())


## 一个"格子"：外圈弧 → 辐条 → 内圈弧 → 辐条回来（闭合）。
func _cell_loop(k: int) -> PackedVector2Array:
	var n := SPOKE_ANGLES.size()
	var a0 := float(SPOKE_ANGLES[k])
	var a1 := float(SPOKE_ANGLES[(k + 1) % n])
	var out := PackedVector2Array()
	for p in _ring_arc(0, a0, a1):
		out.append(p)
	for p in _paths[2 + ((k + 1) % n)]:      # 辐条：外 → 内
		out.append(p)
	for p in _ring_arc(1, a1, a0):
		out.append(p)
	var back: PackedVector2Array = _paths[2 + k]   # 辐条：内 → 外
	for i in range(back.size() - 1, -1, -1):
		out.append(back[i])
	return out


## 截取环路从 from_deg 到 to_deg 的一段（逆时针，跨 360 也没问题）。
func _ring_arc(path_index: int, from_deg: float, to_deg: float) -> PackedVector2Array:
	var path: PackedVector2Array = _paths[path_index]
	var n := path.size()
	var i0 := int(round(fposmod(from_deg, 360.0) / 360.0 * float(n))) % n
	var i1 := int(round(fposmod(to_deg, 360.0) / 360.0 * float(n))) % n
	var out := PackedVector2Array()
	var i := i0
	var guard := 0
	while guard <= n:
		out.append(path[i % n])
		if i % n == i1:
			break
		i += 1
		guard += 1
	return out


## 把一个点挪到"走得了的地面"上：地面太高（爬到山脚了）就沿半径往外拉。
func _walkable_point(p: Vector2) -> Vector2:
	var a := atan2(p.y, p.x)
	var r := p.length()
	for _i in 80:
		var y := _ground(p.x, p.y)
		if y == -INF:
			r -= 0.5
		elif y > PATROL_MAX_Y:
			r += 0.5
		else:
			return p
		p = Vector2(cos(a), sin(a)) * maxf(4.0, r)
	return p


## 这个位置能不能站下一只恐龙（不在崖边、地面够平、离别的恐龙够远）。
func _spot_is_ok(spot: Vector2, half_len: float, used: Array[Vector2]) -> bool:
	var a := atan2(spot.y, spot.x)
	if spot.length() + half_len + 1.0 > _edge_at(a) - 1.0:
		return false
	for u in used:
		if spot.distance_squared_to(u) < DINO_GAP * DINO_GAP:
			return false
	return true


## 给恐龙找一块空地：不在路边、密度低、跟别的恐龙够远、地面够平。
func _find_dino_spot(half_len: float, used: Array[Vector2]) -> Vector2:
	for attempt in 6000:
		var a := _rng.randf_range(0.0, TAU)
		var r := _rng.randf_range(6.0, 34.0)
		var p := Vector2(cos(a), sin(a)) * r
		# 整个身子都要留在岛上：恐龙有一半体长会伸出去，
		# 站在岛缘上会让脖子 / 尾巴悬在崖外。
		if r + half_len + 1.0 > _edge_at(a) - 1.0:
			continue
		# 别站在路面上：离**路边**留一点余量就够了
		var edge_gap := _path_distance(p) - _path_half_width_at(p)
		if edge_gap < DINO_PATH_CLEAR:
			continue
		# 密度要低：得是空地，而不是密林里。
		# 越大的恐龙越能接受"旁边有点树"（它周围一圈的树本来就会被清掉），
		# 小恐龙还是老老实实待在空地上。
		var max_density := 0.30 + clampf(half_len / 10.0, 0.0, 1.0) * 0.25
		if _density_at(p.x, p.y) > max_density:
			continue
		# 跟别的恐龙拉开
		var blocked := false
		for u in used:
			if p.distance_squared_to(u) < DINO_GAP * DINO_GAP:
				blocked = true
				break
		if blocked:
			continue
		# 地面要平
		var y := _ground(p.x, p.y)
		if y == -INF:
			continue
		if _slope_at(p.x, p.y) > 0.34:
			continue
		return p
	return Vector2.INF


## 递归找名字匹配的节点。
func _find_node_named(node: Node, target: String) -> Node:
	if String(node.name) == target:
		return node
	for child in node.get_children():
		var found := _find_node_named(child, target)
		if found != null:
			return found
	return null


# ==============================================================================
# 二、烘成 MultiMesh + 场景
# ==============================================================================

func _bake_from_json() -> void:
	# 边界围栏要用岛缘剖面：只跑了 "bake"（没跑 generate）时这里补一次
	if _edge.is_empty():
		_build_edge_profile()
	var data = JSON.parse_string(FileAccess.get_file_as_string(OUT_JSON))
	if data == null or not data.has("trees"):
		push_error("JSON 读不出来或缺少 trees: " + OUT_JSON)
		quit(1)
		return
	var trees: Dictionary = data["trees"]

	var short_mesh := _merge_tree_mesh(TREE_SHORT)
	var tall_mesh := _merge_tree_mesh(TREE_TALL)
	if short_mesh == null or tall_mesh == null:
		push_error("取不到树的网格")
		quit(1)
		return

	var mm_short := _build_multimesh(short_mesh, trees.get("short", []))
	var mm_tall := _build_multimesh(tall_mesh, trees.get("tall", []))
	ResourceSaver.save(mm_short, RES_SHORT)
	ResourceSaver.save(mm_tall, RES_TALL)

	var root_node := Node3D.new()
	root_node.name = "IslandVegetation"
	root_node.set_script(load(VEGETATION_SCRIPT))

	var trees_node := Node3D.new()
	trees_node.name = "Trees"
	root_node.add_child(trees_node)
	trees_node.owner = root_node

	var mmi_short := MultiMeshInstance3D.new()
	mmi_short.name = "ShortTrees"
	mmi_short.multimesh = load(RES_SHORT)
	mmi_short.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	trees_node.add_child(mmi_short)
	mmi_short.owner = root_node

	var mmi_tall := MultiMeshInstance3D.new()
	mmi_tall.name = "TallTrees"
	mmi_tall.multimesh = load(RES_TALL)
	mmi_tall.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	trees_node.add_child(mmi_tall)
	mmi_tall.owner = root_node

	var ps := PackedScene.new()
	if ps.pack(root_node) != OK:
		push_error("pack 失败")
		quit(1)
		return
	if ResourceSaver.save(ps, OUT_TSCN) != OK:
		push_error("保存场景失败: " + OUT_TSCN)
		quit(1)
		return

	# ---- 恐龙：单独一个场景，跟树解耦 ----
	var dino_root := Node3D.new()
	dino_root.name = "IslandDinosaurs"
	_build_boundary(dino_root)
	var index := 0
	for entry in data.get("dinosaurs", []):
		# 每种恐龙一个自己的场景（components/vegetation/dinosaur/），
		# 场景里已经带好模型、体型、碰撞和 AI；这里只摆位置 + 塞巡逻路线。
		var inst: Node3D = (load(String(entry["scene"])) as PackedScene).instantiate()
		inst.name = String(entry["name"])
		inst.transform = _to_transform(entry["transform"])
		# 路线设在**实例根**（身体）上：Godot 的场景实例化只允许覆写实例根的属性。
		inst.set("route", _route_from_array(entry.get("route", [])))
		dino_root.add_child(inst)
		inst.owner = dino_root
		index += 1
	var dps := PackedScene.new()
	if dps.pack(dino_root) != OK:
		push_error("pack 恐龙场景失败")
		quit(1)
		return
	if ResourceSaver.save(dps, OUT_DINOS) != OK:
		push_error("保存恐龙场景失败: " + OUT_DINOS)
		quit(1)
		return

	print("BAKED %s" % OUT_TSCN)
	print("  矮树 %d 棵 / 高树 %d 棵" % [mm_short.instance_count, mm_tall.instance_count])
	print("  draw call: 2 个 MultiMesh × 2 个表面 = 4")
	print("BAKED %s" % OUT_DINOS)
	print("  恐龙 %d 只（各自一个场景 + 一条巡逻路线）" % index)


## 给恐龙围一圈**边界围栏**：岛缘内 1.5 m 处一圈隐形矮墙。
##
## 浮空岛的边缘就是悬崖，恐龙在崖边走很容易掉下去（掉下去会被送回起点，
## 但看起来是"瞬移"）。这圈围栏只放在**边界层**（层 6），
## 只有恐龙的碰撞掩码里有它 —— 玩家照旧可以走到崖边。
func _build_boundary(root: Node3D) -> void:
	var body := StaticBody3D.new()
	body.name = "Boundary"
	body.collision_layer = 32      # boundary
	body.collision_mask = 1
	var shape := BoxShape3D.new()
	shape.size = Vector3(1.0, 5.0, 0.6)     # 沿切向 1 m、高 5 m、厚 0.6 m
	# 先挂到 root 上，再往里加形状 —— owner 要在节点已经在树上时设才存得进场景
	root.add_child(body)
	body.owner = root
	const SEGMENTS := 96
	for i in SEGMENTS:
		var a := TAU * float(i) / float(SEGMENTS)
		var r := _edge_at(a) - BOUNDARY_INSET
		var p := Vector2(cos(a), sin(a)) * r
		var y := _ground(p.x, p.y)
		if y == -INF:
			continue
		var col := CollisionShape3D.new()
		col.name = "Shape_%03d" % i
		col.shape = shape
		# 盒子沿**切线**摆：角度 a 处的切线是 (-sin a, cos a)，对应 yaw = -a - 90°
		col.transform = Transform3D(Basis(Vector3.UP, -a - PI * 0.5),
			Vector3(p.x, y + 2.0, p.y))
		# 段的长度按弧长算，免得圈上有缝
		col.scale = Vector3(TAU * r / float(SEGMENTS) + 0.4, 1.0, 1.0)
		body.add_child(col)
		col.owner = root      # 不设 owner 的话，pack 的时候子节点会被丢掉


## 把 GLB 里的多个网格**合并成一份 ArrayMesh**（每个表面保留自己的材质）。
##
## 为什么：MultiMesh 只能挂一份网格，而香蕉树是"叶片 + 假茎"两个网格。
## 合并之后一次实例变换就能同时带动叶片和假茎，不会走散；
## 而且一个 MultiMesh 就能画完整棵树（2 个表面 = 2 个 draw call）。
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
		mm.custom_aabb = AABB(Vector3(-46.0, -3.0, -46.0), Vector3(92.0, 26.0, 92.0))
	return mm


# ==============================================================================
# 三、工具
# ==============================================================================

## 物理状态是不是稳定了：同一批探针连续两轮量出来的地面高度完全一样才算。
##
## 为什么要这个：地形碰撞是 116 块共享同一份三角面的 [CollisionShape3D]，
## 物理服务器第一次查询时才建 BVH，早到的射线会漏掉一部分地形 —— 量出来的
## 地面高度偏低，树的棵数、恐龙的落点全都会跟着飘。光是"等够物理帧"不
## 保险（实测同样等 240 帧，脚本改过之后第一次跑还是不稳），所以直接
## 检查"结果有没有收敛"。
func _physics_settled() -> bool:
	var points := PackedVector2Array()
	for i in 128:
		var a := TAU * float(i) / 128.0
		for r in [8.0, 13.0, 18.0, 23.0, 28.0, 33.0]:
			points.append(Vector2(cos(a) * float(r), sin(a) * float(r)))
	var prev := PackedFloat32Array()
	for p in SETTLE_MAX_PASSES:
		var cur := PackedFloat32Array()
		for pt in points:
			cur.append(_ground(pt.x, pt.y))
		if p > 0 and cur == prev:
			return true
		prev = cur
	push_warning("物理状态在 %d 轮内没有收敛，地面高度可能不准" % SETTLE_MAX_PASSES)
	return false


## 某点正下方的地面高度；打不到返回 -INF。
func _ground(x: float, z: float) -> float:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, 60.0, z), Vector3(x, -40.0, z))
	var hit := root.world_3d.direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y


## 某点的坡度（米/米）：用前后左右各 [constant SLOPE_BASELINE] m 的地面高度差。
##
## 基线取 2 m 而不是 1 m：草地是许多块圆地形拼起来的，接缝处有半米级的落差，
## 1 m 基线上量出来的是"接缝"而不是"坡"，会把一大片好地误判成陡坡。
func _slope_at(x: float, z: float) -> float:
	var h0 := _ground(x, z)
	if h0 == -INF:
		return 99.0
	var hx := _ground(x + SLOPE_BASELINE, z)
	var hz := _ground(x, z + SLOPE_BASELINE)
	var s := 0.0
	if hx != -INF:
		s = maxf(s, absf(hx - h0))
	if hz != -INF:
		s = maxf(s, absf(hz - h0))
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
