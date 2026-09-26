// ★ 与 Python 侧对话的三个动作：★ 读状态、发命令、读数据集。
// ★ 全部走 fetch；★ 不解析 HTML ——★ 状态一律来自 GET /view 的 JSON。

const JSON_CT = "application/json";

async function postCommand(kind, path, only) {
  const body = { kind };
  if (path) body.path = path;
  // ★ only 只对 RUN_ALGORITHMS 有意义：★ 契约里它的 payload 键是算法 id 列表
  if (only) body.only = only;
  const res = await fetch("/command", {
    method: "POST",
    headers: { "Content-Type": JSON_CT },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  return { ok: res.ok, status: res.status, text };
}

// ★ 五条命令必须【按序】跑：★ RESET 不到 CREATED，SET_* 就仍非法。
// ★ 而 build_surface 要十几秒，★ 期间状态是 BUILDING，
// ★ 所以每条回来后都要重新读状态，★ 轮询到「有指标」才停。
// ★ 那三条旧缺陷（竞态 / 按钮 / 状态不更新）都由这里的等待逻辑兜住。
export async function runSelection(refPath, praPath, onStatus, only) {
  // ★ only 为空数组时内核会按契约抛错（N=0），★ 所以前端也要拦住并说明
  if (!only || !only.length) {
    onStatus?.("请至少勾选一个插件");
    return { ok: false, failedAt: "none-selected" };
  }
  const steps = [
    { kind: "RESET" },
    { kind: "SET_REFERENCE", path: refPath },
    { kind: "SET_PRACTICE", path: praPath },
    { kind: "BUILD_SURFACE" },
  ];
  for (const step of steps) {
    onStatus?.(`正在执行 ${step.kind}…`);
    const r = await postCommand(step.kind, step.path);
    if (!r.ok) {
      onStatus?.(`${step.kind} 被拒绝：${r.text}`);
      return { ok: false, failedAt: step.kind, text: r.text };
    }
  }
  // ★ 懒加载：★ 把「勾了哪些插件」交给内核，★ 而不是只在前端藏起来。
  // ★ 不勾的插件【根本不跑】，★ 所以 /view 里不会有它的 scalars/series。
  onStatus?.(`正在运行 ${only.length} 个插件…`);
  const run = await postCommand("RUN_ALGORITHMS", null, only);
  if (!run.ok) {
    onStatus?.(`RUN_ALGORITHMS 被拒绝：${run.text}`);
    return { ok: false, failedAt: "RUN_ALGORITHMS", text: run.text };
  }
  // ★ 跑完了还不算完：★ RUN_ALGORITHMS 返回时页面可能已被刷成
  //   BUILDING 那一帧（服务端有 0.5 秒轮询线程）。★ 所以等它真的稳定。
  const settled = await waitForMetrics();
  onStatus?.(settled ? "对比完成" : "已提交，但尚未看到指标");
  return { ok: settled };
}

// ★ 轮询直到「状态是 DATA_READY 且真有指标」，★ 最多 30 秒兜底。
export async function waitForMetrics(timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const view = await fetchView();
    // ★ 判据不能用 scalars.length > 0：★ 勾选的插件可能只产出曲线
    if (view && view.state === "DATA_READY" && view.progress >= 1) {
      return true;
    }
    if (Date.now() > deadline) return false;
    await new Promise((r) => setTimeout(r, 500));
  }
}

// ★ __BOOT__ 只对【首屏】有效。
// ★ 它是服务端建会话那一帧的快照；★ 若之后仍优先读它，★ 页面会永远停在
// ★ 第一次的结果 ——★ 表现为「选曲后数字不变」，★ 而那是假的。
let bootFresh = true;
export function markBootStale() {
  bootFresh = false;
}

export async function fetchView() {
  // ★ 首屏用内联快照，★ 让首屏不依赖第二个请求；
  // ★ 一旦跑过分析，★ bootFresh 变 false，★ 一律走 /view。
  if (bootFresh) {
    const boot = readBoot();
    if (boot) return boot;
  }
  try {
    const res = await fetch("/view", { headers: { Accept: JSON_CT } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    // ★ 服务端不可达时返回 null，★ 而不是抛 ——★ 那正是「Failed to fetch」
    return null;
  }
}

// ★ 读服务端内联的首屏数据。★ 放在 <script type="application/json"> 里
//   而不是可执行 JS 里，★ 所以 JSON.parse 前不需要任何求值 ——★ 更安全。
export function readBoot() {
  try {
    const el = document.getElementById("boot-data");
    if (!el || !el.textContent) return null;
    return JSON.parse(el.textContent);
  } catch {
    return null;
  }
}

export async function fetchDataset() {
  try {
    const res = await fetch("/dataset", { headers: { Accept: JSON_CT } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
