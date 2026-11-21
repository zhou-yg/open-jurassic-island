# m3f-banana —— 新的低多边形香蕉树（树 / 果串分离）

照 `reference.png`（2×2 四个变体）复刻的香蕉树。**树体和香蕉是两个独立的资产**，
可以单独用、单独换、单独做采集逻辑。

| 文件 | 内容 | 原点 | 面数 |
| --- | --- | --- | --- |
| `m3f_banana_tree.glb` | 树体：`M3FBanana_Stalk` / `M3FBanana_Leaves` / `M3FBanana_Grass` | 地面中心 (0,0,0) | 1604 三角面 |
| `m3f_banana_bunch.glb` | 果串：`M3FBanana_BunchStem` + `M3FBanana_Fruit_01` … `M3FBanana_Fruit_16` | 果柄与树体相连的一端 | 1326 三角面 |
| `m3f_banana.py` | **唯一事实来源**：改模型改脚本，别手改 `.glb` | — | — |
| `m3f_banana_*_preview.png` | 四视图预览（Blender 自己渲的） | — | — |
| `m3f_banana_assembled_preview.png` | 树 + 果串拼起来的效果 | — | — |

尺寸（米，1:1）：树高 **2.81**、冠幅 **2.43**；假茎底半径 0.125、高 1.52；
果串 **0.66 × 0.66 × 0.65**；单根香蕉长 0.30~0.36。

## 在 Godot 里怎么用

```gdscript
# 1) 摆树：原点就在地面中心，position 直接给落地点，scale 保持 1
var tree := preload("res://assets/models/m3f-banana/m3f_banana_tree.glb").instantiate()

# 2) 挂果串：果串是"悬挂物"，原点在果柄顶端，整串在 y=0 以下
var bunch := preload("res://assets/models/m3f-banana/m3f_banana_bunch.glb").instantiate()
bunch.position = Vector3(0.060, 1.45, 0.0)   # 树体局部坐标：果柄根部埋进假茎侧面
tree.add_child(bunch)
```

* 果串的 16 根香蕉是**独立网格节点**（`M3FBanana_Fruit_01` … `_16`），
  要做"采集几根就少几根"直接切 `visible` 即可，和
  `components/banana-tree/` 现有的做法一致。
* 不想带脚下的草：删掉树体里的 `M3FBanana_Grass` 节点。
* ⚠️ **不要用 Godot 侧 `scale` 调大小** —— 模型已经是 1:1 米制。

## 重新生成

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python m3f_banana.py
# 只建模、不渲预览（快很多）：
/Applications/Blender.app/Contents/MacOS/Blender --background --python m3f_banana.py -- --no-render
```

脚本末尾会打印 `TREE CHECK` / `BUNCH CHECK`（尺寸 / 面数 / 材质 / scale 自检）。
细节、配色来源和踩过的坑见 `assets/AGENTS.md` §2.13。
