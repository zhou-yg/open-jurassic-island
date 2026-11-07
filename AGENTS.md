# 侏罗纪岛

godot 开发的独立游戏，第一人称，生存，建造，冒险游戏

游戏简介：
在几十分钟的限定时间内，建造工具，抵御恐龙，最后通过救援直升机逃出恐龙岛

low-poly 风格

## 模型规范

涉及建模时看 ./assets/AGENTs.md

### 工作方式

- **建模 / 素材类任务不要擅自启动 Godot**（编辑器、运行时都不行）。
  只有任务明确涉及**改 `.tscn` 场景**，或明确要求"在游戏里跑一下"时才启动；
  需要在 Godot 里验证的，**先说明理由并征求同意**。
- 资产侧的验证一律用 Blender headless + 直接读 `.glb` 的 JSON（动画片段、通道数、
  材质色、包围盒）+ 脚本末尾的自检输出，**不靠 Godot 导入来验**。
  详见 `assets/AGENTS.md` §0。


## 核心项目结构

assets/models
- 3d模型

components
- 核心场景组件，基于模型构建的最基础逻辑单元

components/island
- 核心岛屿

components/vegetation
- 植被组件：`banana_tree`（香蕉树 + 果串）、`dinosaur`（恐龙的身体 + 模型）
  - 恐龙：**每种一个 .tscn**（`t_rex.tscn` / `triceratops.tscn` / …），
    每个场景里带模型、体型、胶囊和 AI 节点

components/ai/dinosaur
- 恐龙的**独立 AI 模块**：感官 → 黑板 → 决策 → 转向 → 身体
  - `dinosaur_perception.gd` 视听（**视线会被树挡住**，玩家能躲树）
  - `dinosaur_blackboard.gd` 共享记忆
  - `dinosaur_ai.gd` 状态机（PATROL / INVESTIGATE / CHASE / ATTACK / FLEE / REST）
  - `dinosaur_steering.gd` 转向 / 避障 / 群体分离
  - `dinosaur_body.gd` 身体的契约 + 执行器
  - `dinosaur_ai_config.gd` 每种恐龙的调参表
  - 改行为改这里，不要改岛屿组件

scenes-3d/jurassic-island/
- 游戏主场景
- jurassic-island.tscn 入口

## 碰撞层约定（3D）

`project.godot` 的 `layer_names` 里命名了 5 层：

| 层 | 名字 | 谁在上面 |
| --- | --- | --- |
| 1 | world | 地形、山体、岛体 |
| 2 | vegetation | 香蕉树的树干 |
| 3 | structure | 园区围墙、大门 |
| 4 | prop | 石头、碎石 |
| 5 | creature | 玩家、恐龙 |

**恐龙只勾 world + creature** —— 树、墙、石头都不挡它，
巡逻不会卡住；但**视线**会被树挡住（玩家能躲树）。
细节见 `components/ai/dinosaur/README.md`。