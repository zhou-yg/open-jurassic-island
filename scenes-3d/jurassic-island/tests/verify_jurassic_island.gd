extends SceneTree
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
const ISLAND_SIZE_M: float = 2000.0
const ISLAND_COMPONENT_WIDTH_M: float = 62.0
const MAX_WALKABLE_DEG: float = 50.0

var _checks: int = 0
var _failures: int = 0
var _scene: Node3D


func _initialize() -> void:
	_scene = load(SCENE_PATH).instantiate()
	get_root().add_child(_scene)
	create_timer(WAIT_SECONDS).timeout.connect(_run_all)


func _run_all() -> void:
	print("=== 2000 m 主岛场景自检（静态配置）===")
	_test_no_runtime_script()
	_test_island_scale()
	_test_sea()
	_test_player()
	_test_component_switches()
	_test_local_scatter()
	_test_walkable_slopes()
	_test_environment()
	print("=== 检查项 %d，失败 %d ===" % [_checks, _failures])
	print("全部通过 ✅" if _failures == 0 else "存在失败 ❌")
	quit(1 if _failures > 0 else 0)


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		print("  [FAIL] ", message)


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
	var component := island.get_node_or_null("IslandComponent")
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
			"海面太小（%.0f x %.0f），需要覆盖 2000 m 岛的视野" % [size.x, size.y])
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
	_check(get_root().get_camera_3d() == camera, "当前视口相机不是玩家相机")
	_check(player.floor_max_angle >= deg_to_rad(49.9),
		"玩家可站立坡度只有 %.1f°，走不上 48° 左右的草坡" % rad_to_deg(player.floor_max_angle))
	_check(player.is_on_floor(), "玩家没有站在地面上")
	_check(player.global_position.y > 1.0, "玩家低于海平面（y=%.1f）" % player.global_position.y)
	var flat := Vector2(player.global_position.x, player.global_position.z)
	_check(flat.length() < 1100.0, "玩家出生点跑出了 2000 m 岛（水平距离 %.0f m）" % flat.length())


func _test_component_switches() -> void:
	var component := _scene.get_node_or_null("Island/IslandComponent")
	_check(component != null, "找不到岛组件")
	if component == null:
		return
	# 唯一真源：主场景直接实例化组件本体 island.tscn，而不是另存一份精简副本。
	_check(component.scene_file_path == "res://components/island/island.tscn",
		"岛组件不是 island.tscn（%s）" % component.scene_file_path)
	_check(component.get_script() != null, "岛组件缺少 island.gd（地形/山体碰撞）")
	if component.get_script() == null:
		return
	# 三个展示开关：组件自带的环境 / 灯光 / 预览相机、62 m 尺度的草石和围墙，在 32 倍
	# 的主场景里全部关掉，由主场景自己的环境 / 灯光 / LocalScatter / ParkEntrance 接管。
	_check(not bool(component.get("show_presentation")),
		"show_presentation 没关（预览相机会抢走第一人称视角，环境光会叠加）")
	_check(not bool(component.get("show_scatter")),
		"show_scatter 没关（放大 32 倍后会变成二十多米高的巨草）")
	_check(not bool(component.get("show_perimeter")),
		"show_perimeter 没关（放大 32 倍后会变成一圈半径近 1 km 的巨墙）")
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
	# 地形 / 山体碰撞仍然由组件自己补齐 —— 这是主场景岛面碰撞的唯一来源。
	var terrain := component.get_node_or_null("Ground/Terrain")
	_check(terrain != null and terrain.get_node_or_null("StaticBody3D") != null,
		"组件没有给 Ground/Terrain 补地形碰撞")
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


func _test_walkable_slopes() -> void:
	var player := _scene.get_node_or_null("Player") as CharacterBody3D
	var local := _scene.get_node_or_null("LocalScatter")
	if player == null or local == null:
		return
	var exclude: Array[RID] = [player.get_rid()]
	for node in local.find_children("*", "StaticBody3D", true, false):
		exclude.append((node as StaticBody3D).get_rid())
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
			var hit := get_root().world_3d.direct_space_state.intersect_ray(query)
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
	var world_env := _scene.get_node_or_null("WorldEnvironment") as WorldEnvironment
	_check(world_env != null, "主场景缺少 WorldEnvironment")
	if world_env != null:
		var env := world_env.environment
		_check(env.sky != null, "主场景没有天空")
		_check(env.fog_enabled, "主场景没有雾（海面边缘会穿帮）")
		_check(env.fog_density <= 0.001, "雾太浓，2000 m 岛会看不清")
	var sun := _scene.get_node_or_null("Sun") as DirectionalLight3D
	_check(sun != null, "主场景缺少太阳")
	if sun != null:
		_check(sun.shadow_enabled, "太阳没有阴影")
		_check(sun.directional_shadow_max_distance >= 2000.0,
			"阴影距离太小（%.0f），远处没有影子" % sun.directional_shadow_max_distance)
