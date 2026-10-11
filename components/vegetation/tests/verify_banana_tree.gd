extends SceneTree
## 香蕉树 / 香蕉串组件自检脚本（无需编辑器，直接跑无头模式）。
##
## 运行方式（在项目根目录执行）：
## [codeblock]
## /Applications/Godot.app/Contents/MacOS/Godot --headless --script res://components/vegetation/tests/verify_banana_tree.gd
## [/codeblock]
## 全部通过时进程退出码为 0，否则为 1。

const BUNCH_SCENE: PackedScene = preload("res://components/vegetation/banana_bunch/banana_bunch.tscn")
const TREE_SCENE: PackedScene = preload("res://components/vegetation/banana_tree/banana_tree.tscn")
const BANANA_SCENE: PackedScene = preload("res://assets/models/banana/banana.glb")
const TREE_MODELS := {
	"tall": preload("res://assets/models/banana-tree-tall/low_poly_banana_tree.glb"),
	"short": preload("res://assets/models/banana-tree-short/low_poly_banana_tree.glb"),
}

var _checks: int = 0
var _failures: int = 0
var _ran: bool = false


## 注意：要等到第一帧再跑，因为 _initialize 阶段根节点还没进场景树，_ready 不会被调用。
func _process(_delta: float) -> bool:
	if _ran:
		return true
	_ran = true
	_run_all()
	return true


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if condition:
		print("  [OK] ", message)
	else:
		_failures += 1
		printerr("  [FAIL] ", message)


func _run_all() -> void:
	print("=== BananaTree / BananaBunch 组件自检 ===")
	_test_banana_asset()
	_test_bunch_count()
	_test_bunch_rows()
	_test_bunch_scale()
	_test_tree_bunch_count()
	_test_tree_bananas_per_bunch()
	_test_tree_style_switch()
	_test_tree_zero_bunches()
	_test_determinism()
	_test_geometry_is_sane()
	_test_bananas_do_not_penetrate_stalk()
	print("=== 共 %d 项检查，失败 %d 项 ===" % [_checks, _failures])
	quit(1 if _failures > 0 else 0)


## 单根香蕉资产本身要可用，且朝向符合约定（蒂在原点、往 -Y 生长）。
func _test_banana_asset() -> void:
	print("[1] 单根香蕉资产")
	_check(BANANA_SCENE != null, "banana.glb 能加载")
	var banana := BANANA_SCENE.instantiate() as Node3D
	root.add_child(banana)
	var aabb := _visual_aabb(banana)
	_check(not aabb.has_volume() == false, "香蕉有实际几何体积")
	# 蒂在原点附近，主体在 -Y 方向
	_check(aabb.position.y < -0.05, "香蕉主体在原点下方（蒂在上）")
	_check(absf(aabb.position.x) < 0.25, "香蕉的弯曲幅度在合理范围内")
	banana.queue_free()


## 一把几根由参数控制。
func _test_bunch_count() -> void:
	print("[2] 香蕉串：根数参数")
	for count in [1, 5, 7, 12]:
		var bunch := BUNCH_SCENE.instantiate() as BananaBunch
		bunch.auto_generate = false
		root.add_child(bunch)
		bunch.banana_count = count
		bunch.rebuild()
		_check(
			bunch.get_banana_count() == count,
			"banana_count=%d 实际生成 %d 根" % [count, bunch.get_banana_count()]
		)
		var actual := _count_descendants(bunch, "Banana_")
		_check(actual == count, "场景里确实有 %d 个香蕉节点（实际 %d）" % [count, actual])
		bunch.queue_free()


## 圈数参数影响排布：多圈应该在高度上更分散。
func _test_bunch_rows() -> void:
	print("[3] 香蕉串：圈数参数")
	var one_row := BUNCH_SCENE.instantiate() as BananaBunch
	one_row.auto_generate = false
	root.add_child(one_row)
	one_row.banana_count = 8
	one_row.rows = 1
	one_row.rebuild()
	var single_height := _banana_height_spread(one_row)

	var three_rows := BUNCH_SCENE.instantiate() as BananaBunch
	three_rows.auto_generate = false
	root.add_child(three_rows)
	three_rows.banana_count = 8
	three_rows.rows = 3
	three_rows.rebuild()
	var multi_height := _banana_height_spread(three_rows)

	_check(single_height < 0.02, "1 圈时香蕉几乎同一高度（%.4f）" % single_height)
	_check(multi_height > single_height + 0.05, "3 圈时高度明显拉开（%.4f）" % multi_height)
	one_row.queue_free()
	three_rows.queue_free()


## 缩放参数要真的作用到几何上。
func _test_bunch_scale() -> void:
	print("[4] 香蕉串：缩放参数")
	var small := BUNCH_SCENE.instantiate() as BananaBunch
	small.auto_generate = false
	root.add_child(small)
	small.banana_count = 6
	small.bunch_scale = 0.5
	small.rebuild()
	var small_height := _visual_aabb(small).size.y

	var big := BUNCH_SCENE.instantiate() as BananaBunch
	big.auto_generate = false
	root.add_child(big)
	big.banana_count = 6
	big.bunch_scale = 2.0
	big.rebuild()
	var big_height := _visual_aabb(big).size.y

	_check(big_height > small_height * 2.0, "放大 4 倍后高度明显增加（%.2f → %.2f）" % [small_height, big_height])
	small.queue_free()
	big.queue_free()


## 一棵树挂几把由参数控制。
func _test_tree_bunch_count() -> void:
	print("[5] 香蕉树：把数参数")
	for count in [0, 1, 3, 5]:
		var tree := TREE_SCENE.instantiate() as BananaTree
		tree.auto_generate = false
		root.add_child(tree)
		tree.bunch_count = count
		tree.bananas_per_bunch = 7
		tree.rebuild()
		_check(
			tree.get_bunch_count() == count,
			"bunch_count=%d 实际挂 %d 把" % [count, tree.get_bunch_count()]
		)
		_check(
			tree.get_bunches().size() == count,
			"查询接口返回 %d 把" % tree.get_bunches().size()
		)
		tree.queue_free()


## 每把几根 + 总根数。
func _test_tree_bananas_per_bunch() -> void:
	print("[6] 香蕉树：每把根数 与 总根数")
	var tree := TREE_SCENE.instantiate() as BananaTree
	tree.auto_generate = false
	root.add_child(tree)
	tree.bunch_count = 3
	tree.bananas_per_bunch = 8
	tree.rebuild()
	_check(tree.get_total_banana_count() == 24, "3 把 x 8 根 = 24 根（实际 %d）" % tree.get_total_banana_count())
	for bunch in tree.get_bunches():
		_check(bunch.get_banana_count() == 8, "每一把都是 8 根（实际 %d）" % bunch.get_banana_count())
	tree.queue_free()


## 高 / 矮款式切换。
func _test_tree_style_switch() -> void:
	print("[7] 香蕉树：高矮款式切换")
	for style in ["tall", "short"]:
		var tree := TREE_SCENE.instantiate() as BananaTree
		tree.auto_generate = false
		root.add_child(tree)
		tree.tree_scene = TREE_MODELS[style]
		tree.tree_height = 4.77 if style == "tall" else 2.66
		tree.bunch_count = 3
		tree.rebuild()
		var expected_height: float = tree.tree_height
		var model := tree.get_node_or_null("Tree/TreeModel") as Node3D
		_check(model != null, "%s 款：树模型已实例化" % style)
		var aabb := _visual_aabb(model)
		_check(
			absf(aabb.size.y - expected_height) < 0.35,
			"%s 款高度约 %.2f m（实际 %.2f）" % [style, expected_height, aabb.size.y]
		)
		# 果串必须挂在树高的范围内，不能飘到树外面
		var bunches := tree.get_bunches()
		var top: float = 0.0
		for bunch in bunches:
			top = maxf(top, bunch.position.y)
		_check(top > 0.0 and top <= expected_height, "%s 款：果串挂在 0~%.2f m 之间（最高 %.2f）" % [style, expected_height, top])
		tree.queue_free()


## 0 把时树还在，只是没有果子。
func _test_tree_zero_bunches() -> void:
	print("[8] 香蕉树：0 把果串")
	var tree := TREE_SCENE.instantiate() as BananaTree
	tree.auto_generate = false
	root.add_child(tree)
	tree.bunch_count = 0
	tree.rebuild()
	_check(tree.get_bunch_count() == 0, "没有果串")
	_check(tree.get_node_or_null("Tree/TreeModel") != null, "树模型仍然存在")
	tree.queue_free()


## 固定种子必须可复现。
func _test_determinism() -> void:
	print("[9] 确定性（固定种子）")
	var positions_a := _collect_bunch_positions(12345)
	var positions_b := _collect_bunch_positions(12345)
	_check(positions_a == positions_b, "同一颗种子两次生成的果串位置完全一致")

	var positions_c := _collect_bunch_positions(999)
	_check(positions_a != positions_c, "换种子后果串位置不同")


## 几何要落在合理范围：不穿进假茎、不飘到树外。
func _test_geometry_is_sane() -> void:
	print("[10] 几何合理性")
	var tree := TREE_SCENE.instantiate() as BananaTree
	tree.auto_generate = false
	root.add_child(tree)
	tree.bunch_count = 3
	tree.bananas_per_bunch = 7
	tree.rebuild()

	var root_aabb := _visual_aabb(tree)
	# 整棵树的最高点应该在树高附近（果串不会比树还高太多）
	_check(
		root_aabb.end.y < tree.tree_height + 1.0,
		"整树最高点 %.2f m 不超过树高 + 1m（树高 %.2f）" % [root_aabb.end.y, tree.tree_height]
	)
	# 果串应该伸出到假茎之外（半径方向有内容）
	var max_radius: float = 0.0
	for bunch in tree.get_bunches():
		for banana in bunch.get_children():
			for item in banana.get_children():
				if item is Node3D and (item as Node3D).name.begins_with("Banana_"):
					var local := (item as Node3D).global_position - tree.global_position
					max_radius = maxf(max_radius, Vector2(local.x, local.z).length())
	_check(max_radius > 0.15, "果串伸出假茎之外（最大半径 %.2f m）" % max_radius)
	tree.queue_free()


## ---------------- 工具 ----------------

func _collect_bunch_positions(seed_value: int) -> Array[Vector3]:
	var tree := TREE_SCENE.instantiate() as BananaTree
	tree.auto_generate = false
	root.add_child(tree)
	tree.random_seed = seed_value
	tree.bunch_count = 4
	tree.rebuild()
	var positions: Array[Vector3] = []
	for bunch in tree.get_bunches():
		positions.append(bunch.position)
	tree.queue_free()
	return positions


## 统计名字以 prefix 开头的后代节点数量。
func _count_descendants(node: Node, prefix: String) -> int:
	var total := 0
	for child in node.get_children():
		if child.name.begins_with(prefix):
			total += 1
		total += _count_descendants(child, prefix)
	return total


## 香蕉在高度上的分散程度（最高与最低香蕉原点之差）。
## 只统计香蕉本身（Banana_*），不含果轴 / 蕉蕾，否则测的就不是香蕉的排布了。
func _banana_height_spread(bunch: BananaBunch) -> float:
	var heights: Array[float] = []
	var container := bunch.get_node_or_null("Bananas")
	if container == null:
		return 0.0
	for item in container.get_children():
		if item is Node3D and (item as Node3D).name.begins_with("Banana_"):
			heights.append((item as Node3D).position.y)
	if heights.is_empty():
		return 0.0
	return heights.max() - heights.min()


## 一个节点下所有可视几何在自身坐标系里的合并包围盒。
func _visual_aabb(node: Node) -> AABB:
	var result := AABB()
	var first := true
	for child in node.get_children():
		if child is VisualInstance3D:
			var box: AABB = (child as VisualInstance3D).get_aabb()
			box = (child as Node3D).transform * box
			result = box if first else result.merge(box)
			first = false
		var sub := _visual_aabb(child)
		if sub.has_volume():
			var offset := (child as Node3D).transform if child is Node3D else Transform3D.IDENTITY
			sub = offset * sub
			result = sub if first else result.merge(sub)
			first = false
	return result

## 香蕉不能插进假茎里——用几何数据判定，而不是靠肉眼看渲染图。
##
## 做法：先从树模型里读出假茎（Stalk）在每个高度上的最大半径，做成一条"半径剖面"，
## 再取每一根香蕉的每个顶点，检查它到中轴的距离是否大于该高度的假茎半径。
## 允许少量顶点贴着假茎（[param tolerance]），因为果串本来就该是"长在茎上"的。
func _test_bananas_do_not_penetrate_stalk(tolerance: float = 0.02) -> void:
	print("[11] 香蕉不插进假茎")
	var tree := TREE_SCENE.instantiate() as BananaTree
	tree.auto_generate = false
	root.add_child(tree)
	tree.bunch_count = 3
	tree.bananas_per_bunch = 7
	tree.rebuild()

	var stalk_profile := _stalk_radius_profile(tree)
	_check(not stalk_profile.is_empty(), "读到了假茎半径剖面（%d 个采样点）" % stalk_profile.size())

	var worst: float = 0.0
	var worst_at := Vector3.ZERO
	for bunch in tree.get_bunches():
		for node in _collect_mesh_instances(bunch):
			# 只查香蕉，不查果柄 / 果轴 / 蕉蕾：果柄本来就该插进假茎
			if (node as Node3D).name.to_lower().contains("stem") \
					or (node as Node3D).name.to_lower().contains("flower"):
				continue
			var mesh: Mesh = (node as MeshInstance3D).mesh
			var to_tree := tree.global_transform.affine_inverse() * (node as Node3D).global_transform
			for surface in mesh.get_surface_count():
				var arrays := mesh.surface_get_arrays(surface)
				var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
				for v in verts:
					var local := to_tree * v
					var radius := sqrt(local.x * local.x + local.z * local.z)
					var stalk_r := _stalk_radius_at(stalk_profile, local.y)
					# 只检查确实落在假茎高度范围内的顶点
					if stalk_r <= 0.0:
						continue
					var penetration := stalk_r - radius
					if penetration > worst:
						worst = penetration
						worst_at = local
	_check(
		worst <= tolerance,
		"没有香蕉插进假茎（最深侵入 %.3f m，容许 %.3f）" % [worst, tolerance]
	)
	if worst > tolerance:
		printerr("       最深侵入点 local=", worst_at, " 建议增大 bunch_outset")
	tree.queue_free()


## 假茎在每个高度上的最大半径。返回 {y: radius} 采样表。
func _stalk_radius_profile(tree: BananaTree) -> Dictionary:
	var profile := {}
	var model := tree.get_node_or_null("Tree/TreeModel")
	if model == null:
		return profile
	for node in _collect_mesh_instances(model):
		var mesh_instance := node as MeshInstance3D
		# 只取假茎：节点名包含 Stalk 的部分
		if not mesh_instance.name.to_lower().contains("stalk"):
			continue
		var mesh: Mesh = mesh_instance.mesh
		var to_tree := tree.global_transform.affine_inverse() * mesh_instance.global_transform
		for surface in mesh.get_surface_count():
			var arrays := mesh.surface_get_arrays(surface)
			var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			for v in verts:
				var local := to_tree * v
				var radius := sqrt(local.x * local.x + local.z * local.z)
				var key := snappedf(local.y, 0.02)
				if not profile.has(key) or profile[key] < radius:
					profile[key] = radius
	return profile


## 查某个高度上的假茎半径。取最近的两个采样点做线性插值；
## 超出假茎高度范围（顶部 / 底部之外）返回 0，表示该处没有假茎。
func _stalk_radius_at(profile: Dictionary, y: float) -> float:
	if profile.is_empty():
		return 0.0
	var keys := profile.keys()
	keys.sort()
	var lowest: float = keys[0]
	var highest: float = keys[keys.size() - 1]
	# 上下各留一点余量，避免果串挂在梢头附近时被误判
	if y < lowest - 0.05 or y > highest + 0.05:
		return 0.0
	var best_y: float = keys[0]
	for key in keys:
		if absf(key - y) < absf(best_y - y):
			best_y = key
	return profile[best_y]


## 收集一个节点下所有 MeshInstance3D。
func _collect_mesh_instances(node: Node) -> Array[Node]:
	var result: Array[Node] = []
	if node is MeshInstance3D:
		result.append(node)
	for child in node.get_children():
		result.append_array(_collect_mesh_instances(child))
	return result
