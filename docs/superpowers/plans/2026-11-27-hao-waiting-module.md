# hao 等待内核模块化拆分（waiting.py）

> 分工：quill 设计并验收，verse 实施。分支 `refactor/hao-waiting-module`（基于 main 73ae0ae，PR #11 合并后）。
> 要求（用户）：**性能、正确性都要保障。**

## 目标

把 `hao/scripts/hao`（2732 行）的**等待内核**拆出为 `hao/scripts/waiting.py`（883 行），主文件降到 **1786 行**。纯移动代码，不改逻辑。

## 方案：物理分文件 + 加载时 exec 合并命名空间（已验证）

主文件新增 `_include_waiting()`，在 `build_parser()` 之前把 `waiting.py` **exec 进自己的命名空间**。所有函数/常量仍在 `hao` 模块命名空间。

**为什么不用独立命名空间模块**：现有测试用 `SourceFileLoader` 加载单文件 `hao` 并 `mock.patch.object(hao, …)`，离线守卫替换 `hao.run_herdr`。若拆成独立模块，各函数的内部引用会指向**各自模块**的命名空间，这些 patch 全部失效（`hao._sentinel_check`、`hao.FAST_PATH_SECONDS`、guard 等），必须改动全部测试与 guard。exec include 保持单一命名空间——**372 个测试一个都不用改，guard 照常工作，运行时零额外间接层**。

## 已完成的可行性验证（quill，/tmp/poc）

- 372 个单元测试在正常环境与 herdr 不可达两种模式全过。
- 集成冒烟通过。
- 11/11 关键函数拆分前后输出完全一致（`build_prompt` 三档、`_token_matches`、`_normalize_for_match`、`_join_wrapped_sentinels`、`_tail_from_pane_text`、`SENTINEL_RE.pattern`、各扫描常量）。

## 拆分边界

- **移到 `waiting.py`**（约 883 行）：`_wait_sentinel`、`_wait_lifecycle`、`_wait_file`、`cmd_wait`、`cmd_done`、哨兵匹配（`_token_matches`、`_join_wrapped_sentinels`、`_sentinel_check`、`_sentinel_scan_tail`、`_confirm_sentinel`）、tail 提取（`_tail_from_pane_text`、`_normalize_for_match`、`_strip_tui_line`、`_prompt_end_line`、`_completion_tail`）、等待辅助（`_timeout_detail`、`_wait_round_rec`、`_agent_status_gate`、`_finish_sentinel`、`_finish_done` 等）及相关常量（`SENTINEL_RE`、`_PREFIX_LINE_RE`、`FAST_PATH_SECONDS`、`WORKING_SCAN_INTERVAL`、`SETTLED_SCAN_INTERVAL` 等）。
- **保留在 `hao`**：基础工具（`run_herdr`、`normalize_id`、`label_role`…）、name/clear/restore、suggest、`build_prompt`/`cmd_ask`、cancel/abort/stop、modes helpers、status/list/result/clean/doctor、CLI parser/main。

## verse 的实施步骤

1. `git checkout main && git pull --ff-only`（应在 `refactor/hao-waiting-module` 分支，先 `git checkout -b refactor/hao-waiting-module` 若尚未建）。
2. 运行 quill 已验证的拆分脚本：`python3 /tmp/poc_split.py /Users/spoon/Code/skill-vault`。它用 AST 精确按函数/常量名拆分，生成 `hao/scripts/waiting.py` 并重写 `hao/scripts/hao`（含 `_include_waiting`）。
3. 检查：`hao/scripts/hao` 1786 行、`hao/scripts/waiting.py` 883 行，两文件 `ast.parse` 通过。
4. 跑测试：正常环境 + herdr 不可达（PATH 上 `exit 1` 的 herdr 替身）+ `tests/hao/integration/test_integration.py`，全部通过。
5. `git add hao/scripts/hao hao/scripts/waiting.py`，提交 `refactor(hao): split the waiting kernel into waiting.py`，push。
6. 简报 ≤10 行（行数变化、两种模式测试数、集成结果），按协议 `hao done`。

## 验收（quill）

- 372 测试两种模式全过 + 集成冒烟。
- 拆分前后关键函数行为一致（已验证的方法复跑）。
- 真机功能回归：短任务、长任务（sleep 75）、两个 text-only 任务、tier 分档，全部正常。
- **性能**：对比拆分前后 `hao` 的加载/启动开销（exec include 应只多毫秒级），确认无退化；等待循环运行时代码路径不变。
- 通过后 quill 提 PR，**不合并**（用户合并）。

## 约束

- **纯移动代码，不改任何逻辑**；不改任何测试文件；不改 `ledger.py`/`names.py`。
- 自包含（skill 目录内），入口仍是 `python3 scripts/hao`，零外部依赖。
- 拆分脚本 `/tmp/poc_split.py` 是一次性工具，**不提交到仓库**（提交只含 `hao/scripts/hao` 与 `hao/scripts/waiting.py`）。
- 禁止 `pkill -f`/`killall`；测试不启动真实 agent；真机验收由 quill 做。
