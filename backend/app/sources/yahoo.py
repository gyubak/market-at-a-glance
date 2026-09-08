"""yahoo finance 해외 데이터 소스 (스펙 3.1: 10초 지연 허용).

- 5분봉 history + fast_info.lastPrice 로 현재 봉을 갱신 → 현재가가 최신으로 유지됨.
- 개장 중에는 flat 패딩을 하지 않는다(지연된 야후 데이터를 가짜 봉으로 덮지 않기 위함).
- 데이터 끊기면 hub 가 빨간불, 폐장이면 회색불 + 종가 유지.
"""
from __future__ import annotations

import asyncio

from ..candlestore import CandleStore
from ..config import settings
from ..hub import hub
from ..market import KST, epoch, market_open
from ..series import LEFT, SeriesDef

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

try:
    from curl_cffi import requests as _cr
except Exception:  # pragma: no cover
    _cr = None


def _session():
    if _cr is None:
        return None
    try:
        return _cr.Session(impersonate="chrome")
    except Exception:
        return None


def _num(v):
    try:
        f = float(v)
        return f if f == f else None  # NaN 제외
    except (TypeError, ValueError):
        return None


def _fetch(ticker: str, sess) -> dict:
    """블로킹 — executor 에서 실행. {bars, last, prev_close} 반환."""
    tk = yf.Ticker(ticker, session=sess)
    df = tk.history(period="2d", interval="5m", auto_adjust=False)  # 9차: 36h 롤링 윈도우를 채울 여유분
    rows: list[dict] = []
    if df is not None and not df.empty:
        for ts, row in df.iterrows():
            kst_ts = ts.tz_convert(KST) if ts.tzinfo else ts.tz_localize("UTC").tz_convert(KST)
            dt = kst_ts.to_pydatetime()
            # 09:00 KST 컷은 여기서 하지 않는다 — global(24시간)물은 CandleStore가
            # market_key 기준으로 알아서 윈도우(롤링/day_open)를 적용한다.
            m = dt.minute - (dt.minute % 5)
            bt = epoch(dt.replace(minute=m, second=0, microsecond=0))
            o, h, l, c = _num(row["Open"]), _num(row["High"]), _num(row["Low"]), _num(row["Close"])
            if None in (o, h, l, c):
                continue
            rows.append({"t": bt, "o": o, "h": h, "l": l, "c": c})
    last = prev_close = None
    try:
        fi = tk.fast_info
        last = _num(fi.get("lastPrice"))
        prev_close = _num(fi.get("previousClose"))
    except Exception:
        pass
    return {"bars": rows, "last": last, "prev_close": prev_close}


class YahooCandles:
    def __init__(self, defs: list[SeriesDef] | None = None) -> None:
        self.defs = [d for d in (defs or LEFT) if settings.yahoo_ticker(d.id)]
        self.stores = {d.id: CandleStore(d.decimals, d.market_key) for d in self.defs}
        self.sess = _session()

    async def run(self) -> None:
        if yf is None:
            print("[yahoo] yfinance 미설치")
            return
        loop = asyncio.get_event_loop()
        while True:
            for d in self.defs:
                ticker = settings.yahoo_ticker(d.id)
                try:
                    res = await loop.run_in_executor(None, _fetch, ticker, self.sess)
                except Exception as e:  # noqa: BLE001
                    print(f"[yahoo] {d.id}({ticker}) 실패: {e}")
                    continue
                store = self.stores[d.id]
                if res["bars"]:
                    store.set_ohlc(res["bars"])
                is_open = market_open(d.market_key)
                if is_open and store.has_data():
                    # 현재 5분 버킷을 최신가(없으면 마지막 종가)로 채워
                    # 야후 지연 때문에 '현재/바로 옆 봉'이 비는 것을 방지
                    store.tick(res["last"] if res["last"] is not None else store.series()[-1]["c"])
                if not store.has_data():
                    continue
                bars = store.fill_to_now(flat=not is_open)
                price = res["last"] if res["last"] is not None else (bars[-1]["c"] if bars else None)
                if price is not None:
                    price = round(price, d.decimals)
                payload = {
                    "label": d.label, "unit": d.unit, "decimals": d.decimals,
                    "bars": bars, "price": price,
                }
                if res["prev_close"] and price:
                    payload["change_pct"] = round((price - res["prev_close"]) / res["prev_close"] * 100, 2)
                await hub.publish(d.id, "candles", payload, market_key=d.market_key)
            await asyncio.sleep(max(3, settings.poll_yahoo_sec))
