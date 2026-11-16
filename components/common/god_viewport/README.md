# 公共测试视口（`components/common/god_viewport/`）

**所有测试场共用的"管理员视角"**：自由飞行 + 环顾 + 鼠标锁定。
原来这套操作只长在恐龙测试场里（`components/dinosaurs/dinosaurs_test_camera.gd`），
现在抽成公共组件，谁要测试场直接实例化，不用再抄一遍。

```
components/common/god_viewport/
├── god_viewport_camera.gd           相机脚本（extends Camera3D，class_name GodViewportCamera）
├── god_viewport_camera.tscn         可直接实例化的相机场景
├── god_viewport_capture_button.gd   「锁定鼠标 (F)」按钮（挂在 HUD 的 Button 上）
└── README.md                        本文件
```

---

## 1. 相机 `god_viewport_camera.tscn`

实例化它就有一套管理员视角：

```gdscript
[node name="Camera" parent="." instance=ExtResource("4_camera")]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 16, 48)
start_look_at = Vector3(0, 2, 0)     # 开局看向哪儿
min_height = 1.0                     # 别钻到地面底下
```

### 操作

| 键 | 作用 |
| --- | --- |
| `↑` `↓` | 水平面前进 / 后退（`W` `S` 同义） |
| `←` `→` | 水平面左右平移（`A` `D` 同义） |
| `Space` | 上升（`E` 同义） |
| `Ctrl` | 下降（`Q` 同义） |
| `Shift` | 加速（×3） |
| `Alt` | 减速（×0.25） |
| 鼠标**右键拖动** | 转视角 |
| `F` | 锁定 / 释放鼠标 |

前后左右走的是**水平面**（跟着视角的偏航转），升降单独用 `Space` / `Ctrl` ——
俯视着看的时候按方向键是平移，不会一头扎进地里。

### 参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `move_speed` | 25 | 基础速度（米/秒） |
| `sprint_multiplier` | 3.0 | `Shift` 加速倍率 |
| `slow_multiplier` | 0.25 | `Alt` 减速倍率 |
| `min_height` | `-INF` | 相机最低世界高度（不限制就填 `-INF`） |
| `mouse_sensitivity` | 0.0025 | 鼠标灵敏度（弧度/像素） |
| `pitch_limit_deg` | 85 | 俯仰上限（度） |
| `start_look_at` | `Vector3.ZERO` | 开局看向哪儿（零向量 = 保持场景朝向） |

### 为什么鼠标默认不锁定

HUD 上有按钮，鼠标锁定了就点不到。所以默认**不锁**：右键拖动转视角，
左键点击在光标处操作。按 `F` 锁上以后就是第一人称那种手感 ——
视角跟着鼠标走，准星在屏幕正中，左键在准星处操作。

锁定状态变了会发 `capture_changed(captured: bool)` 信号。

### 怎么找到这个相机

相机启动时会把自己加进 **`god_viewport_camera`** 组，
所以 HUD 上的按钮不用配路径就能找到它（见下面）。

---

## 2. 「锁定鼠标 (F)」按钮 `god_viewport_capture_button.gd`

挂在 HUD 的 Button 上就行，**不用写任何接线**：

```gdscript
[node name="Mouse" type="Button" parent="TestHUD/Bar"]
custom_minimum_size = Vector2(130, 0)
text = "锁定鼠标 (F)"
toggle_mode = true
script = ExtResource("5_capture_btn")
```

它会自动：

- 在 `god_viewport_camera` 组里找到相机
- 点按钮 = 锁定 / 释放鼠标
- 按钮文字跟着锁定状态变（「锁定鼠标 (F)」↔「释放鼠标 (F)」）
- 锁定时把**同一个 CanvasLayer 里的 `Crosshair`** 标签显示出来

所以测试场里要加准星的话，节点名必须叫 **`Crosshair`**（放在按钮所在的
那个 `CanvasLayer` 下面）。

---

## 3. 谁在用

| 测试场 | 相机 |
| --- | --- |
| `components/dinosaurs/dinosaurs_test.tscn` | 实例 `god_viewport_camera.tscn`（`min_height = 1.0`） |
| `components/island-grass/island_grass_test.tscn` | 实例 `god_viewport_camera.tscn`（`min_height = 1.0`） |

两个测试场的 HUD 上都有同一个「锁定鼠标 (F)」按钮，都不写接线代码。

> ⚠️ 改公共组件前先看这两个测试场 —— 改坏了两个都跑不起来。
> 相机脚本原来叫 `dinosaurs_test_camera.gd`（在恐龙组件里），
> 现在搬到这儿，类名是 `GodViewportCamera`。
