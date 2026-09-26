import React from "react";

// ★ 对比图：★ 两条线叠放，★ 参考一条蓝、练习一条红。
// ★ 手写 SVG 而不用图表库 ——★ 理由：图形必须与 metrics.json 逐值对应，
// ★ 而图表库会自己重采样/补间，★ 那会让图上的数与落盘的数对不上。
// ★ 那正是本项目最防的假绿。

const W = 720;
const H = 240;
const PAD_L = 56;
const PAD_R = 16;
const PAD_T = 28;
const PAD_B = 52;

function buildPath(xs, ys, xMin, xMax, yMin, yMax) {
  let d = "";
  for (let i = 0; i < xs.length; i++) {
    const px = PAD_L + ((xs[i] - xMin) / (xMax - xMin || 1)) * (W - PAD_L - PAD_R);
    const py = PAD_T + (1 - (ys[i] - yMin) / (yMax - yMin || 1)) * (H - PAD_T - PAD_B);
    d += (i === 0 ? "M" : "L") + px.toFixed(2) + " " + py.toFixed(2);
  }
  return d;
}

function ticks(min, max, count) {
  const out = [];
  for (let i = 0; i <= count; i++) out.push(min + ((max - min) * i) / count);
  return out;
}

export function ComparisonChart({ title, unit, xLabel, refValues, pracValues, xs }) {
  const all = [...refValues, ...pracValues].filter((v) => Number.isFinite(v));
  if (!all.length) return null;
  let yMin = Math.min(...all);
  let yMax = Math.max(...all);
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
  }
  const xMin = xs[0];
  const xMax = xs[xs.length - 1];
  const yPad = (yMax - yMin) * 0.08;
  const lo = yMin - yPad;
  const hi = yMax + yPad;

  return (
    <figure className="chart">
      <figcaption>{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={title}>
        {/* 网格与刻度 */}
        {ticks(lo, hi, 4).map((v, i) => {
          const py = PAD_T + (1 - (v - lo) / (hi - lo)) * (H - PAD_T - PAD_B);
          return (
            <g key={`g${i}`}>
              <line x1={PAD_L} y1={py} x2={W - PAD_R} y2={py} stroke="#e6e6e6" />
              <text x={PAD_L - 8} y={py + 4} textAnchor="end" fontSize="11" fill="#666">
                {v.toFixed(1)}
              </text>
            </g>
          );
        })}
        {/* 坐标轴 */}
        <line x1={PAD_L} y1={H - PAD_B} x2={W - PAD_R} y2={H - PAD_B} stroke="#999" />
        <line x1={PAD_L} y1={PAD_T} x2={PAD_L} y2={H - PAD_B} stroke="#999" />
        <text x={PAD_L} y={16} fontSize="11" fill="#666">
          {unit}
        </text>
        <text x={PAD_L} y={H - 12} fontSize="11" fill="#666">
          {xLabel}
        </text>
        {/* 两条线：参考蓝、练习红 */}
        <path
          d={buildPath(xs, refValues, xMin, xMax, lo, hi)}
          fill="none"
          stroke="#1f6feb"
          strokeWidth="1.6"
        />
        <path
          d={buildPath(xs, pracValues, xMin, xMax, lo, hi)}
          fill="none"
          stroke="#d93025"
          strokeWidth="1.6"
        />
      </svg>
      <div className="legend">
        <span className="ref">参考</span>
        <span className="prac">练习</span>
      </div>
    </figure>
  );
}
