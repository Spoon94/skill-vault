# hao：分档角色协作 skill 设计（v3）

> 状态：待用户审阅。前序设计见 `2026-11-22-herdr-agent-ops-design.md`（v33，已实现并合并）。
> v2：角色改为带档位的目录、命名与角色解耦。v3：角色目录从 11 个扩到 27 个（联网调研业界划分后精选）。

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

## 3. 角色：一份带档位的目录

### 3.1 标注方式——命名与角色解耦

pane label 的格式是 **`hao-<name>-<role>`**：

- `name` 是 agent 的代号，怎么选与角色无关（`hao suggest "<task>"` 保持现状，按任务关键词从词表里选）。
- `role` 是独立的字段，来自角色目录。`hao name <target> <name> --role <role>`；取值必须是目录里的角色，否则返回 2 并列出可用角色。
- 重启后 `hao restore` 连同角色一起恢复；不带 `--role` 重跑 `hao name` 时保留原有角色。
- `hao list` / `hao status` 显示角色与档位。
- 已有的非角色 scope（如 `hao-verse-ops`）仍能解析，视为「无角色」。
- label 里角色段的长度上限从 12 个字符放宽到 20 个（为了容纳 `frontend-developer` 这类角色名）。

### 3.2 角色目录（初始 27 个，可扩充）

角色名都不少于 7 个字符，因此不可能与 agent 名（4–6 个字符）混淆。

**决策 — 顶级 `top`**（规划、设计、终审）

| 角色 | 职责 |
|---|---|
| `strategist` | 方向判断、方案取舍 |
| `product-manager` | 需求与范围、优先级 |
| `planner` | 把需求展开为规格与验收标准 |
| `architect` | 整体架构与技术设计 |
| `arbiter` | 最终审核与裁决 |

**协调 — 中间 `mid`**（拆解、衔接）

| 角色 | 职责 |
|---|---|
| `project-manager` | 拆解任务、排期、派活 |
| `orchestrator` | 多 agent 之间的路由与编排 |
| `synthesizer` | 汇总多方结果，向上浓缩 |

**设计评审 — 中间 `mid`**（细化、初审）

| 角色 | 职责 |
|---|---|
| `designer` | 细化设计、接口与数据结构 |
| `ux-designer` | 交互与体验设计 |
| `reviewer` | 初审、代码评审 |
| `evaluator` | 评估产出质量、给出评分与依据 |
| `analyst` | 调研分析、定位问题 |
| `auditor` | 安全与合规审计 |

**实施 — 垫底 `low`**（实现、优化）

| 角色 | 职责 |
|---|---|
| `developer` | 实现功能 |
| `frontend-developer` | 前端实现 |
| `backend-developer` | 后端实现 |
| `debugger` | 定位并修复缺陷 |
| `refactorer` | 重构与优化 |
| `test-engineer` | 编写测试、验证 |

**支撑 — 垫底 `low`**（信息与基础设施）

| 角色 | 职责 |
|---|---|
| `explorer` | 检索代码库 |
| `researcher` | 检索资料、调研 |
| `doc-writer` | 文档、说明、示例 |
| `devops-engineer` | 部署、运维、基础设施 |
| `data-engineer` | 数据管道、存储 |
| `prompt-engineer` | 提示词设计与优化 |
| `memory-curator` | 知识与记忆的整理 |

目录是数据，放在 `references/roles.md`（一张表：角色、档位、职能组、职责）。新增角色只需在表里加一行；档位只有 `top` / `mid` / `low` 三种。

### 3.3 调研依据

角色是以下来源的归并与精选（同名或近义的角色合并为一个）：

- MetaGPT 的「软件公司」五角色：产品经理、架构师、项目经理、工程师、QA 工程师（arxiv.org/html/2308.00352v6）
- BMAD Method：分析师、产品经理、架构师、UX 设计师、Scrum Master、开发、QA、编排者（docs.bmad-method.org/start/how-bmad-works）
- Anthropic 的 Planner / Generator / Evaluator 三角色（shiplight.ai/blog/planner-generator-evaluator-multi-agent-qa）
- 编排模式：orchestrator / worker，researcher、coder、reviewer、synthesizer、memory curator（explainx.ai/blog/multi-agent-orchestration-patterns-guide-2026）
- Claude Code 与 Codex 的内置子 agent：Explore、Plan、General-purpose；worker、explorer、reviewer、docs researcher
- awesome-claude-code-subagents：10 类共 173 个专家角色（github.com/VoltAgent/awesome-claude-code-subagents）

未收录的是按语言、框架、云平台细分的专家（如 `typescript-pro`、`terraform-engineer`）和业务类角色（如 `legal-advisor`、`content-marketer`）——它们是领域细分而非协作职能，需要时在目录里自行添加。

## 4. 协作：按档位选择简报

**角色说明「做什么」，档位决定「怎么派活」。** `hao ask` 读取目标 label 里的角色，查出档位，据此选择简报的繁简与输出上限；`--max-lines N` 可覆盖输出上限。

| 目标档位 | 简报 | 默认输出上限 |
|---|---|---|
| `top` | 精简：任务正文 + 一句完成规则 | 结论先行，不超过 15 行 |
| `mid` | 标准 | 不超过 40 行 |
| `low` 或无角色 | 完整协议（现状） | 不限 |

- 完成信号协议不变（先打印哨兵，再视情况调用 `hao done`；审批型对方用 `--text-only`），只是措辞随简报繁简而不同。精简模板同样遵守「哨兵在前」的顺序。
- **实施更正（2026-11-26，验收时补记）**：`mid` 与 `low`（及无角色目标）共用同一份完整简报，区别只在默认输出上限——`mid` 多一行「输出要求：…不超过 40 行」。只有 `top` 使用精简简报。中间档不单独精简：完整简报里的协议说明正是中间模型可靠完成上报所依赖的，省下的一百余 token 不值得冒不合规的风险。上表的「标准」按此理解。
- 其余命令（`wait` / `done` / `cancel` / `abort` / `stop` / `clean` 等）不变。

## 5. 工作流（写进文档，不新增流水线命令）

`SKILL.md` 以分档流程为主工作流，细节放在 `references/workflow.md`：

```
1 规划   strategist / product-manager / planner / architect   产出方案与验收标准
2 拆解   project-manager                                   把方案拆成任务清单
3 实施   developer 等                                      可并行多个；project-manager 派活并等待
4 初审   reviewer / evaluator / auditor                    不通过则交给 debugger 修复后回到 4
5 终审   arbiter                                           只看结论与必须修改项
```

每一步写明：谁来派、用什么命令、产物怎么交给下一步（`summary` 或报告路径）、失败怎么处理（对方被审批卡住 → 交用户；超时 → `cancel` 或 `abort`）。
编排动作由调用方（通常是 project-manager）完成；顶级角色只在第 1 步和第 5 步出现。

## 6. 不做的事

- 不做「按任务 id 自动拼接上下文」、不做流水线命令、不做摘要长度分档——用户明确表示「主要就是角色、协作、工作流，没那么复杂」。
- 不按角色约束取名（用户要求命名与角色解耦）。
- 不记录 agent 使用的模型。

## 7. 验收标准

1. 改名后仓库内没有 `herdr-agent-ops` 的活引用（历史文档除外）；根 README 索引与文档守卫测试全部通过。
2. `hao name w2:p9 moth --role frontend-developer` 得到 label `hao-moth-frontend-developer`；`--role foo` 返回 2 并列出可用角色；`hao restore` 之后角色仍在；不带 `--role` 重跑保留角色。
3. 27 个角色每个都能通过 `--role` 使用，并按其档位选择简报；在 `roles.md` 加一行自定义角色后立即可用。
4. 同一句任务分别派给 `top` / `mid` / `low` 三种档位的角色，prompt 的长度与输出上限符合第 4 节的表；`--max-lines` 能覆盖默认值。
5. `hao list` / `hao status` 正确显示角色、职能组与档位。
6. 真机：一次性实例分别以三种档位的角色命名后派活，都能完成；派给 `top` 的 prompt 明显短于派给 `low` 的。
7. 单元测试在三种运行方式下全部通过（正常、herdr 不可达、集成冒烟）。
