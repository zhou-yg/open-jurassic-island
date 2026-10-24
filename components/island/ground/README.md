# 地形合批（Ground MultiMesh）

`island.tscn` 的 `Ground` 下面只有 **1 个节点**：

```
Ground (Node3D)
└── Terrain (MultiMeshInstance3D)   ← multimesh = island_ground.res，116 个实例
```

## 为什么

116 块 `plain_terrain.glb` 用的是**同一份网格**，只是变换不同。按场景实例摆的话：

| | 逐块实例 | MultiMesh |
| --- | --- | --- |
| 节点数 | 116（每块一整棵场景：Root + MeshInstance3D + 导入材质） | **1** |
| draw call | 464（116 × 4 个表面） | **4** |
| 网格内存 | 116 份 | **1 份** |
| 地形碰撞 | 116 份三角面形状 | **1 份**，116 个 `CollisionShape3D` 共享 |

碰撞是 `island.gd` 在运行时补的（MultiMesh 本身不产生碰撞）：一个
`StaticBody3D` 挂在 `Terrain` 下面，每个实例一个 `CollisionShape3D`，
形状资源只有一份。

## 文件

| 文件 | 作用 |
| --- | --- |
| `island_ground.json` | **摆放数据的源**：`glb` + 每个地块一行 12 个 float（basis.x / basis.y / basis.z / origin） |
| `island_ground.res` | 烘出来的二进制 `MultiMesh`（被两个岛场景引用），**不要手改** |
| `bake_ground.gd` | 提取 / 烘焙脚本 |

## 改地块 → 改 JSON → 重烘

**必须带真实渲染器（不要加 `--headless`）。** MultiMesh 的实例变换建立在
RenderingServer 上，headless 的 dummy 渲染器会把 `set_instance_transform` 全丢掉，
存出来是一堆零矩阵（加载时物理直接报 `det == 0`）。和
`ground_scatter/bake_scatter.gd` 是同一个坑。

```bash
cd /Users/zhouyunge/Documents/godot/open-jurassic-island

# 日常：改完 JSON 重烘
/Applications/Godot.app/Contents/MacOS/Godot --path . \
  --script res://components/island/ground/bake_ground.gd -- \
  res://components/island/ground/island_ground.json \
  res://components/island/ground/island_ground.res

# 需要从旧场景（Ground 下还是逐块 MeshInstance3D）重新提取时：
/Applications/Godot.app/Contents/MacOS/Godot --path . \
  --script res://components/island/ground/bake_ground.gd -- \
  res://components/island/island.tscn \
  res://components/island/ground/island_ground.json \
  res://components/island/ground/island_ground.res
```

## 自检

```bash
/Applications/Godot.app/Contents/MacOS/Godot --path . \
  --script res://components/island/tests/verify_island.gd
```

同样**不能 headless**（草石的 MultiMesh 变换也读不到）。检查项里会核对：
`Ground` 下没有逐块 `MeshInstance3D`、`Terrain` 是 MultiMesh、实例 ≥ 100、
碰撞体数量与实例一致且共享同一份形状。
