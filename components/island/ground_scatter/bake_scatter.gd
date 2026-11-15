extends SceneTree
## 把散点 JSON 烘成 MultiMesh 场景：每个"分组 × 资产"只有 1 个 MultiMeshInstance3D。
##
## 真正的活儿在 `bake_scatter_core.gd` 里 —— 拆成两个文件是为了同一份逻辑
## 既能命令行跑，也能挂进场景里跑（后台模式，窗口不弹出来）。
##
## 输入：extract 脚本产出的 JSON，形如
##   { "Scatter/Grass/IslandGrass": {"grass_tuft": [[12 floats], ...], ...}, ... }
## 输出：一个场景（根上挂 ground_scatter.gd）+ 每个资产一份二进制 .res（MultiMesh）。
##
## 用法：
##   godot --path . --script res://components/island/ground_scatter/bake_scatter.gd -- \
##         <json> <out_tscn> <res_dir> <res_prefix>
##
## ⚠️ 必须带真实渲染器（MultiMesh 的实例变换在 RenderingServer 里）。

func _initialize() -> void:
	var core: Node = load("res://components/island/ground_scatter/bake_scatter_core.gd").new()
	root.add_child(core)
