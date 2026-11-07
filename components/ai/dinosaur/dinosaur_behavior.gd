class_name DinosaurBehavior
extends RefCounted
## 恐龙的**决策树**（行为树）。
##
## 这里是"恐龙现在该干什么"的全部逻辑，决策的形状一目了然：
##
## [codeblock]
## 根（选择器：按优先级试）
##  ├ 濒死   （并且）血量归零        → 倒下
##  ├ 脱困   （并且）卡住了          → 退出来
##  ├ 逃跑   （并且）威胁逼近        → 远离威胁
##  ├ 攻击   （并且）目标够得着      → 挥击
##  ├ 追击   （并且）还记得目标      → 追上去
##  ├ 调查   （并且）有兴趣点        → 去看看
##  ├ 休息   （并且）该歇了          → 站着
##  ├ 觅食   （并且）饿了（预留）    → 去找吃的
##  └ 巡逻                            → 沿路线走（兜底）
## [/codeblock]
##
## 每一帧从上往下试，**第一个走通的分支就是这一帧的行为**。
## 状态机（[DinosaurStateMachine]）只负责记住"现在是哪个状态"。
##
## 预留分支的条件恒为假 —— 行为还没做，但位置留好了：
## 想做的时候把条件换成真的、再填 [method DinosaurAI.behave_reserved] 就行。

## 造出恐龙的决策树。
static func build(ai: DinosaurAI) -> BehaviorTree:
	var root := BtComposite.Selector.new("根")

	# ---- 1. 濒死 ----
	var dead := BtComposite.Sequence.new("濒死")
	dead.add_child(BtLeaf.condition("血量归零", func(_d: float) -> bool:
		return ai.is_dead()))
	dead.add_child(BtLeaf.action("倒下", func(d: float) -> int:
		return ai.behave_dead(d)))
	root.add_child(dead)

	# ---- 2. 脱困 ----
	# 被树 / 墙 / 石头夹住了：先退出来，巡逻才不会停
	var unstick := BtComposite.Sequence.new("脱困")
	unstick.add_child(BtLeaf.condition("卡住了", func(_d: float) -> bool:
		return ai.is_stuck()))
	unstick.add_child(BtLeaf.action("退出来", func(d: float) -> int:
		return ai.behave_unstick(d)))
	root.add_child(unstick)

	# ---- 3. 逃跑 ----
	var flee := BtComposite.Sequence.new("逃跑")
	flee.add_child(BtLeaf.condition("威胁逼近", func(_d: float) -> bool:
		return ai.is_threatened()))
	flee.add_child(BtLeaf.action("远离威胁", func(d: float) -> int:
		return ai.behave_flee(d)))
	root.add_child(flee)

	# ---- 4. 攻击 ----
	var attack := BtComposite.Sequence.new("攻击")
	attack.add_child(BtLeaf.condition("目标够得着", func(_d: float) -> bool:
		return ai.can_attack()))
	attack.add_child(BtLeaf.action("挥击", func(d: float) -> int:
		return ai.behave_attack(d)))
	root.add_child(attack)

	# ---- 5. 追击 ----
	var chase := BtComposite.Sequence.new("追击")
	chase.add_child(BtLeaf.condition("还记得目标", func(_d: float) -> bool:
		return ai.remembers_target()))
	chase.add_child(BtLeaf.action("追上去", func(d: float) -> int:
		return ai.behave_chase(d)))
	root.add_child(chase)

	# ---- 6. 调查 ----
	var investigate := BtComposite.Sequence.new("调查")
	investigate.add_child(BtLeaf.condition("有兴趣点", func(_d: float) -> bool:
		return ai.has_interest()))
	investigate.add_child(BtLeaf.action("去看看", func(d: float) -> int:
		return ai.behave_investigate(d)))
	root.add_child(investigate)

	# ---- 7. 休息 ----
	var rest := BtComposite.Sequence.new("休息")
	rest.add_child(BtLeaf.condition("该歇了", func(_d: float) -> bool:
		return ai.should_rest()))
	rest.add_child(BtLeaf.action("站着", func(d: float) -> int:
		return ai.behave_rest(d)))
	root.add_child(rest)

	# ---- 8. 觅食（**预留**：行为还没做，条件恒假）----
	# 想做的时候：把条件换成"饥饿度低于阈值"，再实现
	# DinosaurAI.behave_reserved(State.HUNGER, delta) 就行。
	var hunger := BtComposite.Sequence.new("觅食（预留）")
	hunger.add_child(BtLeaf.condition("饿了（预留）", func(_d: float) -> bool:
		return false))
	hunger.add_child(BtLeaf.action("去找吃的（预留）", func(d: float) -> int:
		return ai.behave_reserved(DinosaurStateMachine.State.HUNGER, d)))
	root.add_child(hunger)

	# ---- 9. 巡逻（兜底）----
	root.add_child(BtLeaf.action("巡逻", func(d: float) -> int:
		return ai.behave_patrol(d)))

	return BehaviorTree.new(root)
