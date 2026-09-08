"""환경변수 로딩. .env 가 없으면 KIS/야후 관련만 비활성(해당 소스 미표시)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _b(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _i(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# 해외 5종 기본 소스/심볼.
# - tv : TradingView 비공식 소켓(실시간에 가까움). CFD/지수/TVC 심볼.
# - yahoo : yfinance (선물은 ~10분 지연, 환율은 거의 실시간)
_OVERSEAS_SOURCE_DEFAULT = {
    "nasdaq_fut": "tv",
    "wti": "tv",
    "dxy": "tv",
    "usdkrw": "yahoo",
    "ust2y": "tv",
}
_TV_SYMBOL_DEFAULT = {
    # 나스닥은 TVC:NDX(지수)가 미국 정규장에만 프린트되어 야간이 비므로 24h CFD 사용
    "nasdaq_fut": "OANDA:NAS100USD",
    "wti": "TVC:USOIL",
    "dxy": "TVC:DXY",
    "usdkrw": "FX_IDC:USDKRW",
    "ust2y": "TVC:US02Y",
}
_YAHOO_TICKER_DEFAULT = {
    "nasdaq_fut": "NQ=F",
    "wti": "CL=F",
    "dxy": "DX-Y.NYB",
    "usdkrw": "KRW=X",
}


@dataclass
class Settings:
    kis_app_key: str = field(default_factory=lambda: _b("KIS_APP_KEY", ""))
    kis_app_secret: str = field(default_factory=lambda: _b("KIS_APP_SECRET", ""))
    kis_rest_base: str = field(default_factory=lambda: _b("KIS_REST_BASE", "https://openapi.koreainvestment.com:9443"))
    kis_custtype: str = field(default_factory=lambda: _b("KIS_CUSTTYPE", "P"))
    kis_min_interval_sec: float = field(default_factory=lambda: _f("KIS_MIN_INTERVAL_SEC", 0.45))
    kis_flow_unit_div: float = field(default_factory=lambda: _f("KIS_FLOW_UNIT_DIV", 100.0))

    kis_kospi_fut_code: str = field(default_factory=lambda: _b("KIS_KOSPI_FUT_CODE", ""))
    kis_kosdaq_fut_code: str = field(default_factory=lambda: _b("KIS_KOSDAQ_FUT_CODE", ""))
    kis_ktb3y_code: str = field(default_factory=lambda: _b("KIS_KTB3Y_CODE", ""))

    host: str = field(default_factory=lambda: _b("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _i("PORT", 8000))
    poll_yahoo_sec: int = field(default_factory=lambda: _i("POLL_YAHOO_SEC", 6))
    poll_domestic_sec: int = field(default_factory=lambda: _i("POLL_DOMESTIC_SEC", 5))
    poll_rank_sec: int = field(default_factory=lambda: _i("POLL_RANK_SEC", 20))
    stale_after_sec: int = field(default_factory=lambda: _i("STALE_AFTER_SEC", 10))
    tv_reconnect_sec: int = field(default_factory=lambda: _i("TV_RECONNECT_SEC", 5))

    def overseas_source(self, series_id: str) -> str:
        return _b(f"SOURCE_{series_id.upper()}", _OVERSEAS_SOURCE_DEFAULT.get(series_id, "yahoo"))

    def tv_symbol(self, series_id: str) -> str:
        return _b(f"TV_SYMBOL_{series_id.upper()}", _TV_SYMBOL_DEFAULT.get(series_id, ""))

    def yahoo_ticker(self, series_id: str) -> str:
        return _b(f"YAHOO_TICKER_{series_id.upper()}", _YAHOO_TICKER_DEFAULT.get(series_id, ""))

    @property
    def has_kis(self) -> bool:
        return bool(self.kis_app_key and self.kis_app_secret)


settings = Settings()
