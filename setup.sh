#!/bin/bash
set -euo pipefail

readonly MIN_PY_MAJOR=3
readonly MIN_PY_MINOR=11
readonly ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
readonly REQUIREMENTS="${ROOT_DIR}/requirements.txt"
readonly PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  cat <<'EOF'
用法: ./setup.sh [--dry-run]

  --dry-run  只检查并显示将要执行的命令，不创建环境、不安装依赖。
  环境变量:
    PYTHON_BIN  指定 Python 解释器（默认: python3）
    VENV_DIR    指定虚拟环境目录（默认: <仓库>/.venv）
EOF
}

die() {
  printf '错误: %s\n' "$*" >&2
  exit 1
}

run() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  if [[ "${DRY_RUN:-0}" != 1 ]]; then
    "$@"
  fi
}

DRY_RUN=0
if [[ $# -gt 0 ]]; then
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; die "未知参数: $1" ;;
  esac
fi
[[ $# -le 1 ]] || die "参数过多；使用 --help 查看用法"

[[ "$(uname -s)" == "Darwin" ]] || die "仅支持 macOS"
[[ "$(uname -m)" == "arm64" ]] || die "仅支持 Apple Silicon arm64"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "找不到 Python: $PYTHON_BIN"
[[ -f "$REQUIREMENTS" ]] || die "缺少依赖清单: $REQUIREMENTS"

if ! "$PYTHON_BIN" -c '
import sys
if sys.version_info < (3, 11):
    raise SystemExit(1)
' >/dev/null 2>&1; then
  die "需要 Python >= ${MIN_PY_MAJOR}.${MIN_PY_MINOR}；实际为 $("$PYTHON_BIN" --version 2>&1)"
fi

printf '平台: %s\n' "$(uname -m) macOS"
printf 'Python: %s\n' "$("$PYTHON_BIN" --version 2>&1)"
printf '虚拟环境: %s\n' "$VENV_DIR"
printf '依赖清单: %s\n' "$REQUIREMENTS"

if [[ -d "$VENV_DIR" && ! -x "${VENV_DIR}/bin/python" ]]; then
  die "目录已存在但不是有效虚拟环境: $VENV_DIR"
fi

if [[ "${DRY_RUN:-0}" == 1 ]]; then
  run "$PYTHON_BIN" -m venv "$VENV_DIR"
  run "$VENV_DIR/bin/python" -m pip install --upgrade pip
  run "$VENV_DIR/bin/python" -m pip install -r "$REQUIREMENTS"
  printf 'dry-run 完成；未修改文件系统。\n'
  exit 0
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  run "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  printf '复用虚拟环境: %s\n' "$VENV_DIR"
fi

run "${VENV_DIR}/bin/python" -m pip install --upgrade pip
run "${VENV_DIR}/bin/python" -m pip install -r "$REQUIREMENTS"
printf '环境准备完成。\n'
