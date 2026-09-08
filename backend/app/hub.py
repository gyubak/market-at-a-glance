"""인메모리 상태 + WebSocket 브로드캐스트. DB 없음(스펙 3.2.2)."""
from __future__ import annotations

import asyncio
import time
from typing import Any

from .config import settings
from .market import market_open


class Hub:
    def __init__(self) -> None:
        self._clients: set[asyncio.Queue] = set()
        self._series: dict[str, dict[str, Any]] = {}
        self._updated: dict[str, float] = {}
        self._market_key: dict[str, str] = {}

    # ── 구독 ────────────────────────────────────────
    def connect(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._clients.add(q)
        return q

    def disconnect(self, q: asyncio.Queue) -> None:
        self._clients.discard(q)

    def _light(self, sid: str) -> str:
        """green: 개장+수신, red: 개장+미수신, gray: 폐장."""
        if not market_open(self._market_key.get(sid, "global")):
            return "gray"
        fresh = (time.time() - self._updated.get(sid, 0)) <= settings.stale_after_sec
        return "green" if fresh else "red"

    def snapshot(self) -> dict[str, Any]:
        return {
            "type": "snapshot",
            "series": {sid: {**data, "light": self._light(sid)} for sid, data in self._series.items()},
            "ts": int(time.time()),
        }

    # ── 발행 ────────────────────────────────────────
    async def publish(self, series_id: str, kind: str, data: dict[str, Any], *, market_key: str = "global") -> None:
        self._series[series_id] = {"kind": kind, **data}
        self._updated[series_id] = time.time()
        self._market_key[series_id] = market_key
        await self._fanout({"type": "update", "id": series_id, "kind": kind, "light": self._light(series_id), **data})

    async def _fanout(self, msg: dict[str, Any]) -> None:
        for q in list(self._clients):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                self._clients.discard(q)

    # ── light 감시 (시간 경과로도 상태가 바뀜) ─────────
    async def watch_lights(self) -> None:
        prev: dict[str, str] = {}
        while True:
            for sid in list(self._series):
                lt = self._light(sid)
                if prev.get(sid) != lt:
                    prev[sid] = lt
                    await self._fanout({"type": "light", "id": sid, "light": lt})
            await asyncio.sleep(2)


hub = Hub()
