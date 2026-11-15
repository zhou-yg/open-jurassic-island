extends SceneTree
## 2000 m 主岛场景自检（**命令行入口**）。
##
## 真正的活儿在 `verify_jurassic_island_core.gd` 里 —— 拆成两个文件是为了同一份
## 逻辑既能命令行跑，也能挂进场景里跑（`verify_jurassic_island.tscn`），
## 后者可以用后台模式启动 Godot，**窗口不会弹出来**。
##
## 运行方式：
## [codeblock]
## /Applications/Godot.app/Contents/MacOS/Godot \
##   --script res://scenes-3d/jurassic-island/tests/verify_jurassic_island.gd
## [/codeblock]
## 全部通过时退出码为 0，否则为 1。

func _initialize() -> void:
	var core: Node = load("res://scenes-3d/jurassic-island/tests/verify_jurassic_island_core.gd").new()
	root.add_child(core)
