// ★ 把一个插件的 series 组装成【表格】。★ 设计定稿：表格为核心，图表次要。
// ★ 原则：★ 只列能【一眼看出差异】的列；★ 参考侧恒为 0 的不列（timing）。
// ★ 全部列都从 UiView 现算，★ 不含任何写死的算法名或行数。

// ★ 每个插件的表格列在这里声明。★ 列名取自 series 的 key 后缀，
//   而插件 id 来自数据本身（key 的点号前缀）——★ 注入陌生插件自动获得表格。
const RULES = [
  {
    id: "pitch",
    axisLabel: "音序（第几个音）",
    columns: [
      { key: "reference", header: "参考 Hz", from: ".per_note_f0_reference" },
      { key: "practice", header: "练习 Hz", from: ".per_note_f0_practice" },
      { key: "delta", header: "偏差 cents", from: ".per_note_cents" },
    ],
  },
  {
    id: "timing",
    // ★ 只有练习侧：参考的起音时刻恒为 0，★ 列出那列是废话。
    // ★ 保留「起点秒」与「偏差秒」，★ 这样用户仍能看到音在第几秒起。
    axisLabel: "音序（第几个音）",
    columns: [
      { key: "onset", header: "起音 秒", from: ".per_note_onset_sec" },
    ],
    singleSided: true,
  },
  {
    id: "dynamics",
    axisLabel: "音序（第几个音）",
    columns: [
      { key: "reference", header: "参考 dB", from: ".envelope_db_reference" },
      { key: "practice", header: "练习 dB", from: ".envelope_db_practice" },
    ],
  },
];

// ★ 找一条 series：★ series 的 key 带算法前缀（如 pitch.per_note_cents），
//   而 RULES 里的 from 是【后缀】（如 .per_note_cents）。
//   ★ ★ ★ 2026-09-26 修：★ 原来直接 series.get(c.from) 查全表，
//   ★ ★ ★ 后缀永远 miss ——★ 三个插件的 tableFor 全部返回 null，
//   ★ ★ ★ 页面上插件卡片在、★ 但一个表格一张图都没有。
//   ★ 而【按后缀配对】正是本项目的可插拔约定（见 compare.js）：
//   ★ ★ 新插件若产出同后缀的曲线，★ 它的表格自动出现，★ 不必改这里。
function pick(series, algorithmId, suffix) {
  const direct = series.get(algorithmId + suffix);
  if (direct) return direct;
  // ★ 兜底：按后缀找唯一一条；★ 命中多条时【不猜】——★ 猜错会拼出假对比
  const hits = [...series.values()].filter(
    (s) => s.key.endsWith(suffix) && s.key.startsWith(algorithmId + ".")
  );
  return hits.length === 1 ? hits[0] : null;
}

function ruleFor(algorithmId) {
  return RULES.find((r) => r.id === algorithmId) || null;
}

// ★ series 的 t 是横轴（音序或秒），values 是纵轴。★ 两边按索引对齐。
function rowsFrom(series, rule, algorithmId) {
  const found = rule.columns
    .map((c) => ({ col: c, s: pick(series, algorithmId, c.from) }))
    .filter((x) => x.s);
  if (!found.length) return null;
  // ★ 行数取【各列的最小长度】：★ 参考 34 行、练习 21 行时，
  // ★ 只出 21 行；★ 把缺的行补空会让「未配上」看起来像「值为 0」。
  const n = Math.min(...found.map((x) => x.s.values.length));
  const rows = [];
  for (let i = 0; i < n; i += 1) {
    const row = { index: i + 1, axis: found[0].s.t[i] };
    for (const { col, s } of found) row[col.key] = s.values[i];
    rows.push(row);
  }
  return rows;
}

export function tableFor(algorithmId, series) {
  const byKey = new Map(series.map((s) => [s.key, s]));
  const rule = ruleFor(algorithmId);
  if (!rule) return null;
  const rows = rowsFrom(byKey, rule, algorithmId);
  if (!rows || !rows.length) return null;
  const firstCol = pick(byKey, algorithmId, rule.columns[0].from);
  const unit = (firstCol || {}).unit || "";
  return {
    id: rule.id,
    axisLabel: rule.axisLabel,
    unit,
    singleSided: Boolean(rule.singleSided),
    headers: rule.columns.map((c) => c.header),
    keys: rule.columns.map((c) => c.key),
    rows,
  };
}

// ★ 某插件有哪些可勾的曲线。★ 「不勾就不画」的数据源在这里。
export function chartsFor(algorithmId, series) {
  return series
    .filter((s) => s.key.startsWith(algorithmId + "."))
    .map((s) => ({
      key: s.key,
      label: s.label || s.key,
      unit: s.unit || "",
      axisLabel: s.timeline_basis === "WARPED" ? "时间（秒，归一化）" : "时间（秒）",
      values: s.values,
      t: s.t,
    }));
}

export const KNOWN_RULES = RULES;
