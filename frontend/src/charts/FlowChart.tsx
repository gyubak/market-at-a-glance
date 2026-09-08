import React, { useEffect, useRef, useState } from "react";
import type { FlowSeries } from "../types";
import { dayOpen, fmtClock } from "../lib/session";
import { cssFontPx } from "../lib/cssFont";

const GUT_L = 52;
const PAD_R = 10;
const AXIS_B = 18;
const SESSION_SPAN = 6 * 3600 + 40 * 60; // 09:00 ~ 15:40
const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

const INST_LABELS: Record<string, string> = {
  institution_sum: "기관계",
  financial_invest: "금융투자",
  investment_trust: "투자신탁",
  pension: "연기금",
  private_fund: "사모펀드",
  other_corp: "기타법인",
};

const SERIES = [
  { key: "individual", name: "개인", color: "#8b949e" },
  { key: "foreign", name: "외국인", color: "#e5484d" },
  { key: "institution", name: "기관", color: "#3b82f6" },
] as const;

type Drill = { kind: "foreign" | "institution"; x: number; y: number } | null;

export default function FlowChart({ series, clock, className = "block" }: { series: FlowSeries; clock: number; className?: string }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [box, setBox] = useState({ w: 600, h: 150 });
  const [drill, setDrill] = useState<Drill>(null);

  const w = box.w;
  const headH = Math.max(20, Math.round(box.h * 0.26));
  const chartH = box.h - headH;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setBox({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setBox({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const close = () => setDrill(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, []);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = w * dpr;
    cv.height = chartH * dpr;
    const g = cv.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, chartH);

    const border = css("--border") || "#21262d";
    const muted = css("--muted") || "#8b949e";
    const axisFontPx = cssFontPx("--fs-axis", 12);
    const axisFont = `${axisFontPx}px -apple-system, sans-serif`;
    // 9-3차: CandleChart 와 동일하게, 축 폰트가 커진 만큼 하단 여백도 같이 늘려서 시간축 라벨이 안 잘리게 함.
    const axisB = Math.max(AXIS_B, Math.ceil(axisFontPx * 1.3) + 4);
    const open = dayOpen(clock);
    const close = open + SESSION_SPAN;
    const chartW = Math.max(10, w - GUT_L - PAD_R);
    const tToX = (t: number) => GUT_L + ((t - open) / (close - open)) * chartW;

    const bars = series.bars || [];
    let mag = 1;
    bars.forEach((b) => {
      mag = Math.max(mag, Math.abs(b.individual), Math.abs(b.foreign), Math.abs(b.institution));
    });
    mag *= 1.1;
    const vToY = (v: number) => (1 - (v + mag) / (2 * mag)) * (chartH - axisB);

    g.strokeStyle = muted;
    g.beginPath();
    g.moveTo(GUT_L, vToY(0));
    g.lineTo(w - PAD_R, vToY(0));
    g.stroke();

    g.font = axisFont;
    g.fillStyle = muted;
    g.textAlign = "left";
    g.textBaseline = "middle";
    [mag, mag / 2, 0, -mag / 2, -mag].forEach((v) => g.fillText(Math.round(v).toString(), 4, vToY(v)));

    // x: 15분마다 눈금선, 라벨은 정각(HH:00)만
    g.textAlign = "center";
    g.textBaseline = "top";
    for (let t = open; t <= close; t += 300) {
      const min = Math.floor(t / 60 + 540) % 1440;
      if (min % 15 !== 0) continue;
      const x = tToX(t);
      const onHour = min % 60 === 0;
      g.strokeStyle = border;
      g.globalAlpha = onHour ? 1 : 0.5;
      g.beginPath();
      g.moveTo(x, 0);
      g.lineTo(x, chartH - axisB);
      g.stroke();
      g.globalAlpha = 1;
      if (onHour) {
        g.fillStyle = muted;
        g.fillText(fmtClock(t), x, chartH - axisB + 3);
      }
    }

    for (const s of SERIES) {
      g.strokeStyle = s.color;
      g.lineWidth = 1.9;
      g.beginPath();
      bars.forEach((b, i) => {
        const x = tToX(b.t);
        const y = vToY((b as any)[s.key]);
        if (i === 0) g.moveTo(x, y);
        else g.lineTo(x, y);
      });
      g.stroke();
    }
    g.lineWidth = 1;
  }, [series, clock, w, chartH]);

  const cur = series.current || { individual: 0, foreign: 0, institution: 0 };

  function openDrill(kind: "foreign" | "institution", e: React.MouseEvent) {
    e.stopPropagation();
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setDrill((d) => (d?.kind === kind ? null : { kind, x: r.left, y: r.bottom + 4 }));
  }

  return (
    <div ref={wrapRef} className={className}>
      <div style={{ position: "absolute", inset: "0 0 auto 0", height: headH, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 10px", gap: 8, fontSize: "var(--fs-flow-head)" }}>
        <span style={{ fontWeight: 700, whiteSpace: "nowrap" }}>
          {series.label}
          <span className={"light-dot " + series.light} />
        </span>
        <span style={{ fontVariantNumeric: "tabular-nums", display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "flex-end", fontWeight: 600 }}>
          <span style={{ color: "#8b949e" }}>개인 {fmtEok(cur.individual)}</span>
          <span style={{ color: "#e5484d", cursor: "pointer", textDecoration: drill?.kind === "foreign" ? "underline" : "none" }}
            onClick={(e) => openDrill("foreign", e)}>
            외국인 {fmtEok(cur.foreign)}
          </span>
          <span style={{ color: "#3b82f6", cursor: "pointer", textDecoration: drill?.kind === "institution" ? "underline" : "none" }}
            onClick={(e) => openDrill("institution", e)}>
            기관 {fmtEok(cur.institution)}
          </span>
        </span>
      </div>

      <canvas ref={canvasRef} style={{ position: "absolute", left: 0, top: headH, width: w, height: chartH, opacity: series.unavailable ? 0.15 : 1 }} />
      {series.unavailable && (
        <div style={{ position: "absolute", left: 0, top: headH, width: "100%", height: chartH, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)" }}>
          장 시작 후 집계됩니다
        </div>
      )}

      {drill && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            position: "fixed", left: drill.x, top: drill.y, zIndex: 50,
            background: "rgba(17,20,24,0.97)", border: "1px solid var(--border)", borderRadius: 6,
            padding: "8px 12px", fontSize: "0.9em", fontVariantNumeric: "tabular-nums",
            boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
          }}
        >
          {drill.kind === "foreign" ? (
            series.foreign_detail ? (
              <Grid rows={series.foreign_detail} labels={{}} />
            ) : (
              <span style={{ color: "var(--muted)" }}>외국증권사 Top-5 · 연동 예정</span>
            )
          ) : (
            <Grid rows={series.institution_detail} labels={INST_LABELS} />
          )}
        </div>
      )}
    </div>
  );
}

function Grid({ rows, labels }: { rows: Record<string, number>; labels: Record<string, string> }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "auto auto", gap: "2px 12px" }}>
      {Object.entries(rows).map(([k, v]) => (
        <React.Fragment key={k}>
          <span style={{ color: "var(--muted)" }}>{labels[k] ?? k}</span>
          <span style={{ textAlign: "right", color: v >= 0 ? "var(--up)" : "var(--down)" }}>{fmtEok(v)}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

function fmtEok(v: number): string {
  return `${v >= 0 ? "+" : ""}${Math.round(v).toLocaleString()}억`;
}
