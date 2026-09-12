extends Node2D
## Scratch demo that instantiates the War3-style TopBar and simulates a
## day/night cycle + resource ticks so the component can be seen running.

const TopBarScene := preload("res://scenes/ui/top_bar/top_bar.tscn")

var top_bar: Control
var _clock: float = 6.0
var _tick: float = 0.0

var _res: Dictionary = {
	"wood": 120,
	"stone": 45,
	"banana": 90,
}

func _ready() -> void:
	# HUD must live under a CanvasLayer so the Control can anchor to the
	# full viewport width. A bare Node2D parent gives the Control no valid
	# layout rect, so it collapses to width 0.
	var layer := CanvasLayer.new()
	layer.name = "HUDLayer"
	add_child(layer)
	top_bar = TopBarScene.instantiate()
	layer.add_child(top_bar)
	top_bar.set_time(6.0, 0)
	top_bar.set_resources(_res)

func _process(delta: float) -> void:
	# advance a full day every ~40s
	_tick += delta
	if _tick >= 0.05:
		_tick = 0.0
		_clock = fposmod(_clock + 0.05 * (24.0 / 40.0), 24.0)
		var h := int(_clock)
		var m := int((_clock - h) * 60.0)
		top_bar.set_time(float(h), m)

	# slowly grow resources so counters visibly tick
	if _now_sec() % 300 < 3:
		_res["wood"] = min(_res["wood"] + 1, 999)
		_res["stone"] = min(_res["stone"] + 1, 999)
		_res["banana"] = min(_res["banana"] + 1, 999)
		top_bar.set_resource("wood", _res["wood"])
		top_bar.set_resource("stone", _res["stone"])
		top_bar.set_resource("banana", _res["banana"])

var _start_sec := 0
func _now_sec() -> int:
	if _start_sec == 0:
		_start_sec = int(Time.get_ticks_msec() / 1000.0)
	return int(Time.get_ticks_msec() / 1000.0) - _start_sec