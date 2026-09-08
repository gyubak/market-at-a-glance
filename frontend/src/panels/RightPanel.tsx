import { useState } from "react";
import CandleChart from "../charts/CandleChart";
import Sparkline from "../charts/Sparkline";
import { useSeries } from "../lib/store";
import type { CandleSeries, RankingSeries } from "../types";

function fmtEok(v: number) {
  if (Math.abs(v) >= 10000) return (v / 10000).toFixed(1) + "조";
  return Math.round(v).toLocaleString() + "억";
}

export default function RightPanel({ clock }: { clock: number }) {
  const ktb = useSeries("ktb3y") as CandleSeries | undefined;
  const rank = useSeries("value_rank") as RankingSeries | undefined;
  const [tab, setTab] = useState<"value" | "search">("value");
  return (
    <>
      {ktb ? <CandleChart series={ktb} clock={clock} /> : <div className="block chart-box" />}

      <div className="panel-head">
        <span>🇰🇷 종목</span>
        <span className="switch">
          <button className={tab === "value" ? "on" : ""} onClick={() => setTab("value")}>
            거래대금
          </button>
          <button className={tab === "search" ? "on" : ""} onClick={() => setTab("search")}>
            검색상위
          </button>
        </span>
      </div>

      {tab === "value" ? (
        rank && rank.rows.length ? (
          <div className="rank-list">
            {rank.rows.map((r) => (
              <div key={r.code} className="rank-row">
                <div className="rank-info">
                  <div className="rank-name">{r.name}</div>
                  <div className="rank-sub">
                    시총 {fmtEok(r.market_cap_eok)} · 거래대금 {fmtEok(r.trade_value_eok)}
                  </div>
                </div>
                <div className="rank-chart">
                  <div className="rank-price">
                    {r.change_pct != null && (
                      <span
                        className="rank-pct"
                        style={{
                          color:
                            r.change_pct > 0 ? "var(--up)" : r.change_pct < 0 ? "var(--down)" : "var(--muted)",
                        }}
                      >
                        {r.change_pct > 0 ? "+" : ""}
                        {r.change_pct.toFixed(2)}%
                      </span>
                    )}
                    {r.price.toLocaleString()}
                  </div>
                  <Sparkline values={r.spark} className="rank-spark" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="placeholder">
            거래대금 상위 Top-30
            <br />
            (데이터 수신 대기 중)
          </div>
        )
      ) : (
        <div className="placeholder">
          검색 상위종목
          <br />
          KIS Open API엔 실시간 검색순위 TR이 없어 미구현(관심종목등록 상위로는 대체 가능 — 필요시 요청)
        </div>
      )}
    </>
  );
}
