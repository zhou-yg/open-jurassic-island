extends SceneTree
## 烘主场景的本地草石（**命令行入口**）。
##
## 真正的活儿在 `bake_local_grass_core.gd` 里 —— 拆成两个文件是为了同一份逻辑
## 既能命令行跑，也能挂进场景里跑（后台模式，窗口不弹出来）。

func _initialize() -> void:
	var core: Node = load("res://scenes-3d/jurassic-island/bake_local_grass_core.gd").new()
	root.add_child(core)
