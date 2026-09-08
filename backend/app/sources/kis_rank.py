"""국내주식 랭킹 — 시가총액 상위(히트맵용) + 거래대금 상위(우측 패널용).

- 두 TR 모두 KIS 스펙상 한 번 호출에 **최대 30건**만 오고 다음 페이지 조회가 안 된다(공식 문서 명시).
  스펙은 1~50위까지를 원하지만, 30건 이상을 채우려면 HTS(eFriend Plus)에 조건을 미리 등록해야 하는
  "종목조건검색" API라는 별도 트랙이 필요해서, 1차는 30건으로 시작한다.
- "검색 상위종목"에 대응하는 TR은 KIS Open API에 없다(실시간 검색어/조회수 순위 개념 자체가 없음).
  가장 가까운 건 "관심종목등록 상위"(HTS 관심종목 등록 건수 순위)지만 이것도 "검색"과는 다른 개념이라
  1차에서는 구현하지 않고 거래대금 상위만 다룬다.
- 히트맵은 섹터(업종)별로 묶어야 하는데 랭킹 응답엔 업종코드가 없어서, 종목별로 주식기본조회
  (search-stock-info) TR을 추가로 호출해 업종 대분류명을 가져온다. 업종은 사실상 고정값이라
  종목코드별로 한 번만 조회하고 캐시해서, 이후 폴링에서는 새로 순위권에 든 종목만 추가 조회한다.
- 거래대금 상위 목록의 스파크라인(장중 가격 변동 선차트)은 종목별로 분봉 TR을 또 부르는 대신,
  이 폴링 자체가 매번 찍는 가격을 종목코드별로 누적해서 만든다(추가 호출 없이 가볍게).
"""
from __future__ import annotations

import asyncio
from collections import deque

from ..config import settings
from ..hub import hub
from .kis_client import client

_TR_MARKET_CAP = "FHPST01740000"
_TR_VOLUME_RANK = "FHPST01710000"
_TR_STOCK_INFO = "CTPF1002R"

_SPARK_MAXLEN = 60  # poll_rank_sec(기본 20s) 기준 약 20분 분량


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _signed_pct(ctrt, sign) -> float | None:
    """전일 대비율 + 부호(1상한 2상승 3보합 4하한 5하락) → ±%."""
    try:
        p = abs(float(ctrt))
    except (TypeError, ValueError):
        return None
    return -p if str(sign) in ("4", "5") else p


class KISRanking:
    def __init__(self) -> None:
        self._sector_cache: dict[str, str] = {}  # 종목코드 -> 업종 대분류명
        self._sector_warned: set[str] = set()
        self._spark: dict[str, deque[float]] = {}
        self._warned = {"cap": False, "value": False}

    async def _sector_of(self, code: str) -> str:
        if code in self._sector_cache:
            return self._sector_cache[code]
        body = await client.get(_TR_STOCK_INFO, "/uapi/domestic-stock/v1/quotations/search-stock-info", {
            "PRDT_TYPE_CD": "300", "PDNO": code,
        })
        if body.get("rt_cd") != "0":
            # 호출 실패(레이트리밋 등)는 캐시하지 않는다 — 다음 폴링 때 다시 시도해야 하므로.
            if code not in self._sector_warned:
                self._sector_warned.add(code)
                print(f"[kis-rank] 업종 조회 실패({code}): {body.get('msg1')}")
            return "기타"
        out = body.get("output") or {}
        # idx_bztp_lcls_cd_name 은 이름과 달리 실제로는 "시가총액규모대/중/소"(사이즈 등급)를
        # 반환한다(실측 확인) — 진짜 업종은 mcls(중분류)에 있음. mcls 가 비어있는 종목(주로
        # 최근 상장/지주사 등)은 scls(소분류)로 폴백, 그마저 없으면 "기타"로 묶는다.
        name = (out.get("idx_bztp_mcls_cd_name") or out.get("idx_bztp_scls_cd_name") or "").strip() or "기타"
        self._sector_cache[code] = name
        return name

    async def _market_cap(self) -> list[dict]:
        body = await client.get(_TR_MARKET_CAP, "/uapi/domestic-stock/v1/ranking/market-cap", {
            "fid_input_price_2": "", "fid_cond_mrkt_div_code": "J", "fid_cond_scr_div_code": "20174",
            "fid_div_cls_code": "0", "fid_input_iscd": "0000", "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0", "fid_input_price_1": "", "fid_vol_cnt": "",
        })
        if body.get("rt_cd") != "0":
            if not self._warned["cap"]:
                self._warned["cap"] = True
                print(f"[kis-rank] 시가총액 상위: {body.get('msg1')}")
            return []
        rows = []
        for o in body.get("output") or []:
            rows.append({
                "rank": int(_num(o.get("data_rank"))),
                "code": o.get("mksc_shrn_iscd", ""),
                "name": o.get("hts_kor_isnm", ""),
                "price": _num(o.get("stck_prpr")),
                "change_pct": _signed_pct(o.get("prdy_ctrt"), o.get("prdy_vrss_sign")),
                "market_cap_eok": _num(o.get("stck_avls")),  # 이미 억원 단위(KIS 응답 실측 확인)
            })
        return rows

    async def _value_rank(self) -> list[dict]:
        body = await client.get(_TR_VOLUME_RANK, "/uapi/domestic-stock/v1/quotations/volume-rank", {
            "FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171", "FID_INPUT_ISCD": "0000",
            "FID_DIV_CLS_CODE": "0", "FID_BLNG_CLS_CODE": "3",  # 3: 거래금액순
            "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "0000000000",
            "FID_INPUT_PRICE_1": "", "FID_INPUT_PRICE_2": "", "FID_VOL_CNT": "",
        })
        if body.get("rt_cd") != "0":
            if not self._warned["value"]:
                self._warned["value"] = True
                print(f"[kis-rank] 거래대금 상위: {body.get('msg1')}")
            return []
        rows = []
        for o in body.get("output") or []:
            code = o.get("mksc_shrn_iscd", "")
            price = _num(o.get("stck_prpr"))
            spark = self._spark.setdefault(code, deque(maxlen=_SPARK_MAXLEN))
            if price:
                spark.append(price)
            rows.append({
                "rank": int(_num(o.get("data_rank"))),
                "code": code,
                "name": o.get("hts_kor_isnm", ""),
                "price": price,
                "change_pct": _signed_pct(o.get("prdy_ctrt"), o.get("prdy_vrss_sign")),
                "trade_value_eok": round(_num(o.get("acml_tr_pbmn")) / 1e8, 1),  # 원 -> 억원
                "market_cap_eok": round(price * _num(o.get("lstn_stcn")) / 1e8, 1),  # 시총 TR엔 없어 근사
                "spark": list(spark),
            })
        return rows

    async def run(self) -> None:
        # 랭킹 TR은 장 마감 중에도 마지막 세션 값을 그대로 응답해주므로 개장 여부와 무관하게 계속 폴링한다.
        # (hub 의 초록/회색 표시는 market_key="kr_regular" 기준으로 알아서 처리됨.)
        while True:
            cap_rows = await self._market_cap()
            if cap_rows:
                for r in cap_rows:
                    r["sector"] = await self._sector_of(r["code"])
                await hub.publish("kospi_heatmap", "heatmap", {
                    "label": "코스피 히트맵(시총 상위 30)", "rows": cap_rows,
                }, market_key="kr_regular")

            value_rows = await self._value_rank()
            if value_rows:
                await hub.publish("value_rank", "ranking", {
                    "label": "거래대금 상위", "rows": value_rows,
                }, market_key="kr_regular")

            await asyncio.sleep(settings.poll_rank_sec)
