extends SceneTree
## 临时探针：追踪一只恐龙的轨迹，找出它到底卡在哪。

const SCENE := "res://components/island/island.tscn"
var _f := 0
var _scene: Node3D
var _t0 := 0.0


func _process(_dt: float) -> bool:
	_f += 1
	if _f == 5:
		_scene = load(SCENE).instantiate()
		root.add_child(_scene)
		_t0 = Time.get_ticks_msec()
		return false
	if _f > 8 and _f % 60 == 0:
		var d = _scene.get_node("Dinosaurs").get_children()[0]
		var ai = d.get_node_or_null("AI")
		print("帧=%4d  用时=%5.1fs  位置=(%6.1f,%5.2f,%6.1f) 速度=%5.2f  状态=%s  路点=%d" % [
			_f, (Time.get_ticks_msec() - _t0) / 1000.0,
			d.global_position.x, d.global_position.y, d.global_position.z,
			d.velocity.length(), ai.get_state_name() if ai else "-",
			ai.get_route_index() if ai else -1])
	if _f > 900:
		quit()
		return true
	return false
