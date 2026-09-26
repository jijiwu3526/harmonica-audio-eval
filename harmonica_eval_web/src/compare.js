// ★ 从 UiView 的 series 里【现算】出「参考 / 练习」配对，★ 与 Python 侧
//   `_comparison_pairs` / `_render_comparison` 的规则逐条一致。
// ★ 配对依据是 key 的 _reference / _practice 后缀，★ 不是算法名 ——★
//   新插件若产出同样后缀的曲线，★ 对比图自动出现。

const SUFFIXES = [
  [".per_note_f0_reference", ".per_note_f0_practice"],
  [".envelope_db_reference", ".envelope_db_practice"],
];

export function comparisonPairs(series) {
  const byKey = new Map(series.map((s) => [s.key, s]));
  const pairs = [];
  const seen = new Set();
  for (const item of series) {
    for (const [refSfx, praSfx] of SUFFIXES) {
      if (item.key.endsWith(praSfx)) {
        const base = item.key.slice(0, -praSfx.length);
        const other = byKey.get(base + refSfx);
        if (other && !seen.has(base)) {
          seen.add(base);
          // ★ 顺序与 Python 侧一致：★ (reference, practice)
          pairs.push([other, item]);
        }
        break;
      }
    }
  }
  return pairs;
}

const isFiniteVal = (v) => Number.isFinite(v);

// ★ 音高图要换算成音分：★ 直接画 Hz 会在低频区放大差异
//   （03_气息不匀 音高只差约 48 Hz，★ 而 200 Hz 基频上那是巨大垂直距离）。
// ★ 换算按【下标】配对而非 zip：★ 两侧长度不同时 zip 会截断成等长，
//   那会伪造出「两侧一样长」的假象（05_漏音断句 21/34）。
// ★ 短的一侧原长、长的补 NaN，★ NaN 段在折线里被断开。
export function buildComparison(reference, practice) {
  const unit = practice.unit || "（无单位）";
  const refVals = reference.values.filter(isFiniteVal);
  const praVals = practice.values.filter(isFiniteVal);
  const finite = [...refVals, ...praVals];

  const isF0 = unit === "hz" && refVals.length > 0 && praVals.length > 0;
  if (isF0) {
    const n = Math.max(refVals.length, praVals.length);
    const centsLine = [];
    const refLine = [];
    for (let i = 0; i < n; i++) {
      const a = i < refVals.length ? refVals[i] : null;
      const b = i < praVals.length ? praVals[i] : null;
      if (a === null || b === null || a <= 0 || b <= 0) {
        refLine.push(NaN);
        centsLine.push(NaN);
        continue;
      }
      refLine.push(0.0);
      centsLine.push(1200.0 * Math.log2(b / a));
    }
    const usable = centsLine.filter(isFiniteVal);
    return {
      xs: refLine.map((_, i) => i),
      refValues: refLine,
      pracValues: centsLine,
      unit: "音分（0=准，100=一个半音）",
      xLabel: "音序（第几个音，非秒）",
      usable,
    };
  }

  const xs = praVals.map((_, i) => i);
  return {
    xs,
    refValues: refVals,
    pracValues: praVals,
    unit,
    xLabel: "时间（秒）",
    usable: finite,
  };
}

export function baseKey(key) {
  for (const [refSfx] of SUFFIXES) {
    if (key.endsWith(refSfx)) return key.slice(0, -refSfx.length);
  }
  return key;
}

// ★ 单条图只画【没有配对同伴】的那些。
// ★ 成对曲线已在对比图里叠放过一次；★ 再逐条画一遍，
//   相同数据会落到不同纵坐标上，★ 自比时读成「有差异」——★ 那是假绿。
export function unpairedSeries(series, pairs) {
  const paired = new Set();
  for (const [ref, pra] of pairs) {
    paired.add(ref.key);
    paired.add(pra.key);
  }
  return series.filter((s) => !paired.has(s.key));
}
