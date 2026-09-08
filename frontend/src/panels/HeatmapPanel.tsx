import { useEffect, useMemo, useRef, useState } from "react";
import { squarify } from "../lib/treemap";
import { useSeries } from "../lib/store";
import type { HeatmapRow, HeatmapSeries } from "../types";

const SECTOR_GAP = 2;
const CELL_GAP = 1;
const FLAT_EPS = 0.05; // |등락률| 이 이 값 미만이면 보합 → 회색

function pctColor(pct: number | null): string {
  if (pct == null || Math.abs(pct) < FLAT_EPS) return "var(--heat-flat)"; // 보합/미상: 회색
  const t = Math.max(-1, Math.min(1, pct / 3)); // ±3% 이상이면 최대 채도로 포화
  const alpha = Math.round((0.18 + Math.abs(t) * 0.55) * 100);
  const tone = t >= 0 ? "var(--up)" : "var(--down)";
  return `color-mix(in srgb, ${tone} ${alpha}%, var(--panel-2))`;
}

/** 섹터 이름표 높이/폰트 — 섹터 영역 크기에 비례. */
function sectorLabel(rectW: number): { h: number; font: number } {
  const font = Math.max(10, Math.min(20, Math.round(rectW / 13)));
  return { h: font + 5, font };
}

/** 셀 안 종목명/등락률 폰트 — 셀 크기에 비례. 너무 작으면 숨김. */
function cellText(w: number, h: number, nameLen: number) {
  if (w < 30 || h < 18) return { show: false, name: 0, pct: 0, showPct: false };
  const byWidth = (w - 5) / Math.max(2, nameLen * 0.92);
  const byHeight = h * 0.32;
  const name = Math.max(9, Math.min(24, Math.floor(Math.min(byWidth, byHeight))));
  return { show: true, name, pct: Math.max(8, Math.round(name * 0.78)), showPct: h >= 34 };
}

interface Group {
  sector: string;
  rect: { x: number; y: number; w: number; h: number };
  labelH: number;
  labelFont: number;
  cells: { row: HeatmapRow; rect: { x: number; y: number; w: number; h: number } }[];
}

export default function HeatmapPanel() {
  const s = useSeries("kospi_heatmap") as HeatmapSeries | undefined;
  const wrapRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ w: 600, h: 300 });

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setBox({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setBox({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const groups = useMemo<Group[]>(() => {
    if (!s || !s.rows.length || box.w <= 0 || box.h <= 0) return [];
    const bySector = new Map<string, HeatmapRow[]>();
    for (const r of s.rows) {
      const arr = bySector.get(r.sector) ?? [];
      arr.push(r);
      bySector.set(r.sector, arr);
    }
    const sectors = Array.from(bySector.entries()).map(([sector, rows]) => ({
      sector,
      rows: rows.slice().sort((a, b) => b.market_cap_eok - a.market_cap_eok),
      total: rows.reduce((a, r) => a + Math.max(r.market_cap_eok, 0.01), 0),
    }));
    sectors.sort((a, b) => b.total - a.total);

    const outerRect = { x: 0, y: 0, w: box.w, h: box.h };
    const sectorRects = squarify(sectors.map((g) => g.total), outerRect);

    return sectors.map((g, i) => {
      const r = sectorRects[i];
      const lbl = sectorLabel(r.w);
      const inner = {
        x: r.x + SECTOR_GAP / 2,
        y: r.y + lbl.h,
        w: Math.max(0, r.w - SECTOR_GAP),
        h: Math.max(0, r.h - lbl.h - SECTOR_GAP / 2),
      };
      const cellRects = squarify(
        g.rows.map((row) => Math.max(row.market_cap_eok, 0.01)),
        inner
      );
      return {
        sector: g.sector,
        rect: r,
        labelH: lbl.h,
        labelFont: lbl.font,
        cells: g.rows.map((row, j) => ({ row, rect: cellRects[j] })),
      };
    });
  }, [s, box.w, box.h]);

  return (
    <>
      <div className="panel-head">
        <span>🔥 코스피 히트맵</span>
        <span style={{ fontSize: "0.8em" }}>{s ? `시총 상위 ${s.rows.length}` : ""}</span>
      </div>
      <div ref={wrapRef} className="heatmap-body">
        {!s || !groups.length ? (
          <div className="placeholder">
            섹터별 시가총액 히트맵(시총 Top-30)
            <br />
            (데이터 수신 대기 중)
          </div>
        ) : (
          groups.map((g) => (
            <div
              key={g.sector}
              className="heat-sector"
              style={{ left: g.rect.x, top: g.rect.y, width: g.rect.w, height: g.rect.h }}
            >
              <div
                className="heat-sector-label"
                style={{ height: g.labelH, lineHeight: `${g.labelH}px`, fontSize: g.labelFont }}
              >
                {g.sector}
              </div>
              {g.cells.map(({ row, rect }) => {
                const t = cellText(rect.w - CELL_GAP, rect.h - CELL_GAP, row.name.length);
                return (
                  <div
                    key={row.code}
                    className="heat-cell"
                    style={{
                      left: rect.x - g.rect.x,
                      top: rect.y - g.rect.y,
                      width: Math.max(0, rect.w - CELL_GAP),
                      height: Math.max(0, rect.h - CELL_GAP),
                      background: pctColor(row.change_pct),
                    }}
                    title={`${row.name} ${row.change_pct != null ? row.change_pct.toFixed(2) + "%" : ""}`}
                  >
                    {t.show && (
                      <span className="heat-name" style={{ fontSize: t.name }}>
                        {row.name}
                      </span>
                    )}
                    {t.show && t.showPct && row.change_pct != null && (
                      <span className="heat-pct" style={{ fontSize: t.pct }}>
                        {row.change_pct > 0 ? "+" : ""}
                        {row.change_pct.toFixed(1)}%
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>
    </>
  );
}
