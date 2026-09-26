// ★ 甲 + 丙：插件卡片界面。
//   甲 —— 选曲自动出图，★ 图能看出哪里不一样
//   丙 —— 界面主角是「哪个插件算的、算出了什么」
// ★ 设计定稿（负责人 2026-09-25）：
//   · 多选插件；不选 → 不显示卡片，★ 且【不跑那个插件】（真懒加载）
//   · 每个插件一张卡片，★ 卡片里【表格是核心】，图表次要且可勾选
//   · 与插件参数无关的（端口 / shape / 契约）→ 折叠
//   · 默认只勾一个插件
// ★ 懒加载的判据是「/view 里没有」，★ 不是「界面没显示」。

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { fetchView, fetchDataset, runSelection, readBoot, markBootStale } from "./api.js";
import { ComparisonChart } from "./ComparisonChart.jsx";
import { tableFor, chartsFor, KNOWN_RULES } from "./tables.js";

const PLUGIN_ORDER = ["pitch", "timing", "dynamics"];
const PLUGIN_LABELS = { pitch: "音准", timing: "节奏", dynamics: "能量" };

// ★ 折叠区里的元信息：★ 与插件无关，★ 但每次运行都该在场。
// ★ 「音数 / 未配对」三个插件各报一遍，★ 那是同一事实，★ 只列一次。
function metaOf(view) {
  const pick = (suffix) => {
    const hit = (view.scalars || []).find((s) => s.key.endsWith(suffix));
    return hit ? Math.round(hit.value) : null;
  };
  const sr = (view.scalars || []).find((s) => s.key === "pitch.sampling_rate");
  return {
    参与统计的音数: pick("n_notes_used"),
    未能配对的音数: pick("n_unpaired_notes"),
    采样率: sr ? Math.round(sr.value) : null,
  };
}

function PluginCard({ id, table, charts, chosenCharts, onToggleChart }) {
  return (
    <section className="card">
      <h2>
        {PLUGIN_LABELS[id] || id} <span className="tag">{id}</span>
      </h2>

      {table ? (
        <>
          <table className="pernote">
            <caption>{table.axisLabel}（逐音，不是汇总值）</caption>
            <thead>
              <tr>
                <th>#</th>
                {table.headers.map((h, i) => (
                  <th key={table.keys[i]}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => (
                <tr key={row.index}>
                  <td className="idx">{row.index}</td>
                  {table.keys.map((k) => (
                    <td key={k}>
                      {row[k] === undefined || row[k] === null
                        ? "—"
                        : Number(row[k]).toFixed(2)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {table.singleSided ? (
            <p className="note">
              只有练习侧的起音时刻：参考的起点恒为 0，★ 列出那一列没有信息。
            </p>
          ) : null}
        </>
      ) : (
        <p className="empty">该插件本次未产出可成表的逐音曲线。</p>
      )}

      <div className="charts">
        <h3>对比曲线（勾选才画）</h3>
        {charts.length === 0 ? <p className="empty">本次无曲线。</p> : null}
        {charts.map((c) => (
          <label key={c.key} className="chart-toggle">
            <input
              type="checkbox"
              checked={chosenCharts.includes(c.key)}
              onChange={() => onToggleChart(c.key)}
            />
            {c.label}（{c.unit}）
          </label>
        ))}
        {charts
          .filter((c) => chosenCharts.includes(c.key))
          .map((c) => (
            <ComparisonChart
              key={c.key}
              title={c.label}
              unit={c.unit}
              t={c.t}
              values={c.values}
            />
          ))}
      </div>
    </section>
  );
}

export default function App() {
  const [view, setView] = useState(() => readBoot());
  const [dataset, setDataset] = useState(null);
  const [plugins, setPlugins] = useState(["pitch"]);
  // ★ 默认勾【恰好一个】：负责人「默认就是勾选一个」。
  //   而 key 从规则现算（KNOWN_RULES 的第一个），不写死 ——
  //   写死会在注入陌生插件时勾到一个不存在规则的 key。
  const [charts, setCharts] = useState(() =>
    KNOWN_RULES.length ? [KNOWN_RULES[0].id] : []
  );
  const [status, setStatus] = useState("");
  const [showMeta, setShowMeta] = useState(false);
  const [ref, setRef] = useState("");
  const [pra, setPra] = useState("");

  useEffect(() => {
    let alive = true;
    fetchView().then((v) => alive && setView(v));
    fetchDataset().then((d) => alive && setDataset(d));
    return () => {
      alive = false;
    };
  }, []);

  // ★ 可勾的插件清单来自 /dataset 的 plugins（★ 由 serve_ui 从 registry 注入），
  // ★ 【不是】从 view 推。
  // ★ ★ 理由：★ 懒加载之后，★ 没勾的插件根本不在 view 里；
  // ★ ★ 若从 view 推，★ 那就「没勾的插件永远勾不上」——★ 死路，
  // ★ ★ 恰恰掐死在「可插拔」这条线上。
  // ★ 回落到 view 推断，★ 只为未注入时仍能看到已算的那些。
  const available = useMemo(() => {
    const listed = dataset?.plugins ?? [];
    if (listed.length) {
      const rest = listed.filter((x) => !PLUGIN_ORDER.includes(x)).sort();
      return [...PLUGIN_ORDER.filter((x) => listed.includes(x)), ...rest];
    }
    const seen = new Set();
    for (const s of view?.scalars ?? []) seen.add(s.key.split(".")[0]);
    for (const s of view?.series ?? []) seen.add(s.key.split(".")[0]);
    const rest = [...seen].filter((x) => !PLUGIN_ORDER.includes(x)).sort();
    return [...PLUGIN_ORDER.filter((x) => seen.has(x)), ...rest];
  }, [dataset, view]);

  const togglePlugin = useCallback((id) => {
    setPlugins((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }, []);

  const toggleChart = useCallback((key) => {
    setCharts((prev) =>
      prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key]
    );
  }, []);

  // ★ 勾选变化就重算：★ 只把勾中的 id 交给内核，★ 那才是真懒加载。
  const key = plugins.join(",");
  useEffect(() => {
    if (!ref || !pra) return;
    if (plugins.length === 0) {
      setStatus("请至少勾选一个插件");
      return;
    }
    let alive = true;
    setStatus("正在分析…");
    // ★ 内联首屏快照到此为止：★ 之后一律读 /view，
    // ★ 否则页面会停在「第一次的结果」上（★ 表现为选曲后数字不变）。
    markBootStale();
    runSelection(ref, pra, setStatus, plugins).then(async (r) => {
      if (!alive) return;
      if (r.ok) {
        const v = await fetchView();
        if (alive) {
          setView(v);
          setStatus(`已算 ${plugins.length} 个插件：${plugins.join("、")}`);
        }
      }
    });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref, pra, key]);

  const series = view?.series ?? [];

  return (
    <main>
      <h1>口琴双音频对比</h1>

      <section className="picker">
        <label>
          参考演奏
          <select value={ref} onChange={(e) => setRef(e.target.value)}>
            <option value="">— 选择 —</option>
            {(dataset?.songs ?? []).map((song) => (
              <optgroup key={song.name} label={song.title || song.name}>
                {[song.original, song.melody_version].filter(Boolean).map((path) => (
                  <option key={path} value={path}>
                    {path.split("/").pop()}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <label>
          练习演奏（模拟吹奏的那一条）
          <select value={pra} onChange={(e) => setPra(e.target.value)}>
            <option value="">— 选择 —</option>
            {(dataset?.songs ?? []).flatMap((song) =>
              (song.practice ?? []).map((p) => (
                <option key={p.path} value={p.path}>
                  {(song.title || song.name) + " · " + p.name}
                </option>
              ))
            )}
          </select>
        </label>
      </section>

      <section className="plugins">
        <h2>插件（勾选即只算这些）</h2>
        {available.length === 0 ? <p className="empty">尚无数据。</p> : null}
        {available.map((id) => (
          <label key={id} className="plugin-toggle">
            <input
              type="checkbox"
              checked={plugins.includes(id)}
              onChange={() => togglePlugin(id)}
            />
            {PLUGIN_LABELS[id] || id} <span className="tag">{id}</span>
          </label>
        ))}
        {status ? <p className="status">{status}</p> : null}
      </section>

      {plugins.map((id) => (
        <PluginCard
          key={id}
          id={id}
          table={tableFor(id, series)}
          charts={chartsFor(id, series)}
          chosenCharts={charts}
          onToggleChart={toggleChart}
        />
      ))}

      <section className="meta">
        <button type="button" onClick={() => setShowMeta((s) => !s)}>
          {showMeta ? "收起" : "展开"}：本次分析信息
        </button>
        {showMeta ? (
          <pre>
            {JSON.stringify(metaOf(view ?? {}), null, 2)}
            {"\n\n"}
            {JSON.stringify(view?.port_summary ?? [], null, 2)}
          </pre>
        ) : null}
      </section>
    </main>
  );
}
