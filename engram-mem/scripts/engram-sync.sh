#!/usr/bin/env bash
# engram-mem 同步助手。
#
# 为什么需要这个脚本:`engram sync` 把 chunk 写到「当前目录的 .engram/」
# (engram 源码里 syncDir 是相对路径 ".engram",无 flag 可改)。因此它必须在
# ~/.engram 里运行,否则 chunk 会落到错误目录、永远进不了 git 仓 → 记忆丢失
# (这是实测踩过的坑)。本脚本始终在 ~/.engram(可用 ENGRAM_HOME 覆盖)内操作,
# 且用子 shell 隔离,不影响调用者的当前目录。
#
# 用法:
#   engram-sync.sh push      # 导出全部记忆(--all)→ git add/commit/push   (默认)
#   engram-sync.sh pull      # git pull → engram sync --import
#   engram-sync.sh status    # engram 同步状态 + git 状态
set -euo pipefail

ENGRAM_DIR="${ENGRAM_HOME:-$HOME/.engram}"
cmd="${1:-push}"

if [ ! -d "$ENGRAM_DIR" ]; then
  echo "error: $ENGRAM_DIR 不存在(engram 是否已安装并初始化?)" >&2
  exit 1
fi

# 子 shell:cd 只在脚本内生效,不改调用者 cwd
cd "$ENGRAM_DIR"

case "$cmd" in
  push)
    engram sync --all
    git add .engram/
    # 没有新变更时 commit 会非零退出,用 || true 兜住,避免 set -e 中断
    git commit -m "sync engram memories $(date '+%Y-%m-%d %H:%M:%S')" || true
    git push
    ;;
  pull)
    git pull --ff-only
    engram sync --import
    ;;
  status)
    engram sync --status || true
    echo "--- git status ---"
    git status -s
    ;;
  *)
    echo "usage: engram-sync.sh [push|pull|status]" >&2
    exit 1
    ;;
esac
