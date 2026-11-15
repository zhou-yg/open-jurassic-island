extends Node
## 2000 m 主岛场景自检。
##
## 现在主场景没有运行时脚本：岛体变换、海面、玩家、静态草石都在 .tscn 里；
## 岛组件直接实例化组件本体 island.tscn，组件根的
## show_presentation / show_scatter / show_perimeter 三个开关在主场景里关掉。
##
## 运行方式：
## [codeblock]
## /Applications/Godot.app/Contents/MacOS/Godot \
##   --script res://scenes-3d/jurassic-island/tests/verify_jurassic_island.gd
## [/codeblock]
##
## ⚠️ **不要加 `--headless`**：地形是 MultiMesh，实例变换存在 RenderingServer 里；
## headless 的 dummy 渲染器读出来全是单位矩阵，`island.gd` 补出来的地形碰撞会全部
## 叠在岛心，"坡度抽查"那几项量到的就不是真实地形。其余检查 headless 也能过。

const SCENE_PATH: String = "res://scenes-3d/jurassic-island/jurassic-island.tscn"
const WAIT_SECONDS: float = 5.0
## 岛的**直径**（米）。2026-11 岛缩小了一半（面积减半 → 线性 ×0.7071），
## 2000 m 变成约 1414 m。
const ISLAND_SIZE_M: float = 1414.0
const ISLAND_COMPONENT_WIDTH_M: float = 62.0
const MAX_WALKABLE_DEG: float = 50.0

var _checks: int = 0
var _failures: int = 0
var _scene: Node3D
## 第一帧时每只恐龙的**位置**（跑几秒后再比，看它们是不是真的在动）。
var _dino_start: Dictionary = {}
var _dino_start_captured: bool = false


func _ready() -> void:
	_scene = load(SCENE_PATH).instantiate()
	# 延后一帧挂：此刻 root 正在"设置子节点"，直接 add_child 会被拒，
	# 场景挂不上去的话玩家就没有地形、相机也不对。
	get_tree().root.add_child.call_deferred(_scene)
	get_tree().create_timer(WAIT_SECONDS).timeout.connect(_run_all)


## 场景进树之后（第一帧）记下每只恐龙的位置。
func _capture_dino_start() -> void:
	if _dino_start_captured:
		return
	if _scene == null or not _scene.is_inside_tree():
		return
	# 恐龙群组件是**运行时**放恐龙的（连着放好几帧）：
	# 数量还没到初始值就先别记 —— 否则记下的是一份空表，后面"有没有在动"全判 0。
	var herd := _scene.get_node_or_null("Dinosaurs")
	if herd != null and _herd_dinosaurs().size() < int(herd.get("initial_count")):
		return
	_dino_start_captured = true
	_dino_start = _dino_positions()


func _process(_delta: float) -> void:
	_capture_dino_start()


func _run_all() -> void:
	print("=== 大世界主岛场景自检（静态配置）===")
	_test_no_runtime_script()
	_test_island_scale()
	_test_sea()
	_test_player()
	_test_component_switches()
	_test_local_scatter()
	_test_world_vegetation()
	_test_world_dinosaurs()
	_test_walkable_slopes()
	_test_environment()
	print("=== 检查项 %d，失败 %d ===" % [_checks, _failures])
	print("全部通过 ✅" if _failures == 0 else "存在失败 ❌")
	get_tree().quit(1 if _failures > 0 else 0)


## 场上所有恐龙的碰撞体 RID（坡度抽查时要把它们排除掉）。
func _world_dino_rids() -> Array[RID]:
	var out: Array[RID] = []
	for dino in _herd_dinosaurs():
		if dino is CollisionObject3D:
			out.append((dino as CollisionObject3D).get_rid())
	return out


## 记下每只恐龙现在的位置。
func _dino_positions() -> Dictionary:
	var out: Dictionary = {}
	for dino in _herd_dinosaurs():
		if dino is Node3D:
			out[dino.name] = (dino as Node3D).global_position
	return out


## 恐龙群组件放出来的恐龙（运行时 add 进去的，不是场景里烘死的节点）。
func _herd_dinosaurs() -> Array:
	var herd := _scene.get_node_or_null("Dinosaurs")
	if herd == null:
		return []
	var list: Variant = herd.get("dinosaurs")
	if list is Array:
		return list
	return []


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		print("  [FAIL] ", message)


func _section(title: String) -> void:
	print("-- ", title)


func _test_no_runtime_script() -> void:
	_check(_scene.get_script() == null, "主场景根节点还挂着运行时脚本")


func _test_island_scale() -> void:
	var island := _scene.get_node_or_null("Island") as Node3D
	_check(island != null, "缺少 Island 节点")
	if island == null:
		return
	var expected_x := ISLAND_SIZE_M / ISLAND_COMPONENT_WIDTH_M
	var expected_y := expected_x * 0.65
	_check(absf(island.scale.x - expected_x) < 0.05,
		"岛体水平缩放不是 2000 m（x=%.3f，预期 %.3f）" % [island.scale.x, expected_x])
	_check(absf(island.scale.y - expected_y) < 0.05,
		"岛体竖直缩放不是可走比例（y=%.3f，预期 %.3f）" % [island.scale.y, expected_y])
	_check(absf(island.scale.z - expected_x) < 0.05,
		"岛体水平缩放不是 2000 m（z=%.3f）" % island.scale.z)
	var component := island.get_node_or_null("Island")
	_check(component != null, "Island 下没有 island.tscn 实例")


func _test_sea() -> void:
	var sea := _scene.get_node_or_null("Sea") as MeshInstance3D
	_check(sea != null, "缺少 Sea")
	if sea == null:
		return
	_check(sea.mesh is PlaneMesh, "海面不是 PlaneMesh")
	if sea.mesh is PlaneMesh:
		var size := (sea.mesh as PlaneMesh).size
		_check(size.x >= 10000.0 and size.y >= 10000.0,
			"海面太小（%.0f x %.0f），需要覆盖整座岛的视野" % [size.x, size.y])
	_check(sea.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF,
		"海面不应该投射阴影")


func _test_player() -> void:
	var player := _scene.get_node_or_null("Player") as CharacterBody3D
	_check(player != null, "缺少 Player")
	if player == null:
		return
	var camera := player.get_node_or_null("Head/Camera3D") as Camera3D
	_check(camera != null, "玩家没有第一人称相机")
	if camera == null:
		return
	_check(camera.current, "玩家相机不是 current（会被岛组件的预览相机抢走）")
	_check(camera.far >= 10000.0, "相机远裁剪面太小（%.0f），看不到远处海面" % camera.far)
	_check(get_tree().root.get_camera_3d() == camera, "当前视口相机不是玩家相机")
	_check(player.floor_max_angle >= deg_to_rad(49.9),
		"玩家可站立坡度只有 %.1f°，走不上 48° 左右的草坡" % rad_to_deg(player.floor_max_angle))
	_check(player.is_on_floor(), "玩家没有站在地面上")
	_check(player.global_position.y > 1.0, "玩家低于海平面（y=%.1f）" % player.global_position.y)
	var flat := Vector2(player.global_position.x, player.global_position.z)
	_check(flat.length() < 800.0, "玩家出生点跑出了岛（水平距离 %.0f m）" % flat.length())


func _test_component_switches() -> void:
	var component := _scene.get_node_or_null("Island/Island")
	_check(component != null, "找不到岛组件")
	if component == null:
		return
	# 唯一真源：主场景直接实例化 **terrain.tscn**（岩台 + 山体），
	# 而不是另存一份精简副本，也不会把展示用的草石 / 围墙 / 香蕉林 / 恐龙带进来。
	_check(component.scene_file_path == "res://components/island/terrain.tscn",
		"大世界的地形不是 terrain.tscn（%s）" % component.scene_file_path)
	_check(component.get_script() != null, "地形缺少 terrain.gd（山体碰撞）")
	if component.get_script() == null:
		return
	# 大世界只实例化 `terrain.tscn`（岩台 + 山体）：展示用的环境 / 灯光 / 预览相机、
	# 62 m 尺度的草石 / 围墙 / 香蕉林 / 恐龙**根本不在场景里**，
	# 不靠开关隐藏 —— 编辑器和运行时看到的东西因此完全一致。
	_check(component.get_node_or_null("WorldEnvironment") == null,
		"大世界里出现了组件的 WorldEnvironment（会和主场景的环境叠加过曝）")
	_check(component.get_node_or_null("Scatter") == null,
		"大世界里出现了组件自带的 Scatter（放大 22 倍会变成二十多米高的巨草）")
	_check(component.get_node_or_null("ParkPerimeter") == null,
		"大世界里出现了组件自带的 ParkPerimeter（放大 22 倍会变成一圈巨墙）")
	var world_env := component.get_node_or_null("WorldEnvironment") as WorldEnvironment
	_check(world_env == null or world_env.environment == null,
		"组件的 WorldEnvironment 还在生效（会和主场景的环境叠加过曝）")
	for node_name in ["Sun", "FillLight", "BounceLight"]:
		var light := component.get_node_or_null(node_name) as Node3D
		_check(light == null or not light.visible, "组件的 %s 还亮着" % node_name)
	var preview := component.get_node_or_null("PreviewCamera") as Camera3D
	_check(preview == null or not preview.current, "组件的 PreviewCamera 还在抢相机")
	# 隐藏的草石 / 围墙也不能留下隐形碰撞：它们的碰撞是按 62 m 尺度补的。
	var scatter := component.get_node_or_null("Scatter") as Node3D
	_check(scatter == null or not scatter.visible, "组件的 Scatter 没隐藏")
	if scatter != null:
		_check(scatter.get_node_or_null("RockCollision") == null,
			"隐藏的 Scatter 还补了石头碰撞（会变成几十米宽的隐形石头）")
	var perimeter := component.get_node_or_null("ParkPerimeter") as Node3D
	_check(perimeter == null or not perimeter.visible, "组件的 ParkPerimeter 没隐藏")
	if perimeter != null:
		_check(perimeter.find_children("*", "StaticBody3D", true, false).is_empty(),
			"隐藏的 ParkPerimeter 还补了碰撞（大门会变成百米宽的隐形门）")
	# 岛面碰撞来自岛体自带的台面（glb 的 `-col` 节点），山体碰撞由组件自己补。
	# 2026-11：烘出来的草毯（Ground/Terrain）删掉了 —— 岛面就是台面。
	_check(component.get_node_or_null("Ground") == null,
		"组件里还有烘出来的草毯（Ground 节点）")
	# 内层 `Island` 节点就是 terrain.tscn 的实例（地形子场景）——
	# 所以它的直接子节点就是 IslandBase / Mountain。
	var terrain_root := component
	var base := component.get_node_or_null("IslandBase")
	_check(base != null and not base.find_children("*", "StaticBody3D", true, false).is_empty(),
		"岛体没有台面碰撞（glb 的 -col 节点）")
	var mountain := component.get_node_or_null("Mountain")
	_check(mountain != null and not mountain.find_children("*", "StaticBody3D", true, false).is_empty(),
		"组件没有给 Mountain 补碰撞")


func _test_local_scatter() -> void:
	var local := _scene.get_node_or_null("LocalScatter")
	_check(local != null, "缺少静态 LocalScatter")
	if local == null:
		return
	# 草石已合并成 MultiMesh：节点只剩几个，**实例数**才代表密度。
	var instances := 0
	for node in local.find_children("*", "MultiMeshInstance3D", true, false):
		var mm := (node as MultiMeshInstance3D).multimesh
		if mm != null:
			instances += mm.instance_count
	_check(instances >= 500,
		"静态草石太少（%d 个实例），玩家附近会显得空" % instances)
	_check(local.get_child_count() <= 40,
		"LocalScatter 节点太多（%d），草石应该走 MultiMesh" % local.get_child_count())
	# 石头碰撞：一个 StaticBody3D + N 个共享凸包 CollisionShape3D
	var rock_shapes := 0
	var rock_body := local.get_node_or_null("RockCollision")
	if rock_body is StaticBody3D:
		rock_shapes = (rock_body as StaticBody3D).get_child_count()
	_check(rock_shapes >= 100, "静态石头碰撞太少（%d）" % rock_shapes)


## ---------------- 世界尺度的植被 + 恐龙 ----------------
##
## 主场景是 1400 m 的大世界，组件里那份 62 m 尺度的植被和恐龙**不能**用
## （放大 32 倍会变成 150 m 高的巨树、350 m 长的霸王龙）。
## 所以另有一份 1:1 米制的烘焙：`scenes-3d/jurassic-island/world_vegetation.tscn`
## 和 `world_dinosaurs.tscn`。
func _test_world_vegetation() -> void:
	_section("世界植被")
	var veg := _scene.get_node_or_null("WorldVegetation")
	_check(veg != null, "缺少 WorldVegetation（大世界的香蕉树林）")
	if veg == null:
		return
	var trees := veg.get_node_or_null("Trees")
	_check(trees != null, "WorldVegetation 下缺少 Trees")
	if trees == null:
		return
	var short_mm := trees.get_node_or_null("ShortTrees") as MultiMeshInstance3D
	var tall_mm := trees.get_node_or_null("TallTrees") as MultiMeshInstance3D
	_check(short_mm != null and tall_mm != null, "缺少 ShortTrees / TallTrees 两个 MultiMesh")
	if short_mm == null or tall_mm == null:
		return
	var total := short_mm.multimesh.instance_count + tall_mm.multimesh.instance_count
	_check(total >= 1500, "大世界的树太少（%d 棵，应 >= 1500）" % total)
	# 树必须是 MultiMesh：上千棵树不能变成上千个节点
	_check(veg.find_children("*", "MultiMeshInstance3D", true, false).size() <= 4,
		"WorldVegetation 的 MultiMesh 太多（树应该走 MultiMesh）")
	# 树干碰撞：MultiMesh 不产生碰撞，运行时必须补上。
	#
	# 大世界有几千棵树，用物理服务器直接挂形状（不生成几千个节点），
	# 所以形状数要从物理服务器查，不是数子节点。
	var tree_body := veg.get_node_or_null("TreeCollision")
	_check(tree_body is StaticBody3D, "树干没有补齐碰撞（缺 WorldVegetation/TreeCollision）")
	if tree_body is StaticBody3D:
		var shapes := PhysicsServer3D.body_get_shape_count((tree_body as StaticBody3D).get_rid())
		_check(shapes == total,
			"树干碰撞体数量不对（%d / %d 棵）" % [shapes, total])
	# 树不能长在玩家出生点里
	var player := _scene.get_node_or_null("Player") as Node3D
	if player != null:
		var near_spawn := 0
		for entry in _instances_under(trees):
			var p: Vector3 = entry[0]
			if Vector2(p.x, p.z).distance_to(Vector2(player.global_position.x,
					player.global_position.z)) < 25.0:
				near_spawn += 1
		_check(near_spawn == 0, "玩家出生点附近有 %d 棵树（应该是一片空地）" % near_spawn)


func _test_world_dinosaurs() -> void:
	_section("世界恐龙")
	var herd := _scene.get_node_or_null("Dinosaurs")
	_check(herd != null, "缺少 Dinosaurs（恐龙群组件）")
	if herd == null:
		return
	var all := _herd_dinosaurs()
	var count := 0
	# 组件应该按 initial_count 放满
	var want := int(herd.get("initial_count"))
	_check(all.size() == want,
		"恐龙数量不对（%d 只，组件配置的初始数量是 %d）" % [all.size(), want])
	_check(herd.get_node_or_null("Boundary") != null,
		"恐龙群没有边界围栏（恐龙会走下悬崖）")
	var moved := 0
	var with_ai := 0
	for dino in all:
		if not (dino is Node3D):
			continue
		count += 1
		var start: Vector3 = _dino_start.get(dino.name, (dino as Node3D).global_position)
		if start.distance_to((dino as Node3D).global_position) > 0.5:
			moved += 1
		# 每只恐龙都得有 AI + 调参表 + 巡逻路线
		var ai: Node = (dino as Node3D).get_node_or_null("AI")
		if ai != null and ai.get("config") != null:
			with_ai += 1
		var route: Variant = (dino as Node3D).get("route")
		_check(route is PackedVector3Array and (route as PackedVector3Array).size() >= 8,
			"%s 没有巡逻路线（应 >= 8 个路点）" % dino.name)
		# 碰撞掩码：撞树、撞墙，不撞石头
		var body := dino as CollisionObject3D
		if body != null:
			var mask := body.collision_mask
			_check((mask & 1) != 0, "%s 的碰撞掩码里没有地面层" % dino.name)
			_check((mask & 2) != 0, "%s 的碰撞掩码里没有植被层" % dino.name)
			_check((mask & 8) == 0, "%s 的碰撞掩码里有杂物层（石头会把巡逻卡住）" % dino.name)
	_check(count >= 50, "大世界的恐龙太少（%d 只，应 >= 50）" % count)
	_check(with_ai == count, "有恐龙没有 AI / 调参表（%d / %d）" % [with_ai, count])
	# 歇着的恐龙站着不动是正常的（休息 6 s，比这个 5 s 的观察窗口还长），
	# 所以不要求 100% 都在动 —— 但绝大多数得在动。
	_check(float(moved) / float(maxi(1, count)) >= 0.9,
		"有恐龙没有在巡逻（%d / %d 只在动）" % [moved, count])


## 某个散布分组下所有实例的世界位置。
func _instances_under(root: Node) -> Array:
	var out: Array = []
	if root == null:
		return out
	for node in root.find_children("*", "MultiMeshInstance3D", true, false):
		var mmi := node as MultiMeshInstance3D
		if mmi.multimesh == null:
			continue
		var base := mmi.global_transform
		for i in mmi.multimesh.instance_count:
			out.append([(base * mmi.multimesh.get_instance_transform(i)).origin])
	return out


func _test_walkable_slopes() -> void:
	var player := _scene.get_node_or_null("Player") as CharacterBody3D
	var local := _scene.get_node_or_null("LocalScatter")
	if player == null or local == null:
		return
	var exclude: Array[RID] = [player.get_rid()]
	for node in local.find_children("*", "StaticBody3D", true, false):
		exclude.append((node as StaticBody3D).get_rid())
	# 树干碰撞也要排除：垂直射线会先打在树干侧面，量到的就不是地面了
	var veg := _scene.get_node_or_null("WorldVegetation")
	if veg != null:
		var tree_body := veg.get_node_or_null("TreeCollision")
		if tree_body is StaticBody3D:
			exclude.append((tree_body as StaticBody3D).get_rid())
	# 恐龙的胶囊同理：射线打在侧面就是 90°
	for dino in _world_dino_rids():
		exclude.append(dino)
	var max_deg := 0.0
	var steep := 0
	var total := 0
	var origin := player.global_position
	for gx in range(-24, 25):
		for gz in range(-24, 25):
			var x := origin.x + gx * 25.0
			var z := origin.z + gz * 25.0
			var query := PhysicsRayQueryParameters3D.create(
				Vector3(x, 1500.0, z), Vector3(x, -200.0, z))
			query.exclude = exclude
			var hit := get_tree().root.world_3d.direct_space_state.intersect_ray(query)
			if hit.is_empty():
				continue
			var collider := hit["collider"] as Node
			if collider != null and str(collider.get_path()).contains("Mountain"):
				continue
			var n: Vector3 = hit["normal"]
			var deg := rad_to_deg(acos(clampf(n.y, -1.0, 1.0)))
			max_deg = maxf(max_deg, deg)
			total += 1
			if deg > MAX_WALKABLE_DEG:
				steep += 1
	_check(total > 0, "坡度抽查没有打到地面")
	_check(steep == 0, "基础地形有 %d/%d 个点超过 %.0f°，玩家需要跳跃" % [
		steep, total, MAX_WALKABLE_DEG])
	_check(max_deg <= MAX_WALKABLE_DEG, "基础地形最大坡度 %.1f° 超过 %.0f°" % [
		max_deg, MAX_WALKABLE_DEG])
	print("  坡度抽查：%d 点，最大 %.1f°" % [total, max_deg])


func _test_environment() -> void:
	# 主场景用 Sky3D 插件接管大气和日月：环境节点叫 "Sky3D"，
	# 太阳是它下面的 "SunLight"。老名字（WorldEnvironment / Sun）也认。
	var world_env := _scene.get_node_or_null("WorldEnvironment") as WorldEnvironment
	if world_env == null:
		world_env = _scene.get_node_or_null("Sky3D") as WorldEnvironment
	_check(world_env != null, "主场景缺少 WorldEnvironment（Sky3D）")
	if world_env != null:
		var env := world_env.environment
		_check(env.sky != null, "主场景没有天空")
		_check(env.fog_enabled, "主场景没有雾（海面边缘会穿帮）")
		_check(env.fog_density <= 0.001, "雾太浓，2000 m 岛会看不清")
	var sun := _scene.get_node_or_null("Sun") as DirectionalLight3D
	if sun == null:
		sun = _scene.get_node_or_null("Sky3D/SunLight") as DirectionalLight3D
	_check(sun != null, "主场景缺少太阳（Sky3D/SunLight）")
	if sun != null:
		# SkyDome 在夜里会把太阳关掉（能量 0），那时关阴影是正常的 ——
		# 所以只有太阳亮着的时候才要求它有阴影。
		_check(sun.shadow_enabled or sun.light_energy <= 0.0, "太阳没有阴影")
		_check(sun.directional_shadow_max_distance >= 2000.0,
			"阴影距离太小（%.0f），远处没有影子" % sun.directional_shadow_max_distance)
