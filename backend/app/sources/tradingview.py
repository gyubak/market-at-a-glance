"""TradingView 비공식 websocket 스트리머.

- **하나의 상시 연결**로 여러 심볼을 구독한다(연결을 매번 새로 열지 않음).
  → 트래픽이 적어 차단 위험이 낮고, 스냅샷 폴링이 아니라 스트리밍이라 실시간에 가깝다.
- 5분봉 히스토리는 chart series(timescale_update / du)로, 현재가·등락률은 quote(qsd 의 lp/chp)로 받는다.
- 표준 websockets 만 사용. 공식 API 가 아니므로 개인용 로컬 대시보드 한정.
  프로토콜이 바뀌면 갱신 필요.
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import string
from datetime import datetime, timezone

import websockets

from ..candlestore import CandleStore
from ..config import settings
from ..hub import hub
from ..market import KST, epoch, market_open
from ..series import BY_ID, SeriesDef

_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
_ORIGIN = "https://www.tradingview.com"
_RESOLUTION = "5"
_N_BARS = 300
_FRAME_RE = re.compile(r"~m~(\d+)~m~")


def _tok(prefix: str) -> str:
    return prefix + "".join(random.choice(string.ascii_lowercase) for _ in range(12))


def _msg(func: str, args: list) -> str:
    body = json.dumps({"m": func, "p": args}, separators=(",", ":"))
    return f"~m~{len(body)}~m~{body}"


def _parse_frames(raw: str):
    i = 0
    while i < len(raw):
        m = _FRAME_RE.match(raw, i)
        if not m:
            return
        length = int(m.group(1))
        start = m.end()
        chunk = raw[start:start + length]
        i = start + length
        if chunk.startswith("~h~"):
            yield ("hb", chunk)
        else:
            try:
                yield ("msg", json.loads(chunk))
            except json.JSONDecodeError:
                pass


def _bucket(epoch_sec: int) -> int:
    # 9차: 여기서 day_open(09:00 KST) 이전을 잘라내면 CandleStore 의 global 롤링
    # 윈도우가 무의미해진다 — 왼쪽 경계는 CandleStore.set_ohlc/series 에서만 적용한다.
    dt = datetime.fromtimestamp(epoch_sec, timezone.utc).astimezone(KST)
    m = dt.minute - (dt.minute % 5)
    return epoch(dt.replace(minute=m, second=0, microsecond=0))


class TradingViewStream:
    def __init__(self, series_ids: list[str]) -> None:
        self.defs: dict[str, SeriesDef] = {sid: BY_ID[sid] for sid in series_ids}
        self.stores = {sid: CandleStore(d.decimals, d.market_key) for sid, d in self.defs.items()}
        self.change_pct: dict[str, float] = {}
        self.last_price: dict[str, float] = {}

    async def run(self) -> None:
        while True:
            try:
                await self._session()
            except Exception as e:  # noqa: BLE001
                print(f"[tradingview] 세션 종료: {e} — {settings.tv_reconnect_sec}s 후 재연결")
            await asyncio.sleep(settings.tv_reconnect_sec)

    async def _session(self) -> None:
        qs = _tok("qs_")
        # 게스트 chart 세션은 series 1개 제한 → 심볼마다 별도 chart 세션(연결은 1개)
        chart_sess = {sid: _tok("cs_") for sid in self.defs}
        cs_to_sid = {v: k for k, v in chart_sess.items()}

        async with websockets.connect(_WS_URL, origin=_ORIGIN, open_timeout=10, close_timeout=5,
                                      ping_interval=None, max_size=8 * 1024 * 1024) as ws:
            async def send(func: str, args: list) -> None:
                await ws.send(_msg(func, args))

            await send("set_auth_token", ["unauthorized_user_token"])
            await send("quote_create_session", [qs])
            await send("quote_set_fields", [qs, "lp", "ch", "chp"])

            symbols = {sid: settings.tv_symbol(sid) for sid in self.defs}
            await send("quote_add_symbols", [qs] + list(symbols.values()))
            for sid, cs in chart_sess.items():
                await send("chart_create_session", [cs, ""])
                await send("resolve_symbol", [cs, "sym_1",
                                              '={"symbol":"%s","adjustment":"splits"}' % symbols[sid]])
                await send("create_series", [cs, "sds_1", "s1", "sym_1", _RESOLUTION, _N_BARS, ""])

            publisher = asyncio.create_task(self._publish_loop())
            try:
                async for raw in ws:
                    for kind, frame in _parse_frames(raw):
                        if kind == "hb":
                            await ws.send(f"~m~{len(frame)}~m~{frame}")
                        else:
                            self._on_message(frame, symbols, cs_to_sid)
            finally:
                publisher.cancel()

    # ── 메시지 처리 ─────────────────────────────
    def _on_message(self, fr: dict, symbols: dict[str, str], cs_to_sid: dict[str, str]) -> None:
        m = fr.get("m")
        p = fr.get("p", [])
        if m in ("timescale_update", "du"):
            sid = cs_to_sid.get(p[0]) if p else None
            node = p[1].get("sds_1") if len(p) > 1 and isinstance(p[1], dict) else None
            if sid and isinstance(node, dict):
                rows = []
                for row in node.get("s", []):
                    v = row.get("v")
                    if not v or len(v) < 5:
                        continue
                    bt = _bucket(int(v[0]))
                    rows.append({"t": bt, "o": v[1], "h": v[2], "l": v[3], "c": v[4]})
                if rows:
                    self.stores[sid].set_ohlc(rows)
        elif m == "qsd":
            data = p[1] if len(p) > 1 and isinstance(p[1], dict) else {}
            name = data.get("n")
            vals = data.get("v", {})
            sid = next((s for s, sym in symbols.items() if sym == name), None)
            if not sid:
                return
            lp = vals.get("lp")
            if isinstance(lp, (int, float)):
                self.last_price[sid] = float(lp)
                if market_open(self.defs[sid].market_key):
                    self.stores[sid].tick(float(lp))
            chp = vals.get("chp")
            if isinstance(chp, (int, float)):
                self.change_pct[sid] = round(float(chp), 2)

    # ── 주기적 발행 ─────────────────────────────
    async def _publish_loop(self) -> None:
        while True:
            for sid, d in self.defs.items():
                store = self.stores[sid]
                if not store.has_data():
                    continue
                is_open = market_open(d.market_key)
                bars = store.fill_to_now(flat=not is_open)
                lp = self.last_price.get(sid)
                price = round(lp, d.decimals) if lp is not None else (bars[-1]["c"] if bars else None)
                payload = {
                    "label": d.label, "unit": d.unit, "decimals": d.decimals,
                    "bars": bars, "price": price,
                }
                if sid in self.change_pct:
                    payload["change_pct"] = self.change_pct[sid]
                await hub.publish(sid, "candles", payload, market_key=d.market_key)
            await asyncio.sleep(2)
