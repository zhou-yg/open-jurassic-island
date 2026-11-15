extends SceneTree
## 烘"主场景用的局部入口"（**命令行入口**）。
##
## 真正的活儿在 `bake_entrance_local_core.gd` 里 —— 拆成两个文件是为了同一份
## 逻辑既能命令行跑，也能挂进场景里跑（后台模式，窗口不弹出来）。
##
## 用法（**必须带真实渲染器**）：
##   godot --path . --script res://components/island/park_perimeter/bake_entrance_local.gd -- <out_tscn> [seed]

func _initialize() -> void:
	var core: Node = load("res://components/island/park_perimeter/bake_entrance_local_core.gd").new()
	root.add_child(core)
