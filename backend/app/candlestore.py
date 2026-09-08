"""세션 5분봉 저장소.

- 소스가 OHLC 배열을 주면 그대로 담고, 현재가 틱만 오는 소스는 tick() 사용.
- 발행 시 fill_to_now() 로 마지막 봉 이후를 '종가 유지(flat)' 봉으로 채운다
  → 시장이 닫혀도 시간축이 계속 흐르고 종가가 유지된다.
- 보관 구간의 왼쪽 경계:
  - 국내 kr_regular 는 day_open()(직전 09:00 KST), kr_futures 는 직전 08:45 KST
    기준(자정을 넘겨도 세션 유지).
  - 해외/24시간물(global)은 거래일 개념이 없으므로 09:00 KST 컷 대신 최근 N시간
    롤링 윈도우를 쓴다(9차: 아침에 백엔드를 재기동하면 해외 지표들의 간밤 데이터가
    day_open 09:00 경계에 걸려 전부 사라져 보이던 문제).
"""
from __future__ import annotations

from datetime import datetime

from .market import BAR_SEC, current_bar_time, day_open, epoch, now_kst

GLOBAL_WINDOW_SEC = 36 * 3600  # global 시장 보관 창(약 1.5일)


class CandleStore:
    def __init__(self, decimals: int, market_key: str = "kr_regular") -> None:
        self.decimals = decimals
        self.market_key = market_key
        self.bars: dict[int, dict] = {}

    def _round(self, v: float) -> float:
        return round(float(v), self.decimals)

    def _window_lo(self, ref: datetime | None = None) -> int:
        if self.market_key == "global":
            return epoch(ref or now_kst()) - GLOBAL_WINDOW_SEC
        return epoch(day_open(ref, self.market_key))

    def tick(self, price: float, ref: datetime | None = None) -> None:
        bt = epoch(current_bar_time(ref))
        price = self._round(price)
        bar = self.bars.get(bt)
        if bar is None:
            prev = self._last_bar_before(bt)
            o = prev["c"] if prev else price
            self.bars[bt] = {"t": bt, "o": o, "h": max(o, price), "l": min(o, price), "c": price}
        else:
            bar["c"] = price
            bar["h"] = max(bar["h"], price)
            bar["l"] = min(bar["l"], price)

    def set_ohlc(self, rows: list[dict], ref: datetime | None = None) -> None:
        """rows: [{t: epoch, o,h,l,c}] — 세션 시작 이후만 유지.
        이미 확정(5분 경과)된 봉은 덮어쓰지 않는다 → 매 폴링 재합산에 따른 흔들림 방지.
        현재 형성 중인 봉만 계속 갱신."""
        lo = self._window_lo(ref)
        now = epoch(ref or now_kst())
        for r in rows:
            t = int(r["t"])
            if t < lo:
                continue
            if t + BAR_SEC <= now and t in self.bars:
                continue  # 확정 봉 고정
            self.bars[t] = {
                "t": t,
                "o": self._round(r["o"]),
                "h": self._round(r["h"]),
                "l": self._round(r["l"]),
                "c": self._round(r["c"]),
            }

    def _last_bar_before(self, t: int) -> dict | None:
        keys = [k for k in self.bars if k < t]
        return self.bars[max(keys)] if keys else None

    def series(self, ref: datetime | None = None) -> list[dict]:
        lo = self._window_lo(ref)
        hi = epoch(current_bar_time(ref))
        return [self.bars[k] for k in sorted(self.bars) if lo <= k <= hi]

    def fill_to_now(self, ref: datetime | None = None, *, flat: bool = True) -> list[dict]:
        """실제 봉 목록.
        - 실제 봉 사이의 빈 5분 버킷은 직전 종가로 flat 채움(항상). 야후 지연으로
          '현재 바로 옆 봉'이 비어 보이는 문제 방지.
        - flat=True 이면 마지막 봉 이후 ~ 현재 시각까지도 flat 봉을 덧붙인다(폐장 시 종가 유지)."""
        real = self.series(ref)
        if not real:
            return []
        out: list[dict] = []
        for i, bar in enumerate(real):
            if i > 0:
                t = real[i - 1]["t"] + BAR_SEC
                while t < bar["t"]:
                    c = out[-1]["c"]
                    out.append({"t": t, "o": c, "h": c, "l": c, "c": c, "flat": True})
                    t += BAR_SEC
            out.append(bar)
        if flat:
            last_c = out[-1]["c"]
            t = out[-1]["t"] + BAR_SEC
            end = epoch(current_bar_time(ref))
            while t <= end:
                out.append({"t": t, "o": last_c, "h": last_c, "l": last_c, "c": last_c, "flat": True})
                t += BAR_SEC
        return out

    def has_data(self) -> bool:
        return bool(self.bars)


def rows_to_5m(raw: list[dict], *, t: str, o: str, h: str, l: str, c: str,
               src_interval: int = 60) -> list[dict]:
    """임의 간격 행들을 5분봉으로 묶는다. raw[t] 는 epoch(sec).
    KIS 는 창(window)이 5분 경계에 안 맞아 가장 오래된 버킷이 불완전하게 합쳐지므로
    (o/h/l 이 폴링마다 흔들림) 불완전한 최고참 버킷은 버린다."""
    order = sorted(raw, key=lambda r: r[t])
    out: dict[int, dict] = {}
    counts: dict[int, int] = {}
    for r in order:
        bt = int(r[t]) - (int(r[t]) % 300)
        counts[bt] = counts.get(bt, 0) + 1
        ov, hv, lv, cv = float(r[o]), float(r[h]), float(r[l]), float(r[c])
        b = out.get(bt)
        if b is None:
            out[bt] = {"t": bt, "o": ov, "h": hv, "l": lv, "c": cv}
        else:
            b["h"] = max(b["h"], hv)
            b["l"] = min(b["l"], lv)
            b["c"] = cv
    keys = sorted(out)
    expected = max(1, 300 // max(1, src_interval))
    if len(keys) > 1 and counts.get(keys[0], 0) < expected:
        keys = keys[1:]
    return [out[k] for k in keys]
