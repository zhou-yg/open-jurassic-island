extends SceneTree
## 临时探针：抓恐龙"瞬移"（掉出岛外被送回起点）之前的坐标。

const SCENE := "res://components/island/island.tscn"
var _f := 0
var _scene: Node3D
var _prev := {}
var _n := 0


func _process(_dt: float) -> bool:
	_f += 1
	if _f == 5:
		_scene = load(SCENE).instantiate()
		root.add_child(_scene)
		return false
	if _f > 8:
		for d in _scene.get_node("Dinosaurs").get_children():
			var pos: Vector3 = d.global_position
			if _prev.has(d.name):
				var jump: float = (_prev[d.name] as Vector3).distance_to(pos)
				if jump > 5.0:
					_n += 1
					if _n <= 12:
						var ai = d.get_node_or_null("AI")
						print("瞬移 %-20s 帧%4d 状态=%s %s → (%.1f,%.1f) 跳 %.1f m" % [
							d.name, _f, ai.get_state_name() if ai else "-",
							str((_prev[d.name] as Vector3).round()), pos.x, pos.z, jump])
			_prev[d.name] = pos
	if _f > 1200:
		print("=== 瞬移总次数 %d ===" % _n)
		quit()
		return true
	return false
