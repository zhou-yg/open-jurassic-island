extends SceneTree
## 临时探针：检查恐龙到底跟什么碰撞、围墙有没有碰撞体。

const SCENE := "res://components/island/island.tscn"
var _f := 0
var _scene: Node3D

func _process(_dt: float) -> bool:
	_f += 1
	if _f == 6:
		_scene = load(SCENE).instantiate()
		root.add_child(_scene)
		return false
	if _f < 16:
		return false
	print("--- 恐龙的碰撞层 / 掩码 ---")
	for d in _scene.get_node("Dinosaurs").get_children():
		print("  %-22s layer=%d mask=%d" % [d.name, d.collision_layer, d.collision_mask])
	print("--- 岛上的静态碰撞体 ---")
	for node in _scene.find_children("*", "StaticBody3D", true, false):
		var b := node as StaticBody3D
		var path := str(node.get_path())
		print("  %-46s layer=%d 形状数=%d" % [path, b.collision_layer, b.get_child_count()])
	print("--- 园区围墙的网格节点（有没有碰撞体？）---")
	var perim := _scene.get_node_or_null("ParkPerimeter")
	if perim != null:
		var meshes := perim.find_children("*", "MeshInstance3D", true, false)
		var with_body := 0
		for m in meshes:
			if m.get_node_or_null("Body") != null or m.get_parent() is StaticBody3D:
				with_body += 1
		print("  网格节点 %d 个，其中带碰撞的 %d 个" % [meshes.size(), with_body])
	quit()
	return true
