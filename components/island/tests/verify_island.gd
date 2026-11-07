extends SceneTree
## 低模岛组件自检。
##
## 运行方式（在项目根目录执行）：
## [codeblock]
## /Applications/Godot.app/Contents/MacOS/Godot --path . \
##     --script res://components/island/tests/verify_island.gd
## [/codeblock]
## 全部通过时退出码为 0，否则为 1。
##
## ⚠️ **不要加 `--headless`**：地形和草石都是 MultiMesh，实例变换存在 RenderingServer
## 里；headless 的 dummy 渲染器读出来全是单位矩阵，"贴地"和"地形碰撞"那几项会误报。
##
## 覆盖：场景结构、台面高度、山体尺度、碰撞是否补齐、石头/草是否贴在地面上、
## 环境与相机是否可用。碰撞由 island.gd 在 _ready 里动态补，所以要等几帧。

const SCENE_PATH: String = "res://components/island/island.tscn"
## 碰撞层：地面。
const LAYER_WORLD := 1
## 碰撞层：植被（香蕉树干）。
const LAYER_VEGETATION := 2
## 碰撞层：建筑（围墙 / 大门）。
const LAYER_STRUCTURE := 4
## 碰撞层：杂物（石头）。
const LAYER_PROP := 8
const SETTLE_FRAMES: int = 12

var _checks: int = 0
var _failures: int = 0
var _frames: int = 0
var _ran: bool = false
var _scene: Node3D
## 第二阶段：跑一会儿之后再回来，看恐龙是不是真的在动。
var _phase: int = 0
## 第一阶段记下的恐龙位置。
var _dino_start: Dictionary = {}


func _initialize() -> void:
	_scene = load(SCENE_PATH).instantiate()
	get_root().add_child(_scene)


func _process(_delta: float) -> bool:
	if _ran:
		return true
	_frames += 1
	if _phase == 0:
		if _frames < SETTLE_FRAMES:
			return false
		_dino_start = _dino_positions()
		_run_all()
		_phase = 1
		return false
	# 再跑 2 秒物理，看恐龙有没有真的在巡逻
	if _frames < SETTLE_FRAMES + 120:
		return false
	_ran = true
	_test_dino_patrol()
	print("=== 低模岛检查项 %d，失败 %d ===" % [_checks, _failures])
	print("全部通过 ✅" if _failures == 0 else "存在失败 ❌")
	quit(1 if _failures > 0 else 0)
	return true


## 记下每只恐龙现在的位置。
func _dino_positions() -> Dictionary:
	var out: Dictionary = {}
	var dinos := _scene.get_node_or_null("Dinosaurs")
	if dinos == null:
		return out
	for dino in dinos.get_children():
		out[dino.name] = (dino as Node3D).global_position
	return out


## 恐龙必须真的在动（不是站桩），而且得是**沿着自己的路线**在动。
func _test_dino_patrol() -> void:
	_section("恐龙巡逻")
	var dinos := _scene.get_node_or_null("Dinosaurs")
	if dinos == null:
		_check(false, "缺少 Dinosaurs 节点")
		return
	var moved := 0
	var total := 0
	for dino in dinos.get_children():
		if not (dino is Node3D):
			continue
		total += 1
		var start: Vector3 = _dino_start.get(dino.name, (dino as Node3D).global_position)
		var now := (dino as Node3D).global_position
		if start.distance_to(now) > 0.5:
			moved += 1
		else:
			print("    [dbg] %s 没动：起点 %s 现在 %s" % [dino.name, str(start), str(now)])
	_check(total > 0 and moved == total,
		"有恐龙没有在巡逻（%d/%d 只在动）" % [moved, total])


func _run_all() -> void:
	_test_structure()
	_test_heights()
	_test_collision()
	_test_scatter_on_ground()
	_test_vegetation()
	_test_patrol_network()
	_test_tree_blocks_sight()
	_test_presentation()


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		print("  [FAIL] ", message)


func _section(title: String) -> void:
	print("-- ", title)


## ---------------- 1. 场景结构 ----------------
func _test_structure() -> void:
	_section("场景结构")
	_check(_scene != null, "场景实例化失败")
	if _scene == null:
		return
	var world_env := _scene.get_node_or_null("WorldEnvironment") as WorldEnvironment
	var sun := _scene.get_node_or_null("Sun") as DirectionalLight3D
	var camera := _scene.get_node_or_null("PreviewCamera") as Camera3D
	var base := _scene.get_node_or_null("IslandBase")
	var ground := _scene.get_node_or_null("Ground")
	var mountain := _scene.get_node_or_null("Mountain")
	var scatter := _scene.get_node_or_null("Scatter")
	var vegetation := _scene.get_node_or_null("Vegetation")
	_check(world_env != null, "缺少 WorldEnvironment")
	_check(sun != null, "缺少 Sun")
	_check(camera != null and camera.current, "缺少当前相机 PreviewCamera")
	_check(base != null and base.get_child_count() == 1, "缺少岛屿本体实例")
	_check(ground != null, "缺少 Ground")
	_check(mountain != null and mountain.get_node_or_null("LowMountain") != null, "缺少山体实例")
	_check(scatter != null, "缺少 Scatter")
	if scatter == null:
		return
	var rocks := scatter.get_node_or_null("Rocks")
	var grass := scatter.get_node_or_null("Grass")
	_check(rocks != null and _instance_count(rocks) >= 40,
		"石头数量不足（应 >= 40，实际 %d）" % _instance_count(rocks))
	_check(grass != null and _instance_count(grass) >= 400,
		"草数量不足（应 >= 400，实际 %d）" % _instance_count(grass))
	# 散布合并成 MultiMesh 之后，节点数应该只有几十个 —— 一旦有人把
	# "每个草一个节点"的旧做法加回来，这里立刻报警。
	_check(scatter.get_child_count() <= 40,
		"Scatter 子节点太多（%d），草石应该走 MultiMesh" % scatter.get_child_count())
	var patches := ground.find_children("*", "MeshInstance3D", true, false).size() if ground else 0
	_check(patches == 0, "Ground 下又出现了逐块的地形 MeshInstance3D（%d 个）" % patches)
	# 116 块地形合成 1 个 MultiMesh：节点编号、`_ready()`、draw call 都只算一次。
	# 一旦有人把"每块地形一个实例"的旧做法加回来，下面几条立刻报警。
	var terrain := ground.get_node_or_null("Terrain") if ground else null
	_check(terrain is MultiMeshInstance3D, "缺少 Ground/Terrain（MultiMeshInstance3D）")
	_check(ground != null and ground.get_child_count() <= 4,
		"Ground 子节点太多（%d），地形应该走 MultiMesh" % (ground.get_child_count() if ground else -1))
	if terrain is MultiMeshInstance3D and (terrain as MultiMeshInstance3D).multimesh != null:
		var instances := (terrain as MultiMeshInstance3D).multimesh.instance_count
		_check(instances >= 100, "地形块数量不足（应 >= 100，实际 %d）" % instances)
		_check((terrain as MultiMeshInstance3D).multimesh.mesh != null, "地形的 MultiMesh 没有网格")

	# 香蕉树林：必须是 MultiMesh（几百棵树不能变成几百个节点）
	_check(vegetation != null, "缺少 Vegetation（香蕉树林 + 恐龙）")
	if vegetation != null:
		_check(vegetation.get_child_count() <= 6,
			"Vegetation 子节点太多（%d），树应该走 MultiMesh" % vegetation.get_child_count())
		_check(_instance_count(vegetation.get_node_or_null("Trees")) >= 200,
			"树的数量不足（应 >= 200，实际 %d）" % _instance_count(vegetation.get_node_or_null("Trees")))


## ---------------- 2. 高度 / 尺度 ----------------
func _test_heights() -> void:
	_section("高度 / 尺度")
	var mountain := _scene.get_node_or_null("Mountain")
	if mountain != null:
		# 用**真实顶点范围**，不用 get_aabb()：MeshInstance 的 AABB 是网格包围盒
		# 整体套上旋转后的结果（还含 LOD 余量），会把山脚量宽 4~5 m。
		var box := _vertex_aabb(mountain)
		_check(box.size.y > 17.5 and box.size.y < 19.5,
			"山体总高异常：%.2f m（含水下裙边，预期约 18.6 m）" % box.size.y)
		_check(box.end.y > 16.5 and box.end.y < 19.5,
			"山体主峰高度异常：峰顶 %.2f m（预期约 17.8 m）" % box.end.y)
		# 山是**故意偏心**的（正中会显得像个同心圆靶子），但必须仍稳稳落在岛上：
		# 既不能偏回中心，也不能偏到把山脚推到岛外。
		var c := box.get_center()
		var off := Vector2(c.x, c.z).length()
		_check(off > 6.0, "山体又跑回岛中央了（偏移 %.1f m，应 > 6 m）" % off)
		# 山脚不能悬在岛外：山体（真实顶点范围）要整个落在岛体范围里（留 1 m 余量）。
		var base := _vertex_aabb(_scene.get_node_or_null("IslandBase"))
		_check(base.size.x > 0.0
				and box.position.x > base.position.x + 1.0 and box.end.x < base.end.x - 1.0
				and box.position.z > base.position.z + 1.0 and box.end.z < base.end.z - 1.0,
			"山脚超出岛体范围：山体 x[%.1f,%.1f] z[%.1f,%.1f]，岛体 x[%.1f,%.1f] z[%.1f,%.1f]" % [
				box.position.x, box.end.x, box.position.z, box.end.z,
				base.position.x, base.end.x, base.position.z, base.end.z])
		_check(box.position.y < 0.5, "山体底座没有落在地面上（y=%.2f）" % box.position.y)

	# 岛屿台面：山体外侧、草地边缘的几个点都应该能向下打到地面
	# （巡逻中的恐龙正好站在探测点上的话，射线会打在恐龙身上，所以要排除）
	var probes := [Vector2(24, 0), Vector2(-24, 0), Vector2(0, 24), Vector2(0, -24),
		Vector2(17, 17), Vector2(-17, -17)]
	var hits := 0
	for p in probes:
		var ground_y := _ground_height(p, 50.0, _dino_rids())
		if ground_y > -0.5 and ground_y < 2.2:
			hits += 1
	_check(hits == probes.size(), "岛屿台面不完整（%d/%d 个探测点打到地面）" % [hits, probes.size()])


## ---------------- 3. 碰撞 ----------------
func _test_collision() -> void:
	_section("碰撞")
	var ground := _scene.get_node_or_null("Ground")
	var mountain := _scene.get_node_or_null("Mountain")
	var rock_body := _scene.get_node_or_null("Scatter/RockCollision")
	_check(_has_static_bodies(ground), "草地地形块没有补齐碰撞")
	_check(_has_static_bodies(mountain), "山体没有补齐碰撞")
	# 地形是 MultiMesh：island.gd 补 **一个** StaticBody3D + 每个实例一个
	# CollisionShape3D，所有形状共享同一份三角面数据（116 份 → 1 份）。
	var terrain := ground.get_node_or_null("Terrain") if ground else null
	if terrain is MultiMeshInstance3D and (terrain as MultiMeshInstance3D).multimesh != null:
		var instances := (terrain as MultiMeshInstance3D).multimesh.instance_count
		var terrain_body := terrain.get_node_or_null("StaticBody3D")
		_check(terrain_body is StaticBody3D, "地形没有补齐碰撞（缺 Ground/Terrain/StaticBody3D）")
		if terrain_body is StaticBody3D:
			var shapes := (terrain_body as StaticBody3D).get_child_count()
			_check(shapes == instances, "地形碰撞体数量不对（%d / %d 块）" % [shapes, instances])
			var shared := true
			var first_shape: Shape3D = null
			for child in terrain_body.get_children():
				var collision := child as CollisionShape3D
				if collision == null or collision.shape == null:
					shared = false
					break
				if first_shape == null:
					first_shape = collision.shape
				elif collision.shape != first_shape:
					shared = false
					break
			_check(shared, "地形碰撞没有共享同一份形状（每块各存一份就退化了）")
	# 石头现在由 ground_scatter.gd 用**一个** StaticBody3D + N 个共享凸包
	# CollisionShape3D 补碰撞（MultiMesh 本身不产生碰撞）。
	_check(rock_body is StaticBody3D, "石头没有补齐碰撞（缺 Scatter/RockCollision）")
	if rock_body is StaticBody3D:
		var shapes := (rock_body as StaticBody3D).get_child_count()
		_check(shapes >= 40, "石头碰撞体太少（%d）" % shapes)
	# 岛屿本体的台面由 glb 自带的 `-col` 节点提供碰撞
	var base_body := _scene.get_node_or_null("IslandBase").find_children("*", "StaticBody3D", true, false)
	_check(base_body.size() > 0, "岛屿本体没有碰撞")


## ---------------- 4. 石头 / 草贴地 ----------------
func _test_scatter_on_ground() -> void:
	_section("石头 / 草贴地")
	var rocks := _scene.get_node_or_null("Scatter/Rocks")
	var rock_body := _scene.get_node_or_null("Scatter/RockCollision")
	var excluded: Array[RID] = []
	if rock_body is StaticBody3D:
		excluded.append((rock_body as StaticBody3D).get_rid())
	# 入口大门/围墙也有碰撞体；射线打在上面会误判成"草悬空"，
	# 所以贴地检查里把它们排除掉（贴地检查关心的是地面，不是墙顶）。
	var entrance := _scene.get_node_or_null("ParkPerimeter")
	if entrance != null:
		for node in entrance.find_children("*", "StaticBody3D", true, false):
			excluded.append((node as StaticBody3D).get_rid())
	# 树干碰撞也要排除：垂直射线会先打在树干侧面 / 顶上，量出来的就不是地面了
	var tree_body := _scene.get_node_or_null("Vegetation/TreeCollision")
	if tree_body is StaticBody3D:
		excluded.append((tree_body as StaticBody3D).get_rid())
	# 恐龙的胶囊也要排除：巡逻中的恐龙正好站在石头上方时，
	# 射线会打在恐龙肚子上，石头就变成"浮空"了
	excluded.append_array(_dino_rids())

	# 草石现在是 MultiMesh，位置要按"实例变换"取，而不是节点 global_position。
	# 山顶/山腰的石头经常落在挑檐下面，垂直射线会先打到上层台地，
	# 所以只对岛屿范围内的石头做严格贴地检查；山体石头只数数量。
	var rock_checked := 0
	var rock_ok := 0
	var mountain_rocks := 0
	for entry in _instances_under(rocks):
		var p: Vector3 = entry[0]
		var on_mountain: bool = entry[1]
		if on_mountain:
			mountain_rocks += 1
			continue
		var y := _ground_height_xz(p.x, p.z, p.y + 4.0, excluded)
		if y == -INF:
			continue
		rock_checked += 1
		if absf(y - p.y) < 0.8:
			rock_ok += 1

	_check(rock_checked > 0 and rock_ok == rock_checked,
		"有石头悬空或陷得太深（%d/%d 贴地）" % [rock_ok, rock_checked])
	_check(mountain_rocks >= 12, "山上的石头太少（%d 块）" % mountain_rocks)

	var grass := _scene.get_node_or_null("Scatter/Grass")
	var all_grass := _instances_under(grass)
	var grass_checked := 0
	var grass_ok := 0
	for i in range(0, all_grass.size(), maxi(1, all_grass.size() / 18)):
		var p: Vector3 = all_grass[i][0]
		var y := _ground_height_xz(p.x, p.z, p.y + 4.0, excluded)
		if y == -INF:
			continue
		grass_checked += 1
		if absf(y - p.y) < 0.35:
			grass_ok += 1

	_check(grass_checked > 0 and grass_ok == grass_checked,
		"有草悬空（%d/%d 贴地）" % [grass_ok, grass_checked])


## ---------------- 5. 香蕉树林 / 恐龙 ----------------
func _test_vegetation() -> void:
	_section("香蕉树林 / 恐龙")
	var vegetation := _scene.get_node_or_null("Vegetation")
	if vegetation == null:
		_check(false, "缺少 Vegetation 节点")
		return
	var trees := vegetation.get_node_or_null("Trees")
	var short_mm := trees.get_node_or_null("ShortTrees") as MultiMeshInstance3D
	var tall_mm := trees.get_node_or_null("TallTrees") as MultiMeshInstance3D
	_check(short_mm != null and tall_mm != null, "缺少 ShortTrees / TallTrees 两个 MultiMesh")
	if short_mm == null or tall_mm == null:
		return
	var short_n := short_mm.multimesh.instance_count
	var tall_n := tall_mm.multimesh.instance_count
	var total := short_n + tall_n
	_check(total >= 200, "树太少了（%d 棵，应 >= 200）" % total)
	# 两种树都要有，而且比例不能太偏（"高矮分布要均匀"）
	_check(short_n >= 40 and tall_n >= 40,
		"高矮款式分布不均（矮 %d / 高 %d）" % [short_n, tall_n])
	var tall_ratio := float(tall_n) / maxf(1.0, float(total))
	_check(tall_ratio > 0.3 and tall_ratio < 0.7,
		"高款占比 %.0f%% 不在 30%%~70%% 之间" % (tall_ratio * 100.0))
	# 树的网格必须是合并过的（叶片 + 假茎两个表面），不是逐块的网格列表
	for mmi in [short_mm, tall_mm]:
		var mm := (mmi as MultiMeshInstance3D).multimesh
		_check(mm.mesh != null and mm.mesh.get_surface_count() == 2,
			"树的网格表面数不对（应 2：叶片 + 假茎）")
		_check(mm.mesh != null and mm.mesh.get_surface_count() == 2
			and mm.mesh.surface_get_material(0) != null
			and mm.mesh.surface_get_material(1) != null,
			"树的表面没有材质")

	# 树贴地：抽样的树必须站在地面上
	var tree_pts := _instances_under(trees)
	# 量树脚下的地面高度时必须排除树干碰撞，否则射线打在树干上
	var excluded: Array[RID] = []
	var tree_body := vegetation.get_node_or_null("TreeCollision")
	if tree_body is StaticBody3D:
		excluded.append((tree_body as StaticBody3D).get_rid())
	# 石头也有碰撞体：射线打在石头上量到的不是地面
	var rock_body := _scene.get_node_or_null("Scatter/RockCollision")
	if rock_body is StaticBody3D:
		excluded.append((rock_body as StaticBody3D).get_rid())
	excluded.append_array(_dino_rids())
	var checked := 0
	var grounded := 0
	for i in range(0, tree_pts.size(), maxi(1, tree_pts.size() / 20)):
		var p: Vector3 = tree_pts[i][0]
		var y := _ground_height_xz(p.x, p.z, p.y + 4.0, excluded)
		if y == -INF:
			continue
		checked += 1
		# 容差 1 m：草地是一块块圆地形拼起来的，射线打在树干半径内最高的那块上，
		# 跟树脚正下方的高差能有半米多。
		if absf(y - p.y) < 1.0:
			grounded += 1
	_check(checked > 0 and grounded == checked,
		"有树悬空或陷进地里（%d/%d 贴地）" % [grounded, checked])

	# 密度 vs 通道：既要"很密"，也要"留出路"
	# 在岛面上撒一圈采样点：既要有大量点被树盖住，也要有相当一部分是空地。
	var covered := 0
	var clear := 0
	var samples := 0
	for radius in [10.0, 16.0, 22.0, 28.0]:
		for i in 72:
			var a := TAU * float(i) / 72.0
			var p := Vector2(cos(a), sin(a)) * float(radius)
			samples += 1
			var nearest := INF
			for q in tree_pts:
				var qp: Vector3 = q[0]
				var d := Vector2(qp.x - p.x, qp.z - p.y).length()
				nearest = minf(nearest, d)
			if nearest < 3.0:
				covered += 1
			elif nearest > 2.2:
				clear += 1
	_check(float(covered) / float(samples) > 0.25,
		"林子不够密（只有 %.0f%% 的采样点被树盖住）" % (100.0 * float(covered) / float(samples)))
	_check(float(clear) / float(samples) > 0.10,
		"没有留出足够的道路 / 空地（只有 %.0f%% 的采样点是空的）"
		% (100.0 * float(clear) / float(samples)))

	# 树干碰撞：MultiMesh 不产生碰撞，运行时必须补上
	_check(tree_body is StaticBody3D, "树干没有补齐碰撞（缺 Vegetation/TreeCollision）")
	if tree_body is StaticBody3D:
		var shapes := (tree_body as StaticBody3D).get_child_count()
		_check(shapes == total, "树干碰撞体数量不对（%d / %d 棵）" % [shapes, total])
		# 两种树各共享一份形状：几百棵树不该有几百份形状数据
		var distinct := {}
		for child in (tree_body as StaticBody3D).get_children():
			var collision := child as CollisionShape3D
			if collision != null and collision.shape != null:
				distinct[collision.shape.get_instance_id()] = true
		_check(distinct.size() <= 2,
			"树干形状没有按款式共享（%d 份，应该只有 2 份）" % distinct.size())

	# 恐龙：数量、脚底贴地、尺寸
	var dinos := _scene.get_node_or_null("Dinosaurs")
	_check(dinos != null, "缺少 Dinosaurs 节点")
	if dinos == null:
		return
	var dino_nodes := dinos.get_children()
	_check(dino_nodes.size() >= 8, "恐龙太少了（%d 只，应 >= 8）" % dino_nodes.size())
	# 恐龙贴地检查同样要排除树干碰撞和围墙：射线打在墙上量到的不是地面
	var dino_excluded: Array[RID] = []
	if tree_body is StaticBody3D:
		dino_excluded.append((tree_body as StaticBody3D).get_rid())
	dino_excluded.append_array(_dino_rids())
	var entrance := _scene.get_node_or_null("ParkPerimeter")
	if entrance != null:
		for node in entrance.find_children("*", "StaticBody3D", true, false):
			dino_excluded.append((node as StaticBody3D).get_rid())
	var dino_ok := 0
	var dino_checked := 0
	for dino in dino_nodes:
		if not (dino is Node3D):
			continue
		var skeleton := _find_skeleton(dino)
		if skeleton == null:
			continue
		dino_checked += 1
		# 用骨骼 / 脚尖的最低点判断有没有浮空或陷进地里
		var lowest := INF
		var points: Array[Vector3] = []
		for i in skeleton.get_bone_count():
			points.append((skeleton.global_transform * skeleton.get_bone_global_pose(i)).origin)
		for child in skeleton.get_children():
			if child is BoneAttachment3D:
				points.append((skeleton.global_transform * (child as Node3D).transform).origin)
		for p in points:
			lowest = minf(lowest, p.y)
		if lowest == INF:
			continue
		var ground_y := _ground_height_xz(dino.global_position.x, dino.global_position.z,
			lowest + 2.0, dino_excluded)
		if ground_y == -INF:
			continue
		# 允许略微陷进地里，不允许浮空
		if lowest - ground_y < 0.8 and lowest - ground_y > -1.6:
			dino_ok += 1
	_check(dino_checked > 0 and dino_ok == dino_checked,
		"有恐龙浮空或陷进地里（%d/%d 贴地）" % [dino_ok, dino_checked])

	# 恐龙是**实心的**：树、围墙都撞得到（树是掩体、围墙是建筑，都该挡路）。
	# 石头**不挡**（最大的也就 5 m，恐龙跨得过去，非要撞只会把巡逻卡住）。
	for dino in dino_nodes:
		if not (dino is CollisionObject3D):
			continue
		var body := dino as CollisionObject3D
		var mask := body.collision_mask
		_check((mask & LAYER_WORLD) != 0,
			"%s 的碰撞掩码里没有地面层（会掉出岛外）" % dino.name)
		_check((mask & LAYER_VEGETATION) != 0,
			"%s 的碰撞掩码里没有植被层（会从树干里穿过去）" % dino.name)
		_check((mask & LAYER_STRUCTURE) != 0,
			"%s 的碰撞掩码里没有建筑层（会从围墙里穿过去）" % dino.name)
		_check((mask & LAYER_PROP) == 0,
			"%s 的碰撞掩码里有杂物层（石头会把巡逻卡住）" % dino.name)
		# 每只恐龙都得有 AI，AI 得有调参表和巡逻路线
		var ai := dino.get_node_or_null("AI")
		_check(ai != null, "%s 没有 AI 节点" % dino.name)
		if ai == null:
			continue
		var route: Variant = body.get("route")
		_check(route is PackedVector3Array and (route as PackedVector3Array).size() >= 8,
			"%s 没有巡逻路线（应 >= 8 个路点）" % dino.name)
		var ai_config: Variant = ai.get("config")
		_check(ai_config != null, "%s 的 AI 没有调参表" % dino.name)
		# 模型的"脸"要对上 Godot 的前方（-Z），否则恐龙会倒着走
		var head := _find_node_named(dino, "Head_end")
		if head is Node3D:
			var local := (dino as Node3D).global_transform.affine_inverse() \
				* (head as Node3D).global_position
			_check(local.z < 0.0,
				"%s 的模型是倒的（吻在局部 +Z，应该在 -Z）" % dino.name)


## ---------------- 6. 巡逻路网 ----------------
##
## 用户要求：树要重新排列，形成**多个回路**让恐龙来回巡逻；围墙要在
## 辐条穿过的角度上留**开口**。这里验三件事：
##  1. 恐龙的每个路点都不被树挡住（树真给恐龙留了通路）；
##  2. 至少有路线**跨内外两圈**（说明路网是连通的多个回路，不是各绕各的小圈）；
##  3. 围墙在辐条角度上确实有开口（没有墙段堵着）。
func _test_patrol_network() -> void:
	_section("巡逻路网")
	var dinos := _scene.get_node_or_null("Dinosaurs")
	if dinos == null:
		_check(false, "缺少 Dinosaurs 节点")
		return
	var trees := _scene.get_node_or_null("Vegetation/Trees")
	var tree_pts := _instances_under(trees)

	# 1. 路点不能被树挡住
	var blocked := 0
	var checked := 0
	for dino in dinos.get_children():
		var route: Variant = (dino as Node3D).get("route")
		if not (route is PackedVector3Array):
			continue
		for p in (route as PackedVector3Array):
			checked += 1
			for t in tree_pts:
				if (t[0] as Vector3).distance_to(p) < 1.2:
					blocked += 1
					break
	_check(checked > 0 and blocked == 0,
		"有 %d / %d 个路点被树挡住（树没给恐龙留出通路）" % [blocked, checked])

	# 2. 路线要跨圈：至少有一条同时走过外圈和内圈
	var crossing := 0
	var loops := 0
	for dino in dinos.get_children():
		var route: Variant = (dino as Node3D).get("route")
		if not (route is PackedVector3Array) or (route as PackedVector3Array).size() < 8:
			continue
		loops += 1
		var rmin := INF
		var rmax := -INF
		for p in (route as PackedVector3Array):
			var r := Vector2(p.x, p.z).length()
			rmin = minf(rmin, r)
			rmax = maxf(rmax, r)
		if rmax - rmin > 5.0:
			crossing += 1
	_check(loops >= 8, "巡逻路线太少（%d 条）" % loops)
	_check(crossing >= 1, "没有一条路线跨越内外两圈（路网没连起来）")

	# 3. 围墙在辐条角度上要有开口
	var walls := _scene.get_node_or_null("ParkPerimeter/Walls")
	if walls == null:
		_check(false, "找不到 ParkPerimeter/Walls")
		return
	var wall_positions: Array[Vector2] = []
	for wall in walls.get_children():
		if wall is Node3D:
			var pos := (wall as Node3D).position
			wall_positions.append(Vector2(pos.x, pos.z))
	# 跟 bake_vegetation.gd 的 SPOKE_ANGLES 一致
	for deg in [30.0, 150.0, 210.0, 330.0]:
		var spoke := deg_to_rad(deg)
		var blocked_by_wall := false
		for p in wall_positions:
			var d := absf(fposmod(atan2(p.y, p.x) - spoke + PI, TAU) - PI)
			if d * p.length() < 3.2:
				blocked_by_wall = true
				break
		_check(not blocked_by_wall,
			"围墙在辐条 %.0f° 的位置没有开口（恐龙穿不过去）" % deg)


## ---------------- 7. 树能挡住恐龙的视线 ----------------
##
## 这是核心玩法：玩家躲在香蕉树后面，恐龙就**看不见**。
## 恐龙的感知（`DinosaurPerception`）是从眼睛往目标胸口打一条射线，
## 打在植被层上就算被挡住 —— 所以这里直接验这条物理事实。
func _test_tree_blocks_sight() -> void:
	_section("树能挡住视线")
	var trees := _scene.get_node_or_null("Vegetation/Trees")
	if trees == null:
		_check(false, "找不到 Vegetation/Trees")
		return
	var tree_pts := _instances_under(trees)
	if tree_pts.is_empty():
		_check(false, "拿不到树的位置")
		return
	# 找一棵"独立"的树：周围 1.5 m 内没有别的树，射线才只会打在它身上
	var chosen := Vector3.ZERO
	var found := false
	for entry in tree_pts:
		var pos: Vector3 = entry[0]
		var isolated := true
		for other in tree_pts:
			var op: Vector3 = other[0]
			if op.distance_to(pos) < 1.5 and not op.is_equal_approx(pos):
				isolated = false
				break
		if isolated:
			chosen = pos
			found = true
			break
	_check(found, "找不到一棵独立的树")
	if not found:
		return
	# 从树的一侧穿到另一侧：中间必须被树干挡住
	var from := chosen + Vector3(2.2, 1.4, 0)
	var to := chosen + Vector3(-2.2, 1.0, 0)
	var query := PhysicsRayQueryParameters3D.create(from, to)
	query.collision_mask = LAYER_VEGETATION
	var hit := get_root().world_3d.direct_space_state.intersect_ray(query)
	_check(not hit.is_empty(),
		"树干没有挡住视线（玩家藏在树后也会被恐龙直接看见）")
	# 对照组：同一高度、但绕开树，射线应该打不到任何植被
	var side_from := chosen + Vector3(2.2, 1.4, 2.6)
	var side_to := chosen + Vector3(-2.2, 1.0, 2.6)
	var query2 := PhysicsRayQueryParameters3D.create(side_from, side_to)
	query2.collision_mask = LAYER_VEGETATION
	var hit2 := get_root().world_3d.direct_space_state.intersect_ray(query2)
	_check(hit2.is_empty(), "对照组也撞到植被了（挑的树不独立）")


## ---------------- 8. 环境 ----------------
func _test_presentation() -> void:
	_section("环境 / 相机")
	var env := (_scene.get_node("WorldEnvironment") as WorldEnvironment).environment
	_check(env.background_mode == Environment.BG_SKY, "背景不是天空")
	_check(env.sky != null and env.sky.sky_material is ProceduralSkyMaterial, "天空材质不是 ProceduralSkyMaterial")
	_check(env.fog_enabled, "没有开启雾")
	_check(env.tonemap_mode == Environment.TONE_MAPPER_FILMIC, "色调映射不是 Filmic")
	var sun := _scene.get_node("Sun") as DirectionalLight3D
	_check(sun.shadow_enabled, "太阳没有开启阴影")
	var camera := _scene.get_node("PreviewCamera") as Camera3D
	_check(is_equal_approx(camera.fov, 50.0), "相机 FOV 不是 50")


## ---------------- 工具 ----------------
## 子树里每个可见几何体（MeshInstance3D / MultiMeshInstance3D）都要挂 StaticBody3D。
func _has_static_bodies(root: Node) -> bool:
	if root == null:
		return false
	var geometry: Array[Node] = []
	geometry.append_array(root.find_children("*", "MeshInstance3D", true, false))
	geometry.append_array(root.find_children("*", "MultiMeshInstance3D", true, false))
	if geometry.is_empty():
		return false
	for node in geometry:
		var found := false
		for child in node.get_children():
			if child is StaticBody3D:
				found = true
				break
		if not found:
			return false
	return true


## 子树里所有网格**真实顶点**的世界包围盒。
##
## 为什么不用 `mi.get_aabb()`：那是「网格包围盒整体套上节点变换」的结果 ——
## 旋转后盒子会显著变大（低山实测 x/z 各被放大 4~5 m，还叠加了 LOD 余量），
## 拿来判"山脚有没有超出岛体"会误报。
func _vertex_aabb(root: Node) -> AABB:
	var box := AABB()
	var first := true
	if root == null:
		return box
	for node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		if mi.mesh == null:
			continue
		var xf := mi.global_transform
		for s in mi.mesh.get_surface_count():
			var arr := mi.mesh.surface_get_arrays(s)
			if arr.is_empty():
				continue
			for v in arr[Mesh.ARRAY_VERTEX]:
				var w: Vector3 = xf * v
				if first:
					box = AABB(w, Vector3.ZERO)
					first = false
				else:
					box = box.expand(w)
	return box


func _ground_height(point: Vector2, from_y: float, exclude: Array[RID]) -> float:
	return _ground_height_xz(point.x, point.y, from_y, exclude)


func _ground_height_xz(x: float, z: float, from_y: float, exclude: Array[RID]) -> float:
	var query := PhysicsRayQueryParameters3D.create(
		Vector3(x, from_y, z), Vector3(x, -12.0, z))
	query.collide_with_areas = true
	query.exclude = exclude
	var hit := get_root().world_3d.direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y


## 某个散布分组下所有实例的世界位置。返回 [[Vector3 位置, 是否属于山体], ...]
## 分组层级（Rocks/MountainBoulders 这种）在烘 MultiMesh 时**特意保留**了，
## 所以这里还能按名字把山上的石头分出来。
func _instances_under(root: Node) -> Array:
	var out: Array = []
	if root == null:
		return out
	for node in root.find_children("*", "MultiMeshInstance3D", true, false):
		var mmi := node as MultiMeshInstance3D
		if mmi.multimesh == null:
			continue
		var on_mountain := false
		var walk := mmi.get_parent()
		while walk != null and walk != root.get_parent():
			if String(walk.name).contains("Mountain"):
				on_mountain = true
				break
			walk = walk.get_parent()
		var base := mmi.global_transform
		for i in mmi.multimesh.instance_count:
			out.append([(base * mmi.multimesh.get_instance_transform(i)).origin, on_mountain])
	return out


func _instance_count(root: Node) -> int:
	if root == null:
		return 0
	var total := 0
	for node in root.find_children("*", "MultiMeshInstance3D", true, false):
		var mm := (node as MultiMeshInstance3D).multimesh
		if mm != null:
			total += mm.instance_count
	return total


## 递归找名字匹配的节点。
func _find_node_named(node: Node, target: String) -> Node:
	if String(node.name) == target:
		return node
	for child in node.get_children():
		var found := _find_node_named(child, target)
		if found != null:
			return found
	return null


## 岛上所有恐龙的碰撞体 RID（射线探测时要把它们排除掉）。
func _dino_rids() -> Array[RID]:
	var out: Array[RID] = []
	var dinos := _scene.get_node_or_null("Dinosaurs")
	if dinos == null:
		return out
	for dino in dinos.get_children():
		if dino is CollisionObject3D:
			out.append((dino as CollisionObject3D).get_rid())
	return out


## 找到某个节点下面的 Skeleton3D（恐龙用）。
func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node as Skeleton3D
	for child in node.get_children():
		var found := _find_skeleton(child)
		if found != null:
			return found
	return null
