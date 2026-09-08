import { useEffect, useState } from "react";

export const BAR_SEC = 300;
const KST_OFFSET_MIN = 9 * 60;

/** epoch(sec) → KST 벽시계 분(0=자정). */
function kstMinutes(epochSec: number): number {
  return ((Math.floor(epochSec / 60) + KST_OFFSET_MIN) % (24 * 60) + 24 * 60) % (24 * 60);
}

export function nowEpoch(): number {
  return Date.now() / 1000;
}

/** 가장 최근의 09:00 KST (= 그 거래일 시작). 자정을 넘겨도 세션이 이어진다. */
export function dayOpen(ref = nowEpoch()): number {
  const kstDayStart = Math.floor((ref + KST_OFFSET_MIN * 60) / 86400) * 86400 - KST_OFFSET_MIN * 60;
  let open = kstDayStart + 9 * 3600;
  if (ref < open) open -= 86400;
  return open;
}

/**
 * 가장 우측 5분봉 시각. freeze 없음 — 정규장이 끝나도 계속 흐른다.
 * (닫힌 상품은 백엔드가 종가를 flat 봉으로 채워 보낸다)
 */
export function currentBarTime(ref = nowEpoch()): number {
  return Math.floor(ref / BAR_SEC) * BAR_SEC;
}

export function fmtClock(epochSec: number): string {
  const m = kstMinutes(epochSec);
  const hh = String(Math.floor(m / 60)).padStart(2, "0");
  const mm = String(m % 60).padStart(2, "0");
  return `${hh}:${mm}`;
}

/** KST 현재시각 "HH:MM:SS" */
export function fmtClockSeconds(epochSec: number): string {
  const totalSec = (Math.floor(epochSec) + KST_OFFSET_MIN * 60) % 86400;
  const hh = String(Math.floor(totalSec / 3600)).padStart(2, "0");
  const mm = String(Math.floor((totalSec % 3600) / 60)).padStart(2, "0");
  const ss = String(totalSec % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

/** 1초마다 갱신되는 KST now (epoch sec). */
export function useClock(): number {
  const [t, setT] = useState(nowEpoch());
  useEffect(() => {
    const id = window.setInterval(() => setT(nowEpoch()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return t;
}
