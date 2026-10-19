# 破败石墙（可拼接）`RuinedWall`

模块化的荒废石墙：**单段 2.90 m 长**，沿本地 **+X** 一段段接下去就是任意长度的废墟墙，
接缝处看不出是拼的。也能直接怼在园区大门的两翼上继续加长（两者是同一份几何）。

- 模型：`assets/models/ruined-wall/low_poly_ruined_wall.glb`
- 生成脚本：`assets/models/ruined-wall/low_poly_ruined_wall.py`
- 共享构建代码：`assets/models/_shared/ruin_kit.py`（墙体尺寸的唯一来源）
- 单段尺寸：**2.90 × 0.99 × 2.25 m**（长 × 厚 × 高），墙厚 0.75 m、基座 0.28 m、压顶 0.20 m
- 原点：**单段中心**，底面 `y = 0`

## 两个场景，按需要选

| 场景 | 用途 |
| --- | --- |
| `ruined_wall_run.tscn` | **懒人版**：拖进场景，改 `segments` 就自动往 +X 拼 N 段 |
| `ruined_wall.tscn` | **手工版**：单段，想自己一段段摆 / 精确控制位置时用 |

## 懒人版 `RuinedWall`（`ruined_wall_run.tscn`）

```gdscript
@onready var wall: Node3D = $ParkEntrance/WallEast

wall.segments = 6            # 6 段 = 17.4 m
wall.total_length()          # -> 17.4
```

| 属性 | 默认 | 说明 |
| --- | --- | --- |
| `segments` | `4` | 拼几段（1–40） |
| `mirror_alternate` | `true` | 相邻段交替做 X 轴镜像，错开苔藓 / 塌口的位置 |
| `build_collision` | `true` | 每段挂三角面碰撞 |

**锚点在墙的起点**：第 0 段占 `x ∈ [0, 2.90]`，第 i 段占 `[(i)·2.90, (i+1)·2.90]`。
所以本节点的 `position` 就是"墙从这里开始长"。想让墙朝别的方向，旋转本节点即可。

## 手工版 `RuinedWallPiece`（`ruined_wall.tscn`）

只做一件事：给模型挂碰撞。摆位规则是**相邻两段沿本地 X 间隔 2.90 m**。

## 为什么接缝看不出来

不是靠对齐手调，是靠三条硬约定 + 脚本内断言（见 `ruin_kit.py` 文件头的「拼接缝契约」）：

1. **长度是砖模数的整数倍** —— `build_wall_segment()` 内部按 `n_bay = round(len/0.48)`
   反算砖宽，所以无论传多长，两端都不会留半块砖。
2. **两端强制满高，压顶端片取固定满厚度** —— 墙头本来逐块随机（破败感的来源），
   但端头那块如果也随机，两段接起来就会在墙顶掉一个台阶。
3. **基座 / 压顶在 X 方向不外扩** —— 只朝前后（Y）外扩，X 严格切在 `[xa, xb]`，
   于是相邻两段的基座正好对接成一整条、压顶连成一条脊。

错缝为什么能跨缝对上：偶数层首块从 `xa` 起、末块到 `xb` 止，砖缝正好落在接缝上；
奇数层两端各是半块砖，拼起来就是"一整块砖 + 一道竖缝"。两种情况都跟镜像无关，
所以 `mirror_alternate` 不会破坏接缝。

Blender 端 `verify_seams()` 会数值校验：`min(x) == -len/2`、`max(x) == +len/2`，
且左右两端面的 `(y, z)` 顶点集合完全相等，不满足直接 `AssertionError`。

实测：两端各 **108 个剖面点全等**，接缝最高 **2.25 m**，X 严格切在 **±1.45 m**。
Godot 端实测三段拼起来是 `[0, 2.9]`、`[2.9, 5.8]`、`[5.8, 8.7]`，间隙 0。

## 改尺寸要注意

改 `WALL_LEN_M`（Blender 侧单段长）时，必须同步改
`components/island/ruined_wall/ruined_wall_run.gd` 里的 `SEGMENT_LENGTH`，
否则相邻两段会错位或重叠。墙厚 / 墙高 / 基座 / 压顶则统一改 `assets/models/_shared/ruin_kit.py`，
大门两翼和这里会一起变。
