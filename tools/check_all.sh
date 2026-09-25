#!/usr/bin/env bash
# tools/check_all.sh — harmonica-eval 的唯一检查/工具执行入口。
#
# 分类口径（逐项依据脚本实际职责维护；新增 .py 未登记时入口直接拒绝运行）：
#   check       阻塞检查：非 0、崩溃或超时均阻塞。
#   allowed-red 允许红：仅退出码 1 表示已登记的真实差异；2、超时、崩溃仍阻塞。
#   tool        工具/分析器：必须运行；非 0、崩溃或超时按失败处理。
#   deprecated  已弃用：不运行，但必须在本清单中写明原因（当前无弃用脚本）。
#
# ★ check 与 tool 的区别只在【汇报归类】，不在【是否阻塞】：
#   两类失败同等阻塞，均使本入口非 0 退出。汇报里不得出现「阻塞检查 0 个」这种
#   会被读成「没阻塞所以没事」的表述。
#
# 只读纪律：build_virtual_graph 使用 --check，不写生成物；其余命令保持各脚本
# 原有行为。check_all.sh 本身不修改任何现有 Python 脚本。

set -u

TOOLS_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
REPO_ROOT=$(CDPATH= cd -- "$TOOLS_DIR/.." && pwd -P)
TIMEOUT_SECONDS=600

# 字段：分类|相对路径|参数|分类理由
# 注意：此表是覆盖闸门，不是给人看的可选清单。若 tools/ 出现未登记的 .py，
# 入口会在执行任何脚本前退出，防止新增脚本再次被静默漏跑。
RUN_ENTRIES=(
  "check|tools/check_bi_scripts.py||抽取并编译 BI §8 脚本，核对静态调用参数数；非 0 表示验收源码或骨架契约有问题。"
  "check|tools/check_counts.py||把 BI 的可机械定位数量声明与当前 AST/枚举/常量事实对账；非 0 表示文档或结构漂移。"
  "check|tools/check_deliverable_hygiene.py||扫描交付物中的智能体控制标记、零宽字符等污染；非 0 表示交付物不洁净。"
  "check|tools/check_injection_wiring.py||跨模块接线检查：核对已注入模块（bootstrap/registry）产出的 PluginSpec 与算法源码 MUST 条款、entry 归属、顺序单一来源是否一致；非 0 表示注入件之间接错。"
  "check|tools/check_plugin_contract.py||执行 C3 插件架构与契约的机械检查；非 0 表示存在架构违规。"
  "check|tools/check_reachability.py||检查 BI 要求产出的量是否真能由对应函数参数/投影/合法来源取得；非 0 表示不可达。"
  "check|tools/check_registration.py||登记守卫：未跟踪的新 .py 必须在 tools/authorized_impl.py 有精确路径条目（哪次授权+哪份 BI）；非 0 表示授权流程漏了一步。精确匹配不用前缀，否则 core/ingest_extra.py 会被 core/ingest.py 连带放过。git 不可用时跳过并打印原因，不静默失效。与 verify_shell 分工：它管「已登记却出现实现」，本守卫管「未登记却已存在」。"
  "check|tools/check_ui_contract_fit.py||契约可绘制性检查：核对 UiView/UiScalar/UiSeries/PortDescriptor 每个字段是否都有来源与去处、单位与状态是否全覆盖、端口投影是否只含裁定字段；非 0 表示契约不足以驱动 C4 视图。"
  "check|tools/check_xref.py||核验 FILE-NNN 章节交叉引用和重号节；非 0 表示引用指向不存在或歧义的章节。"
  "check|tools/verify_shell.py||执行空壳完整性、依赖方向、签名、文档/代码一致性等复合检查；非 0 表示阻塞违规。"
  "check|tools/verify_stubs_raise.py||实际调用仍为空壳的符号并验证其按 FILE-ID 抛 NotImplementedError；非 0 表示空壳失效。"
  "check|tools/attacks/verify_attack_surfaces.py||用最小实验证实四类错误实现会静默产出假结果；非 0 表示反方论据未被复现。"
  "allowed-red|tools/check_scratch_freshness.py||允许红的理由：_scratch 是故意保留的陈旧参考实现副本；主包与它存在契约漂移是本仓已知真实信号，不是入口故障。仅退出码 1 可放行；退出码 2、检查器崩溃或超时仍按失败处理。"
  "tool|tools/build_virtual_graph.py|--check|生成/分析器：用当前代码推导 Virtual System Graph 并校验；使用 --check 避免写盘。任何失败或崩溃都必须阻塞，不能静默漏跑。"
  "tool|tools/check_bi_scripts_exec.py||诊断分析器：抽取 BI §8 Python 并对参考实现逐段执行，输出 PASS/FAIL 状态；其退出码与诊断报告按脚本原契约处理，非 0 仍按工具失败阻塞。"
  "tool|tools/derive_clusters.py||分析器：按结构信号推导组件聚类并与铭牌对照；任何失败、异常或超时均阻塞。"
  "tool|tools/derive_semantic.py||分析器：按文件职责声明推导语义亲和度并输出机器/人类可读结果；任何失败、异常或超时均阻塞。"
  "tool|tools/probe_audio_chain.py||只读链路探针：逐环确证「双音频 → metrics.json」的可达性并定位第一个物理断点；不产出指标、绝不伪造结果，只读不写盘。其退出码与诊断报告按脚本原契约处理，非 0 仍按工具失败阻塞。"
  "lib|tools/authorized_impl.py||已授权注入文件的唯一真相源（被 verify_shell / verify_stubs_raise / check_plugin_contract import 派生，自身无独立判定职责，故分类为 lib 不单列执行）。"
  "tool|tools/golden_baseline.py||回归参照工具：把已注入冻结文件在真实音频上的输出固化为可回归基线；非 0 表示与基线不符。"
)

if ! command -v timeout >/dev/null 2>&1; then
  printf '❌ ENTRYPOINT CONFIG ERROR: 找不到 timeout 命令；无法为每个脚本提供超时保护。\n' >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf '❌ ENTRYPOINT CONFIG ERROR: 找不到 python3 命令。\n' >&2
  exit 2
fi

cd "$REPO_ROOT" || {
  printf '❌ ENTRYPOINT CONFIG ERROR: 无法进入仓库根目录 %s\n' "$REPO_ROOT" >&2
  exit 2
}

entry_field_script() {
  local entry=$1 rest
  rest=${entry#*|}
  printf '%s' "${rest%%|*}"
}

manifest_file=$(mktemp "${TMPDIR:-/tmp}/harmonica-check-all-manifest.XXXXXX") || exit 2
discovered_file=$(mktemp "${TMPDIR:-/tmp}/harmonica-check-all-discovered.XXXXXX") || exit 2
trap 'rm -f "$manifest_file" "$discovered_file"' EXIT HUP INT TERM

for entry in "${RUN_ENTRIES[@]}"; do
  entry_field_script "$entry"
  printf '\n'
done | LC_ALL=C sort -u >"$manifest_file"

find "$TOOLS_DIR" -type f -name '*.py' \
  ! -path '*/__pycache__/*' -print \
  | while IFS= read -r path; do
      case "$path" in
        "$REPO_ROOT"/*) printf '%s\n' "${path#"$REPO_ROOT"/}" ;;
        *) printf 'ERROR:%s\n' "$path" ;;
      esac
    done \
  | LC_ALL=C sort -u >"$discovered_file"

unregistered=$(LC_ALL=C comm -23 "$discovered_file" "$manifest_file")
if [ -n "$unregistered" ]; then
  printf '❌ ENTRYPOINT CONFIG ERROR: 以下 tools/*.py 未被 check_all.sh 分类登记：\n' >&2
  printf '  - %s\n' $unregistered >&2
  printf '请先实测并明确归类；入口拒绝静默漏跑。\n' >&2
  exit 2
fi

missing=''
while IFS= read -r script; do
  [ -f "$REPO_ROOT/$script" ] || missing="$missing$script"$'\n'
done <"$manifest_file"
if [ -n "$missing" ]; then
  printf '❌ ENTRYPOINT CONFIG ERROR: 清单中的脚本不存在：\n' >&2
  printf '  - %s' $missing >&2
  exit 2
fi

printf '============================================================\n'
printf 'harmonica-eval · 统一检查入口\n'
printf '============================================================\n'
printf '仓库根：%s\n' "$REPO_ROOT"
printf '超时：每个脚本 %s 秒（timeout --kill-after=5s）\n' "$TIMEOUT_SECONDS"
printf '已登记：%s 个 Python 脚本；未发现未登记脚本。\n' "$(wc -l <"$manifest_file" | tr -d ' ')"
printf '\n执行清单（分类是机器判定的一部分）：\n'
for entry in "${RUN_ENTRIES[@]}"; do
  IFS='|' read -r kind script args reason <<EOF
$entry
EOF
  printf '  %-12s %-45s %s\n' "$kind" "$script" "${args:-(默认参数)}"
done

ran=0
passed=0
allowed_red=0
failed=0
check_failures=0
tool_failures=0
FAILURES=()

record_failure() {
  local script=$1 kind=$2 rc=$3
  failed=$((failed + 1))
  FAILURES+=("${script} (分类=${kind}, 退出码=${rc})")
  if [ "$kind" = "tool" ]; then
    tool_failures=$((tool_failures + 1))
  else
    check_failures=$((check_failures + 1))
  fi
}

run_entry() {
  local entry=$1 kind script args reason rc status
  entry=$1
  kind=${entry%%|*}
  local rest=${entry#*|}
  script=${rest%%|*}
  rest=${rest#*|}
  args=${rest%%|*}
  reason=${rest#*|}

  if [ "$kind" = "lib" ]; then
    ran=$((ran + 1))
    printf '\n------------------------------------------------------------\n'
    printf '[%02d] %s\n' "$ran" "$script"
    printf '分类：%s\n' "$kind"
    if [ -n "$reason" ]; then
      printf '说明：%s\n' "$reason"
    fi
    printf '（lib 分类：被其它检查器 import，此处不执行）\n'
    return 0
  fi

  ran=$((ran + 1))
  printf '\n------------------------------------------------------------\n'
  printf '[%02d] %s\n' "$ran" "$script"
  printf '分类：%s\n' "$kind"
  if [ -n "$reason" ]; then
    printf '说明：%s\n' "$reason"
  fi

  timeout --kill-after=5s "${TIMEOUT_SECONDS}s" \
    python3 "$script" $args
  rc=$?

  if [ "$rc" -eq 0 ]; then
    passed=$((passed + 1))
    if [ "$kind" = "tool" ]; then
      status='✅ PASS [TOOL-OK] 工具执行完成'
    elif [ "$kind" = "allowed-red" ]; then
      status='✅ PASS [NO-DRIFT] 允许红项本次未检测到差异（退出码 0）'
    else
      status='✅ PASS [CHECK-OK] 检查通过（与 tool 类同等阻塞口径）'
    fi
    printf '%s\n' "$status"
  elif [ "$kind" = "allowed-red" ] && [ "$rc" -eq 1 ]; then
    allowed_red=$((allowed_red + 1))
    status='⚠️  ALLOWED-RED [EXPECTED-DRIFT] 退出码 1：这是已登记的真实差异，按设计允许红，不阻塞'
    printf '%s\n' "$status"
  else
    if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
      status="❌ FAIL [TIMEOUT] 超过 ${TIMEOUT_SECONDS} 秒或被超时保护终止（退出码 ${rc}）"
    elif [ "$kind" = "tool" ]; then
      status="❌ FAIL [TOOL-FAIL] 工具未正常完成或报告阻塞性失败（退出码 ${rc}）；不得静默跳过"
    else
      status="❌ FAIL [CHECK-FAIL] 阻塞检查未通过（退出码 ${rc}）"
    fi
    printf '%s\n' "$status"
    record_failure "$script" "$kind" "$rc"
  fi
}

for entry in "${RUN_ENTRIES[@]}"; do
  run_entry "$entry"
done

printf '\n============================================================\n'
printf '汇总\n'
printf '============================================================\n'
printf '运行：%s 个\n' "$ran"
printf '通过：%s 个\n' "$passed"
printf '允许红：%s 个（计入运行；不计入通过；按设计不阻塞）\n' "$allowed_red"
printf '失败：%s 个 —— 其中 check 类 %s 个、tool 类 %s 个\n' \
  "$failed" "$check_failures" "$tool_failures"
printf '\n★ 分类只说明「失败被归到哪一栏」，不说明「是否阻塞」。\n'
printf '★ check 类与 tool 类的失败【同等阻塞】：任何一类失败都会使本入口非 0 退出。\n'
printf '★ 唯一不阻塞的是 allowed-red，且它只放行【已登记且退出码恰为 1】的真实差异。\n'

if [ "$failed" -gt 0 ]; then
  printf '\n⚠️  以上 %s 个失败项【全部阻塞】，入口将以非 0 退出。\n' "$failed"
  printf '⚠️  工具返回非 0 不一定都是进程崩溃，也可能是工具按契约报告阻塞性数据缺失；无论哪种都计入失败。\n'
  for failure in "${FAILURES[@]}"; do
    printf '  - %s\n' "$failure"
  done
  printf '\n❌ 整体结果：失败（%s 个失败项中有 %s 个 check 类、%s 个 tool 类；全部阻塞）\n' \
    "$failed" "$check_failures" "$tool_failures"
  exit 1
fi

printf '\n✅ 整体结果：通过（%s 个 check 类与 tool 类全部通过；%s 个 allowed-red 本次未检测到差异）\n' \
  "$((ran - allowed_red))" "$allowed_red"
exit 0
