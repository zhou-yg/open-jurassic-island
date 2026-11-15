extends SceneTree
## 香蕉树林 + 恐龙的**烘焙脚本（命令行入口）**。
##
## 真正的活儿在 `bake_vegetation_core.gd` 里 —— 拆成两个文件是为了同一份逻辑
## 既能命令行跑，也能**挂进场景里**跑：把 core 挂到一个节点上、用后台模式
## 启动 Godot，窗口就不会弹出来（大世界的烘焙就是这么跑的）。
##
## 为什么要烘：岛上要"很密"的树（几百棵）。逐棵摆成场景实例 = 几百个节点、
## 几百个 draw call、几百份网格内存；而且布局必须是**固定**的（每次打开位置
## 完全一样），不能运行时随机。烘成 MultiMesh 之后：节点 2 个、
## draw call 4 个（2 种树 × 每个 2 个表面）、网格内存 2 份。
##
## 布局全部来自 FastNoiseLite 采样：
##   - **密度场**决定哪里是林子、哪里是空地（空地留给恐龙和玩家）；
##   - **款式场**决定这一棵是高款还是矮款 —— 两种树成片交错，不会东一棵高
##     西一棵矮地乱跳，整体比例也接近对半；
##   - **道路**：双环 + 四条辐条，路面上不长树 —— 冒险者顺着路跑，
##     恐龙也能沿着路巡逻；林子里的树则可以当掩体躲开恐龙的视野。
##
## ## 用法（**必须带真实渲染器，不要加 `--headless`** —— headless 的 dummy
## ## 渲染器会把 MultiMesh 的实例变换全丢掉，烘出来是一堆零矩阵）：
## [codeblock]
## # 重新生成布局 + 重新烘焙（换种子 / 改参数后跑这个）
## godot --path . --script res://components/island/vegetation/bake_vegetation.gd -- all
##
## # 只按现有 JSON 重新烘 .res + .tscn（改了 JSON 之后跑这个）
## godot --path . --script res://components/island/vegetation/bake_vegetation.gd -- bake
##
## # 换一套布局（换种子）
## godot --path . --script res://components/island/vegetation/bake_vegetation.gd -- all 20260715
## [/codeblock]

func _initialize() -> void:
	var core: Node = load("res://components/island/vegetation/bake_vegetation_core.gd").new()
	root.add_child(core)
