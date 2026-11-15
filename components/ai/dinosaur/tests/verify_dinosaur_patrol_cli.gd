extends SceneTree
## 恐龙巡逻生命周期自检（**命令行入口**）。
##
## 真正的活儿在 `verify_dinosaur_patrol.gd` 里 —— 拆成两个文件是为了同一份
## 逻辑既能命令行跑，也能挂进场景里跑（后台模式，窗口不弹出来）。

func _initialize() -> void:
	var core: Node = load("res://components/ai/dinosaur/tests/verify_dinosaur_patrol.gd").new()
	root.add_child(core)
