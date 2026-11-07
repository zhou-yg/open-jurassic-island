extends SceneTree
## 临时探针：统计每只恐龙在测试期间走了多远、停住了多久。

const SCENE := "res://components/island/island.tscn"
var _f := 0
var _scene: Node3D
var _prev := {}
var _dist := {}
var _frozen := {}
var _phys0 := 0


func _process(_dt: float) -> bool:
	_f += 1
	if _f == 5:
		_scene = load(SCENE).instantiate()
		root.add_child(_scene)
		_phys0 = Engine.get_physics_frames()
		return false
	if _f > 8:
		_track()
	if _f > 900:
		var phys := Engine.get_physics_frames() - _phys0
		print("=== 跑了 %d 个物理帧（%.1f 秒）===" % [phys, phys / 60.0])
		for n in _dist:
			print("  %-20s 走了 %6.1f m  平均 %4.2f m/s  定住 %4d 帧" % [
				n, _dist[n], _dist[n] / maxf(1.0, phys / 60.0), int(_frozen.get(n, 0))])
		quit()
		return true
	return false


func _track() -> void:
	for d in _scene.get_node("Dinosaurs").get_children():
		var ai = d.get_node_or_null("AI")
		if ai == null: continue
		var pos: Vector3 = d.global_position
		if _prev.has(d.name):
			var moved: float = (_prev[d.name] as Vector3).distance_to(pos)
			_dist[d.name] = float(_dist.get(d.name, 0.0)) + moved
			var busy: bool = ai.get_state_name() in ["巡逻", "追击", "调查", "逃跑", "脱困"]
			if busy and moved < 0.004:
				_frozen[d.name] = int(_frozen.get(d.name, 0)) + 1
		_prev[d.name] = pos
