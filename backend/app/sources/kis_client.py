"""KIS REST 공용 클라이언트: 토큰 디스크 캐시 + 초당 호출 throttle.

- 토큰 발급은 KIS 가 분당 1회로 제한하므로 `.kis_token.json` 에 캐시해서
  서버 재시작 시 재발급을 피한다.
- 모든 호출은 KIS_MIN_INTERVAL_SEC 간격을 두고 직렬화한다(초당 거래건수 초과 방지).
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx

from ..config import settings

_TOKEN_FILE = Path(__file__).resolve().parent.parent.parent / ".kis_token.json"


class KisClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=15)
        self._lock = asyncio.Lock()          # 호출 직렬화
        self._last_call = 0.0
        self._token: str | None = None
        self._token_exp = 0.0
        self._load_token()

    def _load_token(self) -> None:
        try:
            d = json.loads(_TOKEN_FILE.read_text())
            if d.get("key_head") == settings.kis_app_key[:6] and time.time() < d["exp"] - 300:
                self._token = d["token"]
                self._token_exp = d["exp"]
        except Exception:
            pass

    def _save_token(self) -> None:
        try:
            _TOKEN_FILE.write_text(json.dumps({
                "key_head": settings.kis_app_key[:6],
                "token": self._token,
                "exp": self._token_exp,
            }))
            _TOKEN_FILE.chmod(0o600)
        except Exception:
            pass

    async def _ensure_token(self) -> str | None:
        if self._token and time.time() < self._token_exp - 300:
            return self._token
        try:
            r = await self._client.post(
                f"{settings.kis_rest_base}/oauth2/tokenP",
                json={
                    "grant_type": "client_credentials",
                    "appkey": settings.kis_app_key,
                    "appsecret": settings.kis_app_secret,
                },
            )
            r.raise_for_status()
            d = r.json()
            self._token = d["access_token"]
            self._token_exp = time.time() + int(d.get("expires_in", 86400))
            self._save_token()
            return self._token
        except Exception as e:  # noqa: BLE001
            print(f"[kis] 토큰 발급 실패(분당 1회 제한일 수 있음): {e}")
            return None

    async def get(self, tr_id: str, url_path: str, params: dict, *, retry: int = 1) -> dict:
        token = await self._ensure_token()
        if not token:
            return {"rt_cd": "9", "msg1": "no token"}
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": settings.kis_app_key,
            "appsecret": settings.kis_app_secret,
            "tr_id": tr_id,
            "custtype": settings.kis_custtype,
        }
        async with self._lock:
            wait = settings.kis_min_interval_sec - (time.time() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                r = await self._client.get(settings.kis_rest_base + url_path, headers=headers, params=params)
                body = r.json()
            except Exception as e:  # noqa: BLE001
                self._last_call = time.time()
                return {"rt_cd": "9", "msg1": str(e)}
            self._last_call = time.time()
        if "초당" in str(body.get("msg1", "")) and retry > 0:  # 초당 거래건수 초과
            await asyncio.sleep(0.8)
            return await self.get(tr_id, url_path, params, retry=retry - 1)
        return body

    async def aclose(self) -> None:
        await self._client.aclose()


client = KisClient()
