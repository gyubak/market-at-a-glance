"""1차 슬라이스에서 다루는 시계열 정의."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeriesDef:
    id: str
    label: str
    group: str          # "left" | "top" | "flow"
    unit: str           # "price" | "yield" | "won_bil"
    decimals: int
    market_key: str      # market.market_open() 키: "global" | "kr_regular" | "kr_futures"


LEFT: list[SeriesDef] = [
    SeriesDef("nasdaq_fut", "나스닥 선물", "left", "price", 2, "global"),
    SeriesDef("ust2y", "미국채 2년", "left", "yield", 3, "global"),
    SeriesDef("wti", "WTI", "left", "price", 2, "global"),
    SeriesDef("dxy", "달러 인덱스", "left", "price", 3, "global"),
    SeriesDef("usdkrw", "USD / KRW", "left", "price", 2, "global"),
]

TOP: list[SeriesDef] = [
    # kospi_fut/kosdaq_fut: 실제로는 KIS 선물 코드가 설정된 경우 선물(kr_futures, 08:45 개장)로
    # 표시되고, 코드가 없을 때만 지수(kr_regular)로 폴백한다(kis.py:_one). 실사용은 항상 선물이므로
    # 기본 market_key 도 kr_futures 로 맞춰 CandleStore 의 day_open/개장시각 계산이 맞게 함.
    SeriesDef("kospi_fut", "코스피", "top", "price", 2, "kr_futures"),
    SeriesDef("kosdaq_fut", "코스닥", "top", "price", 2, "kr_futures"),
    SeriesDef("ktb3y", "국고채 3년", "top", "yield", 3, "kr_regular"),
]

FLOW_ID = "kospi_flow"
FLOW_INVESTORS = ["individual", "foreign", "institution"]
FLOW_INSTITUTION_BREAKDOWN = [
    "institution_sum", "financial_invest", "investment_trust", "pension", "private_fund", "other_corp",
]

BY_ID = {s.id: s for s in LEFT + TOP}
