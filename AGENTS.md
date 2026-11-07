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

scenes-3d/jurassic-island/
- 游戏主场景
- jurassic-island.tscn 入口