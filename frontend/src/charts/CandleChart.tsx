import { useEffect, useMemo, useRef, useState } from "react";
import type { Bar, CandleSeries } from "../types";
import { BAR_SEC, currentBarTime, fmtClock } from "../lib/session";
import { setHoverOHLC, clearHoverOHLC } from "../lib/hover";
import { cssFontPx } from "../lib/cssFont";

const VISIBLE_BARS = 48; // 약 4시간
const GUT_L = 48;
const PAD_R = 8;
const PAD_T = 3;
const AXIS_B = 13;
// 9차: 가로/세로축 눈금·크로스헤어 태그·현재가 박스 폰트는 canvas 그리기라 CSS로 못 늘리므로
// --fs-axis/--fs-tag/--fs-price-tag(index.css) 계산값을 읽어와 화면 폭에 비례하게 그린다.
const FONT_FAMILY = "-apple-system, sans-serif";
const TAG_H_RATIO = 1.35; // 태그 박스 높이 = 폰트 크기 * 이 비율(기존 10px폰트/13px박스, 12px폰트/16px박스 비와 동일)

const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

interface Props {
  series: CandleSeries;
  clock: number;
  className?: string;
}

export default function CandleChart({ series, clock, className = "block chart-box" }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [box, setBox] = useState({ w: 320, h: 80 });
  const [panBars, setPanBars] = useState(0);
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null);
  const drag = useRef<{ x: number; startPan: number } | null>(null);

  const headH = Math.max(14, Math.round(box.h * 0.2));
  const chartH = box.h - headH;
  const w = box.w;

  // 9-3차: 축 폰트가 화면 크기에 비례해 커지므로, 시간축 라벨이 잘리지 않도록
  // 하단 여백(AXIS_B)도 실제 폰트 크기에 맞춰 늘어나야 한다(고정 13px로는 부족해짐).
  const axisFontPx = cssFontPx("--fs-axis", 10);
  const tagFontPx = cssFontPx("--fs-tag", 10);
  const priceTagFontPx = cssFontPx("--fs-price-tag", 12);
  const axisB = Math.max(AXIS_B, Math.ceil(Math.max(axisFontPx, tagFontPx) * 1.3) + 4);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setBox({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setBox({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const bars = series.bars;
  const barByT = useMemo(() => {
    const m = new Map<number, Bar>();
    bars.forEach((b) => m.set(b.t, b));
    return m;
  }, [bars]);

  const rightT = currentBarTime(clock) + panBars * BAR_SEC;
  const domainRight = rightT + BAR_SEC * 0.5;
  const domainLeft = rightT - (VISIBLE_BARS - 1) * BAR_SEC - BAR_SEC * 0.5;
  const chartW = Math.max(10, w - GUT_L - PAD_R);
  const barPx = chartW / VISIBLE_BARS;

  const tToX = (t: number) => GUT_L + ((t - domainLeft) / (domainRight - domainLeft)) * chartW;
  const xToT = (x: number) => domainLeft + ((x - GUT_L) / chartW) * (domainRight - domainLeft);

  const visBars = bars.filter((b) => b.t >= domainLeft - BAR_SEC && b.t <= domainRight + BAR_SEC);
  let lo = Infinity;
  let hi = -Infinity;
  visBars.forEach((b) => {
    lo = Math.min(lo, b.l);
    hi = Math.max(hi, b.h);
  });
  if (!isFinite(lo)) {
    lo = 0;
    hi = 1;
  }
  const pad = (hi - lo) * 0.06 || hi * 0.001 || 1;
  const yLo = lo - pad;
  const yHi = hi + pad;
  const plotBottom = chartH - PAD_T - axisB;
  const vToY = (v: number) => PAD_T + (1 - (v - yLo) / (yHi - yLo)) * plotBottom;
  const yToV = (y: number) => yLo + (1 - (y - PAD_T) / plotBottom) * (yHi - yLo);

  const snapT = hover ? Math.round(xToT(hover.x) / BAR_SEC) * BAR_SEC : null;
  const hoveredBar = snapT != null ? barByT.get(snapT) : undefined;
  const lastBar = bars[bars.length - 1];
  const dec = series.decimals;
  const price = series.price ?? (lastBar ? lastBar.c : null);
  const pct = series.change_pct;

  useEffect(() => {
    if (hoveredBar) {
      setHoverOHLC(series.id, { label: series.label, decimals: dec, o: hoveredBar.o, h: hoveredBar.h, l: hoveredBar.l, c: hoveredBar.c });
    } else {
      clearHoverOHLC(series.id);
    }
  }, [hoveredBar, series.id, series.label, dec]);
  useEffect(() => () => clearHoverOHLC(series.id), [series.id]);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = w * dpr;
    cv.height = chartH * dpr;
    const g = cv.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, chartH);

    const up = css("--up") || "#e5484d";
    const down = css("--down") || "#3b82f6";
    const border = css("--border") || "#21262d";
    const muted = css("--muted") || "#8b949e";
    const accent = css("--accent") || "#f5c518";

    const labelFont = `${axisFontPx}px ${FONT_FAMILY}`;
    const tagFont = `${tagFontPx}px ${FONT_FAMILY}`;
    const priceTagFont = `${priceTagFontPx}px ${FONT_FAMILY}`;
    const tagH = Math.round(tagFontPx * TAG_H_RATIO);
    const priceTagH = Math.round(priceTagFontPx * TAG_H_RATIO);

    const yTicks = plotBottom < 90 ? 2 : plotBottom < 150 ? 3 : 4;

    // y grid + labels
    g.font = labelFont;
    g.textBaseline = "middle";
    for (let i = 0; i <= yTicks; i++) {
      const v = yLo + ((yHi - yLo) * i) / yTicks;
      const y = vToY(v);
      g.strokeStyle = border;
      g.beginPath();
      g.moveTo(GUT_L, y);
      g.lineTo(w - PAD_R, y);
      g.stroke();
      g.fillStyle = muted;
      g.textAlign = "left";
      g.fillText(v.toFixed(dec), 3, Math.max(6, Math.min(chartH - axisB - 4, y)));
    }

    // x: 15분마다 눈금선, 라벨은 정각(HH:00)만
    g.textAlign = "center";
    g.textBaseline = "top";
    for (let t = Math.ceil(domainLeft / BAR_SEC) * BAR_SEC; t <= domainRight; t += BAR_SEC) {
      const min = Math.floor(t / 60 + 540) % 1440;
      if (min % 15 !== 0) continue;
      const x = tToX(t);
      const onHour = min % 60 === 0;
      g.strokeStyle = border;
      g.globalAlpha = onHour ? 1 : 0.5;
      g.beginPath();
      g.moveTo(x, PAD_T);
      g.lineTo(x, chartH - axisB);
      g.stroke();
      g.globalAlpha = 1;
      if (onHour) {
        g.fillStyle = muted;
        g.fillText(fmtClock(t), x, chartH - axisB + 2);
      }
    }

    // candles
    const bw = Math.max(1, barPx * 0.62);
    visBars.forEach((b) => {
      const x = tToX(b.t);
      const rising = b.c >= b.o;
      g.strokeStyle = rising ? up : down;
      g.fillStyle = rising ? up : down;
      g.beginPath();
      g.moveTo(x, vToY(b.h));
      g.lineTo(x, vToY(b.l));
      g.stroke();
      const yo = vToY(b.o);
      const yc = vToY(b.c);
      g.fillRect(x - bw / 2, Math.min(yo, yc), bw, Math.max(1, Math.abs(yo - yc)));
    });

    // 현재값 수평선 + 노란 태그
    if (lastBar && !hover) {
      const y = vToY(lastBar.c);
      g.strokeStyle = muted;
      g.setLineDash([3, 3]);
      g.beginPath();
      g.moveTo(GUT_L, y);
      g.lineTo(w - PAD_R, y);
      g.stroke();
      g.setLineDash([]);
      drawTag(g, 1, clampY(y, chartH, axisB), lastBar.c.toFixed(dec), accent, "#000", "left", priceTagFont, priceTagH);
    }

    // crosshair
    if (hover) {
      const sx = snapT != null ? tToX(snapT) : hover.x;
      const cy = Math.max(PAD_T, Math.min(chartH - axisB, hover.y));
      g.strokeStyle = muted;
      g.setLineDash([2, 2]);
      g.beginPath();
      g.moveTo(sx, PAD_T);
      g.lineTo(sx, chartH - axisB);
      g.moveTo(GUT_L, cy);
      g.lineTo(w - PAD_R, cy);
      g.stroke();
      g.setLineDash([]);
      if (snapT != null) drawTag(g, sx, chartH - axisB + 1, fmtClock(snapT), accent, "#000", "center", tagFont, tagH);
      drawTag(g, 1, cy, yToV(cy).toFixed(dec), accent, "#000", "left", tagFont, tagH);
    }
  }, [series, clock, w, chartH, hover, panBars, snapT, axisB, axisFontPx, tagFontPx, priceTagFontPx]);

  function onMove(e: React.MouseEvent) {
    const r = canvasRef.current!.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    if (drag.current) {
      const dxBars = (x - drag.current.x) / barPx;
      setPanBars(clamp(drag.current.startPan - dxBars, -(VISIBLE_BARS * 6), 0));
    } else {
      setHover({ x, y });
    }
  }

  return (
    <div ref={wrapRef} className={className}>
      <div
        style={{
          position: "absolute",
          inset: "0 0 auto 0",
          height: headH,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 6px",
          gap: 5,
          fontSize: "var(--fs-chart-head)",
          lineHeight: 1,
        }}
      >
        <span style={{ fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {series.label}
          <span className={"light-dot " + series.light} />
        </span>
        <span style={{ fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap", display: "flex", alignItems: "baseline", gap: 4 }}>
          {pct != null && (
            <span style={{ fontSize: "0.9em", fontWeight: 600, color: pct > 0 ? "var(--up)" : pct < 0 ? "var(--down)" : "var(--muted)" }}>
              {pct > 0 ? "+" : ""}
              {pct.toFixed(2)}%
            </span>
          )}
          {price != null && <b style={{ color: "var(--text)" }}>{price.toFixed(dec)}</b>}
        </span>
      </div>
      {series.unavailable && (
        <div style={{ position: "absolute", left: 0, top: headH, width: "100%", height: chartH, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)", fontSize: "var(--fs-chart-head)" }}>
          데이터 미연동
        </div>
      )}
      <canvas
        ref={canvasRef}
        style={{ position: "absolute", left: 0, top: headH, width: w, height: chartH, cursor: drag.current ? "grabbing" : "crosshair", opacity: series.unavailable ? 0 : 1 }}
        onMouseMove={onMove}
        onMouseLeave={() => {
          setHover(null);
          drag.current = null;
        }}
        onMouseDown={(e) => {
          const r = canvasRef.current!.getBoundingClientRect();
          drag.current = { x: e.clientX - r.left, startPan: panBars };
          setHover(null);
        }}
        onMouseUp={() => (drag.current = null)}
      />
    </div>
  );
}

function clamp(v: number, a: number, b: number) {
  return Math.max(a, Math.min(b, v));
}
function clampY(y: number, chartH: number, axisB: number) {
  return Math.max(8, Math.min(chartH - axisB - 4, y));
}

function drawTag(
  g: CanvasRenderingContext2D,
  x: number,
  y: number,
  text: string,
  bg: string,
  fg: string,
  align: "left" | "center",
  font: string,
  h: number
) {
  g.font = font;
  const tw = g.measureText(text).width;
  const padX = 3;
  let bx = x;
  if (align === "center") bx = x - tw / 2 - padX;
  const by = align === "center" ? y : y - h / 2;
  g.fillStyle = bg;
  g.fillRect(bx, by, tw + padX * 2, h);
  g.fillStyle = fg;
  g.textAlign = "left";
  g.textBaseline = align === "center" ? "top" : "middle";
  g.fillText(text, bx + padX, align === "center" ? by + 2 : y);
}
