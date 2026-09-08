"""KST 시간 그리드 + 시장 개장 상태.

스펙 피드백: 시간축은 한국 정규장이 끝나도 계속 흐른다.
- 데이터가 계속 들어오는 상품(해외 선물/환율/미국채, NXT 등)은 그대로 갱신
- 닫힌 상품은 마지막 종가를 유지한 채로 봉만 오른쪽으로 밀려남
불빛: 개장+데이터수신=green, 개장+미수신=red, 폐장=gray
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
BAR_SEC = 300
SESSION_OPEN = (9, 0)
KR_FUT_OPEN = (8, 45)         # 9차: 선물 정규장은 09:00보다 앞서 열림
KR_REGULAR_CLOSE = (15, 40)   # 정규장(+시간외 단일가 여유)


def now_kst() -> datetime:
    return datetime.now(KST)


def day_open(ref: datetime | None = None, market_key: str = "kr_regular") -> datetime:
    """가장 최근의 장 시작 시각(= 그 거래일의 시작). 자정을 넘겨도 세션이 이어진다.
    kr_futures 는 08:45, 그 외(kr_regular 등)는 09:00 기준."""
    ref = ref or now_kst()
    h, m = KR_FUT_OPEN if market_key == "kr_futures" else SESSION_OPEN
    o = ref.replace(hour=h, minute=m, second=0, microsecond=0)
    if ref < o:
        o -= timedelta(days=1)
    return o


def bucket_start(dt: datetime) -> datetime:
    return dt.replace(minute=dt.minute - (dt.minute % 5), second=0, microsecond=0)


def current_bar_time(ref: datetime | None = None) -> datetime:
    """가장 우측 봉 시각. freeze 없음 — 항상 현재 5분 버킷."""
    return bucket_start(ref or now_kst())


def session_bar_times(ref: datetime | None = None) -> list[datetime]:
    """직전 09:00 부터 현재 버킷까지의 모든 5분봉 시각."""
    ref = ref or now_kst()
    t = day_open(ref)
    last = current_bar_time(ref)
    out: list[datetime] = []
    while t <= last:
        out.append(t)
        t += timedelta(seconds=BAR_SEC)
    return out


def epoch(dt: datetime) -> int:
    return int(dt.timestamp())


# ── 시장 개장 상태 ────────────────────────────────
def _is_weekend(dt: datetime) -> bool:
    return dt.weekday() >= 5  # 5=토, 6=일 (공휴일 캘린더는 미반영)


def market_open(market_key: str, ref: datetime | None = None) -> bool:
    """market_key 별 현재 개장 여부."""
    dt = (ref or now_kst()).astimezone(KST)
    if market_key == "global":
        # 해외 선물/환율/미국채: 대략 24x5. 주말만 폐장으로 간주(주 경계는 근사).
        return not _is_weekend(dt)
    if market_key == "kr_regular":
        if _is_weekend(dt):
            return False
        mins = dt.hour * 60 + dt.minute
        return SESSION_OPEN[0] * 60 <= mins < KR_REGULAR_CLOSE[0] * 60 + KR_REGULAR_CLOSE[1]
    if market_key == "kr_futures":
        # 주간 08:45~15:45 + 야간 18:00~익일 05:00 (근사)
        mins = dt.hour * 60 + dt.minute
        day = (not _is_weekend(dt)) and KR_FUT_OPEN[0] * 60 + KR_FUT_OPEN[1] <= mins < 15 * 60 + 45
        night = (dt.weekday() <= 4 and mins >= 18 * 60) or (dt.weekday() in (1, 2, 3, 4) and mins < 5 * 60)
        return day or night
    return True
