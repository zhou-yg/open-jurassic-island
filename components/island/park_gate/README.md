# 园区入口大门 `ParkGate`

荒废侏罗纪园区的大门组件。门楣是一块被苔藓爬过的木匾，上面凸着 **"dinosaur"** 几个字；
中间半圆拱券，两侧矮墙继续残破下去；两扇绣铁门静止时是**合**的。

- 模型：`assets/models/jurassic-gate/low_poly_jurassic_gate.glb`
- 生成脚本：`assets/models/jurassic-gate/low_poly_jurassic_gate.py`（改模型请改脚本后重新生成）
- 尺寸：**10.56 × 1.40 × 6.24 m**（宽 × 厚 × 高），门洞净宽 **3.20 m**、净高 **2.95 m**
- 原点：**门洞地面中线**，所以 `position` 就是"门槛落地点"，`y = 0` 即地面
- 朝向：正面朝 **+Z**，门扇也朝 **+Z** 向外开

## 用法

```gdscript
@onready var gate: Node3D = $ParkEntrance/ParkGate

func _on_player_approach() -> void:
    gate.open()      # 播 Gate_Open：0.4 s 开到位，之后保持

func _on_player_leave() -> void:
    gate.close()     # 播 Gate_Close：0.4 s 合上
```

也可以在检查器里直接勾 `is_open` 看效果，或者在编辑器里改它来预览开合姿态。

## 两条内置动画（GLB 自带，不必另做动画）

| 片段 | 时长 | 内容 |
| --- | --- | --- |
| `Gate_Open` | 1.20 s | 0.00 s 合(0°) → 0.40 s 开(±88°) → 保持到 1.20 s |
| `Gate_Close` | 1.20 s | 0.00 s 开(±88°) → 0.40 s 合(0°) → 保持到 1.20 s |

两段都是"行程 0.4 s + 保持 0.8 s"，所以播完**停住不回弹**。
两扇门共用一条 Action，`AnimationPlayer` 一次就把左右门扇同时驱动了。

> 门轴方向是有讲究的：两扇门的网格互为镜像，动画里已经算成"都朝门外摆"。
> 不要在组件里自己算角度，否则会变成两扇门朝同一侧推倒。

## 导出参数

| 属性 | 默认 | 说明 |
| --- | --- | --- |
| `is_open` | `false` | 当前是否打开。改它会立刻切姿态（并 emit `opened` / `closed`） |
| `build_collision` | `true` | 给每个网格挂 `StaticBody3D` + 三角面碰撞 |
| `animate` | `true` | 关掉后只切姿态、不播动画（远景装饰门用） |
| `speed` | `1.0` | 播放速度倍率 |

信号：`opened`、`closed`。

## 碰撞

每个网格下都会生成 `Body`（`StaticBody3D`）+ `Shape`（三角面 `CollisionShape3D`）。
门扇的碰撞体挂在**门扇节点下面**，所以会跟着门轴一起转 —— 关着门能挡人，开了门就能走过去。

碰撞只在**运行时**生成（`_ready()` 里跳过 `Engine.is_editor_hint()`），
编辑器里不会往场景文件里塞临时节点。

## 接墙加长

大门两侧矮墙的**外端是"接缝端"**：基座不外扩、压顶必留一片、墙头强制满高。
所以可以直接在 `x = ±5.05` 处接上 `components/island/ruined_wall/` 的破墙模块继续加长，
接缝处不会有台阶或洞。两端面剖面已用数值校验过与 `low_poly_ruined_wall` 完全一致
（108 个剖面点全等）。

`components/island/island.tscn` 里的 `ParkEntrance` 就是这么摆的：门 + 东西各 3 段破墙。
