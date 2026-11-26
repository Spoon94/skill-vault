# hao：分档角色协作 skill 设计（v1）

> 状态：待用户审阅。前序设计见 `2026-11-22-herdr-agent-ops-design.md`（v33，已实现并合并）。

## 1. 目标

把 `herdr-agent-ops` 改名为 **`hao`**，定位从「herdr agent 运维」调整为「多 agent 分档协作」——herdr 只是底层通道。围绕三件事：**角色、协作、工作流**。

背景（用户诉求）：三档模型协作——

| 档位 | 职责 | token |
|---|---|---|
| 顶级 | 整体规划、设计、最终审核 | 最有限，只花在最难的部分 |
| 中间 | 拆解规划、细化设计、初步审核 | 较充裕 |
| 垫底 | 实施、优化 | 几乎无限 |

技能的职责是让「贵模型只在最难处花钱」：贵模型的输入要短、输出要被约束得短；机械性的衔接由便宜的模型或调用方完成。

## 2. 改名（硬改，不保留兼容层）

- 目录 `herdr-agent-ops/` → `hao/`；`tests/herdr-agent-ops/` → `tests/hao/`
- `SKILL.md` 的 `name: hao`；`description` 以「分档多 agent 协作（规划 / 拆解 / 实施 / 审核）」为主，herdr 作为前提条件出现
- 根 `README.md` 索引、脚本里内嵌的路径与说明文字（`hao_command()`、帮助文案）、`references/*.md`
- CLI 名不变（仍是 `hao`）；历史设计文档（`docs/superpowers/` 下已合并的 5 份）保持原样
- 仓库之外：已安装的副本由用户同步（`hao` 进技能库，移除旧名 `herdr-agent-ops`）

## 3. 角色

三个内置角色。角色名都不少于 7 个字符，因此不可能与 agent 名（4–6 个字符）混淆。

| 角色 | 档位 | 职责 | 取名的推荐组（词表里的组） |
|---|---|---|---|
| `architect` | 顶级 | 整体规划、设计、终审 | 规划编排、架构接口、战略分析、验证审阅 |
| `captain` | 中间 | 拆解规划、细化设计、初审 | 项目管理、验证审阅、测试实验、调试修复 |
| `builder` | 垫底 | 实施、优化 | 实现构建、调试修复、测试实验；其余技术组按任务关键词参与 |

- **标注在 pane label**：`hao-<name>-<role>`，沿用现有 label 格式。`hao name` 的 `--scope` 改为 `--role`，取值限定为三个角色之一。重启后 `hao restore` 连同角色一起恢复。
- **agent 名体现角色**：`hao suggest "<task>" --role <role>` 只在角色的推荐组里选名；任务关键词命中的组优先。
- `hao list` / `hao status` 显示角色。
- 已有的非角色 scope（如 `hao-verse-ops`）仍能解析，视为「无角色」。
- 不带 `--role` 重跑 `hao name` 时保留原有角色（与现有「沿用 scope」的行为一致）。

## 4. 协作：按角色选择简报

`hao ask` 读取目标 label 里的角色，自动选择简报的繁简与输出上限；`--max-lines N` 可覆盖输出上限。

| 目标角色 | 简报 | 默认输出上限 |
|---|---|---|
| `architect` | 精简：任务正文 + 一句完成规则 | 结论先行，不超过 15 行 |
| `captain` | 标准 | 不超过 40 行 |
| `builder` 或无角色 | 完整协议（现状） | 不限 |

- 完成信号协议不变（先打印哨兵，再视情况调用 `hao done`；审批型对方用 `--text-only`），只是措辞随简报繁简而不同。精简模板同样遵守「哨兵在前」的顺序。
- 其余命令（`wait` / `done` / `cancel` / `abort` / `stop` / `clean` 等）不变。

## 5. 工作流（写进文档，不新增流水线命令）

`SKILL.md` 以三档流程为主工作流，细节放在 `references/workflow.md`：

```
1 规划   architect   产出方案与验收标准
2 拆解   captain     把方案拆成任务清单
3 实施   builder     可并行多个；captain 派活并等待
4 初审   captain     不通过则回到 3
5 终审   architect   只看结论与必须修改项
```

每一步写明：谁来派、用什么命令、产物怎么交给下一步（`summary` 或报告路径）、失败怎么处理（对方被审批卡住 → 交用户；超时 → `cancel` 或 `abort`）。
编排动作由调用方（通常是 captain）完成；architect 只在第 1 步和第 5 步出现。

## 6. 不做的事

- 不做「按任务 id 自动拼接上下文」、不做流水线命令、不做摘要长度分档——用户明确表示「主要就是角色、协作、工作流，没那么复杂」。
- 不记录 agent 使用的模型。

## 7. 验收标准

1. 改名后仓库内没有 `herdr-agent-ops` 的活引用（历史文档除外）；根 README 索引与文档守卫测试全部通过。
2. `hao name w2:p9 moth --role builder` 得到 label `hao-moth-builder`；`--role foo` 返回 2；`hao restore` 之后角色仍在。
3. `hao suggest "重构模块" --role architect` 的候选全部来自 architect 的推荐组；`--role builder` 同理。
4. 同一句任务分别派给三种角色，prompt 的长度与输出上限符合第 4 节的表；`--max-lines` 能覆盖默认值。
5. 真机：一次性实例分别以三种角色命名后派活，都能完成；派给 architect 的 prompt 明显短于派给 builder 的。
6. 单元测试在三种运行方式下全部通过（正常、herdr 不可达、集成冒烟）。
