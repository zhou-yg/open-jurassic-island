extends SceneTree
## 低模岛组件自检（**命令行入口**）。
##
## 真正的活儿在 `verify_island_core.gd` 里 —— 拆成两个文件是为了同一份逻辑
## 既能命令行跑，也能挂进场景里跑（`verify_island.tscn`），
## 后者可以用后台模式启动 Godot，**窗口不会弹出来**。
##
## 运行方式（在项目根目录执行）：
## [codeblock]
## /Applications/Godot.app/Contents/MacOS/Godot --path . \
##     --script res://components/island/tests/verify_island.gd
## [/codeblock]
## 全部通过时退出码为 0，否则为 1。

func _initialize() -> void:
	var core: Node = load("res://components/island/tests/verify_island_core.gd").new()
	root.add_child(core)
