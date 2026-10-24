# 地面散布 `ground_scatter`

把成百上千的草和石头从"一个道具一个节点"改成 **MultiMesh**：
每个「分组 × 资产」只有 **1 个 `MultiMeshInstance3D`**，也就是 1 个 draw call。
每株草的变换仍然独立（MultiMesh 里逐实例存 3×4 矩阵），外观和位置**逐点不变**。

## 效果

| | 改之前 | 改之后 |
| --- | --- | --- |
| `components/island/island.tscn` | 1128 节点 / 262 KB | **132 节点 / 30 KB** + 散布场景 |
| 展示岛散布 | 988 个节点 | **17 节点**（988 实例 / 8 draw call） |
| `scenes-3d/jurassic-island/local_scatter.tscn` | 2161 节点 / 332 KB | **4 节点 / 1 KB**（900 实例） |
| 草的绘制调用 | 720（各自一个 mesh） | **2** |
| 草的阴影 | 每棵都投影 | **关闭**（上千棵草的阴影纯属浪费） |

## 目录

```
components/island/ground_scatter/
  ground_scatter.gd        # 运行时脚本：补石头碰撞、提供 instance_count()
  island_scatter.tscn      # 展示岛用的散布场景（island.tscn 里实例成 Scatter）
  island_scatter.json      # 位置数据的**源**（分组 → 资产 → 逐实例 3×4 矩阵）
  island_scatter_*.res     # 烘出来的 MultiMesh（二进制，构建产物）
  extract_scatter.py       # 老 .tscn（上千节点）→ JSON
  bake_scatter.gd          # JSON → .tscn + .res
scenes-3d/jurassic-island/
  local_scatter.tscn       # 主场景用的散布场景（4 节点）
  local_scatter.json       # 位置数据的源
  local_scatter_flat_*.res # 烘出来的 MultiMesh
```

**`.res` 是构建产物，`.json` 才是源。** 改位置就改 JSON，然后重跑烘焙：

```bash
cd /Users/zhouyunge/Documents/godot/open-jurassic-island

# 展示岛
/Applications/Godot.app/Contents/MacOS/Godot --path . --script \
  res://components/island/ground_scatter/bake_scatter.gd -- \
  components/island/ground_scatter/island_scatter.json \
  res://components/island/ground_scatter/island_scatter.tscn \
  res://components/island/ground_scatter island_scatter

# 主场景
/Applications/Godot.app/Contents/MacOS/Godot --path . --script \
  res://components/island/ground_scatter/bake_scatter.gd -- \
  scenes-3d/jurassic-island/local_scatter.json \
  res://scenes-3d/jurassic-island/local_scatter.tscn \
  res://scenes-3d/jurassic-island local_scatter
```

从老场景重新提取（需要一份还在的旧 `.tscn`）：

```bash
python3 components/island/ground_scatter/extract_scatter.py 旧场景.tscn 输出.json
```

## 挪了山 / 地形之后：`resnap_scatter.gd`

散点是**烘死的世界坐标**，山一挪、或者换了一座山，原本站在坡上的草石就会悬空 / 陷进山里。
`resnap_scatter.gd` 对着每个道具打垂直射线把它重新贴到面上：

```bash
# 展示岛的山上草石：换山时用 slide（保住原来的高度，沿坡滑到该高度对应的半径）
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . \
  --script res://components/island/ground_scatter/resnap_scatter.gd -- \
  components/island/ground_scatter/island_scatter.json Mountain \
  res://components/island/island.tscn slide

# 主场景的草石：整片重新贴一遍（高了落下、埋了抬上来，不删）
/Applications/Godot.app/Contents/MacOS/Godot --headless --path . \
  --script res://components/island/ground_scatter/resnap_scatter.gd -- \
  scenes-3d/jurassic-island/local_scatter.json "*" \
  res://scenes-3d/jurassic-island/jurassic-island.tscn project 700 700
```

三种模式：

| 模式 | 行为 | 什么时候用 |
| --- | --- | --- |
| `drop`（默认） | 只往下贴；埋进面里超过 0.5 m 的**剔除** | 原地微调地形 |
| `project` | 双向贴，不删；偏差 ≤ 0.35 m 的当成已贴地不动 | 整片草石重贴（主场景） |
| `slide` | 保住道具原来的高度，沿坡面向外找到该高度所在的位置 | **换山**（新山更陡，同高度半径不同） |

参数：`-- <json> <分组子串> [场景] [模式] [上窗口] [下窗口]`。
改完 JSON **必须重跑 `bake_scatter.gd`**（记得别加 `--headless`）。

## 三个必须知道的坑（都踩过了）

1. **不要用 `--headless` 烘 MultiMesh。**
   `--headless` 挂的是 dummy 渲染器，`MultiMesh.set_instance_transform()` 写进去的内容
   读回来是单位阵，烘出来的 `.res` 里 900 个实例会全堆在原点。
   烘焙和验证都要带真实渲染器跑（去掉 `--headless` 即可）。

2. **必须合成祖先变换。**
   `local_scatter` 的老结构是「容器 `Grass_000` 带变换 → 子节点 `GrassMesh` 才是 glb 实例且变换为单位阵」。
   只看实例节点自己的 `transform`，会把全部草石放在原点。`extract_scatter.py` 现在按
   `父变换 · 自身变换` 递归合成，并在文件头写明了这件事。

3. **保留分组层级。**
   `Scatter/Grass/MountainGrass` 这种分组本身只有几个 `Node3D`，合并 MultiMesh 只该解决
   "上千个节点"，不该把结构信息一起丢掉 —— 自检脚本还要靠 `MountainBoulders` 这个名字
   把山上的石头分出来。每株道具自己的容器（`Rock_000` 这种带数字后缀的）会被折叠掉。

## 石头碰撞

MultiMesh 本身不产生碰撞。`ground_scatter.gd` 在 `_ready()` 里补：

- 找所有**名字以 `Rock` 开头**的 `MultiMeshInstance3D`（不写死路径，兼容分组和扁平两种布局）
- 建 **1 个** `StaticBody3D`，下面挂 N 个 `CollisionShape3D`
- 所有形状**共享同一份** `ConvexPolygonShape3D`（同一块石头的网格只生成一次）
- 形状变换 = `相对本节点的实例变换`，所以父节点移动后碰撞跟着走

草不参与碰撞（玩家直接穿过去），这也是草能放心铺这么密的原因。

## 验证过什么

- 900（主场景）/ 988（展示岛）个草石的世界坐标，改前 vs 改后**逐点完全一致**（0 处偏差）。
  做法是同时实例化新旧场景，各自取出可见几何的世界坐标排序比对，**不是**拿同一份
  JSON 自比（那样会掩盖提取错误）。
- `components/island/tests/verify_island.gd`：32 项全过
- `scenes-3d/jurassic-island/tests/verify_jurassic_island.gd`：41 项全过
