extends SceneTree
## 世界尺度（2000 m 岛）的植被 + 恐龙**烘焙脚本（命令行入口）**。
##
## 真正的活儿在 `bake_world_vegetation_core.gd` 里 —— 拆成两个文件是为了同一份
## 逻辑既能命令行跑，也能**挂进场景里**跑（`bake_world_vegetation.tscn`）。
##
## ## 用法（**必须带真实渲染器，不要加 `--headless`** —— headless 的 dummy
## ## 渲染器会把 MultiMesh 的实例变换全丢掉，烘出来是一堆零矩阵）：
## [codeblock]
## godot --path . --script res://scenes-3d/jurassic-island/bake_world_vegetation.gd
## [/codeblock]

func _initialize() -> void:
	var core: Node = load("res://scenes-3d/jurassic-island/bake_world_vegetation_core.gd").new()
	root.add_child(core)
