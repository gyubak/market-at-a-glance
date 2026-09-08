"""FastAPI 진입점 — REST 스냅샷 + WebSocket 스트림. (mock 없음)"""
from __future__ import annotations

import asyncio
import contextlib

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .hub import hub
from .market import now_kst
from .series import LEFT, TOP

_tasks: list[asyncio.Task] = []


def _build_sources():
    srcs = []

    # 해외 5종: series 별 소스(tv|yahoo)에 따라 그룹화
    tv_ids = [d.id for d in LEFT if settings.overseas_source(d.id) == "tv"]
    yahoo_ids = [d for d in LEFT if settings.overseas_source(d.id) == "yahoo"]
    if tv_ids:
        from .sources.tradingview import TradingViewStream
        srcs.append((f"overseas=tv({','.join(tv_ids)})", TradingViewStream(tv_ids)))
    if yahoo_ids:
        from .sources.yahoo import YahooCandles
        srcs.append((f"overseas=yahoo({','.join(d.id for d in yahoo_ids)})", YahooCandles(yahoo_ids)))

    if settings.has_kis:
        from .sources.kis import KISCandles, KISFlow
        from .sources.kis_rank import KISRanking
        srcs.append(("domestic=kis", KISCandles(TOP)))
        srcs.append(("flow=kis", KISFlow()))
        srcs.append(("rank=kis", KISRanking()))
    else:
        print("[dashboard] KIS 키 없음 — 코스피/코스닥/국채/투자자매매동향 미표시")

    return srcs


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[dashboard] KST now={now_kst():%Y-%m-%d %H:%M:%S}")
    for name, src in _build_sources():
        print(f"[dashboard] source: {name}")
        _tasks.append(asyncio.create_task(src.run()))
    _tasks.append(asyncio.create_task(hub.watch_lights()))
    try:
        yield
    finally:
        for t in _tasks:
            t.cancel()
        await asyncio.gather(*_tasks, return_exceptions=True)
        with contextlib.suppress(Exception):
            from .sources.kis_client import client
            await client.aclose()


app = FastAPI(title="주식 dashboard", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
async def health():
    return {"now": now_kst().isoformat(), "kis": settings.has_kis}


@app.get("/api/snapshot")
async def snapshot():
    return hub.snapshot()


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    q = hub.connect()
    try:
        await sock.send_json(hub.snapshot())
        while True:
            await sock.send_json(await q.get())
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        hub.disconnect(q)
