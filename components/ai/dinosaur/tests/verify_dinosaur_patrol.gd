extends Node
## 恐龙**巡逻生命周期**自检。
##
## ## 为什么要有这个
##
## 之前恐龙的"歇一会儿"是没有出口的：巡完第一圈之后
## `should_rest()` 永远返回 true，恐龙就再也不巡逻了 ——
## 站桩到游戏结束。这个自检盯的就是这条生命周期：
##
## ```
## PATROL ──巡完一圈──▶ REST ──歇够 rest_time──▶ PATROL ──▶ …
## ```
##
## 跑法：
## [codeblock]
## godot --path . --script res://components/ai/dinosaur/tests/verify_dinosaur_patrol.gd
##
## # 或者挂进场景跑（后台模式，窗口不弹出来）：
## godot --path . res://components/ai/dinosaur/tests/verify_dinosaur_patrol.tscn
## [/codeblock]
##
## ## 为什么把时间加快
##
## 绕一圈约 40 s，等不起。这里用 [member Engine.time_scale] 把时间加快
## [constant TIME_SCALE] 倍：恐龙的物理也跟着变快，一圈只要十几秒。
## 代价是碰撞可能被"穿"过去（围栏只有 0.6 m 厚），但这个自检只看
## 状态机的生命周期，不看它有没有撞墙。

const SCENE: String = "res://components/island/island.tscn"
## 时间加快多少倍。
const TIME_SCALE := 2.0
## 跑多久（**游戏内**秒数）。
const RUN_SECONDS := 260.0
## 采样间隔（游戏内秒数）。
const SAMPLE_INTERVAL := 0.2
## 一只恐龙在 REST 里最多待多久（游戏内秒）才算"歇够了又回来了"。
## rest_time 是 6 s，留 3 倍余量给掉帧。
const MAX_REST_SECONDS := 18.0

var _scene: Node3D
var _game_time := 0.0
var _sample_timer := 0.0
var _done := false
var _checks := 0
var _failures := 0
## 每只恐龙：{ 圈数, 见过休息, 休息之后又巡逻过, 最长单次休息时长, 当前状态 }
var _stats: Dictionary = {}


func _ready() -> void:
	Engine.time_scale = TIME_SCALE
	_scene = load(SCENE).instantiate()
	get_tree().root.add_child.call_deferred(_scene)


func _process(delta: float) -> void:
	if _done:
		return
	if _scene == null or not _scene.is_inside_tree():
		return
	_game_time += delta
	_sample_timer += delta
	if _sample_timer >= SAMPLE_INTERVAL:
		_sample_timer = 0.0
		_sample()
	if _game_time >= RUN_SECONDS:
		_done = true
		_report()
		Engine.time_scale = 1.0
		get_tree().quit(1 if _failures > 0 else 0)


## 每只恐龙的当前状态记一笔。
func _sample() -> void:
	var dinos := _scene.get_node_or_null("Dinosaurs")
	if dinos == null:
		return
	for dino in dinos.get_children():
		if not (dino is Node3D) or String(dino.name) == "Boundary":
			continue
		var ai := dino.get_node_or_null("AI")
		if ai == null:
			continue
		var state := String(ai.get_state_name())
		var laps := int(ai.get_laps())
		if not _stats.has(dino.name):
			_stats[dino.name] = {
				"laps": 0, "saw_rest": false, "patrol_after_rest": false,
				"rest_run": 0.0, "max_rest_run": 0.0, "last_state": "",
			}
		var s: Dictionary = _stats[dino.name]
		s["laps"] = laps
		if state == "休息":
			s["saw_rest"] = true
			s["rest_run"] = float(s["rest_run"]) + SAMPLE_INTERVAL
			s["max_rest_run"] = maxf(float(s["max_rest_run"]), float(s["rest_run"]))
		else:
			s["rest_run"] = 0.0
			# 休息之后**又巡逻了** —— 这就是"歇完能接着走"的证据
			if bool(s["saw_rest"]) and state == "巡逻":
				s["patrol_after_rest"] = true
		s["last_state"] = state


func _report() -> void:
	print("=== 恐龙巡逻生命周期自检 ===")
	for name in _stats.keys():
		var s: Dictionary = _stats[name]
		_check(int(s["laps"]) >= 1, "%s 一圈都没巡完（%d 圈）" % [name, int(s["laps"])])
		_check(bool(s["saw_rest"]), "%s 从来没有休息过（说明没巡完一圈）" % name)
		_check(bool(s["patrol_after_rest"]),
			"%s 休息之后没有再巡逻（'歇一会儿'没有出口）" % name)
		_check(float(s["max_rest_run"]) <= MAX_REST_SECONDS,
			"%s 一次休息拖了 %.1f s（歇完应该接着巡逻）" % [
				name, float(s["max_rest_run"])])
		print("  %-22s 圈数=%d 见过休息=%s 休息后继续巡逻=%s 最长休息=%.1fs 当前=%s" % [
			name, int(s["laps"]), str(bool(s["saw_rest"])),
			str(bool(s["patrol_after_rest"])), float(s["max_rest_run"]),
			str(s["last_state"])])
	print("=== 检查项 %d，失败 %d ===" % [_checks, _failures])
	print("全部通过 ✅" if _failures == 0 else "存在失败 ❌")


func _check(condition: bool, message: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		print("  [FAIL] ", message)
