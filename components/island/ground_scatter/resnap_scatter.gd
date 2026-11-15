extends SceneTree
## 把散点 JSON 里指定分组的道具重新贴到"它正下方的那个面"上。
##
## 真正的活儿在 `resnap_scatter_core.gd` 里 —— 拆成两个文件是为了同一份逻辑
## 既能命令行跑，也能挂进场景里跑（后台模式，窗口不弹出来）。
##
## 什么时候需要：挪动山体 / 地形之后。散点是烘死的坐标，地形一改，
## 原本站在上面的石头就悬空或陷进去了。
##
## 用法：
##   godot --path . --script res://components/island/ground_scatter/resnap_scatter.gd -- \
##         <json> <分组名包含的子串> [场景] [模式] [上窗口] [下窗口]
##
##   场景      默认 res://components/island/island.tscn
##   模式      drop（默认）/ project / slide
##             drop    往下贴：高了就落下来，埋进面里（高了 0.5 m 以上）的直接剔除
##             project 双向贴：不管高了低了都放到正下方那个面上，一个不删
##             slide   沿坡滑：保住道具原来的高度，沿坡面找到该高度所在的位置
##   上/下窗口  射线窗口（米），默认 6
##
## 改完 JSON 记得重新烘 MultiMesh（bake_scatter.gd，**不能**加 --headless）。

func _initialize() -> void:
	var core: Node = load("res://components/island/ground_scatter/resnap_scatter_core.gd").new()
	root.add_child(core)
