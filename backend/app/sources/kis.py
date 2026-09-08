"""한국투자증권(KIS) REST 소스 — 코스피/코스닥, 국고채 3년, 투자자매매동향.

- 조회 TR 은 실전(실계좌) 도메인 전용. mock 폴백 없음 — 실패 시 종가 유지 + 빨간불.
- 코스피/코스닥: 근월물 코드(.env)가 있으면 지수선물(FHKIF03020200), 없으면 업종 지수 분봉(FHKUP03500200).
- 국고채 3년: 금리 종합(HHPST070200C0, DATA_GB=3 장내국고채) 스냅샷을 5분 버킷에 누적.
- 투자자매매동향: FHPTJ04030000 '현재 누적' 스냅샷을 5분 버킷에 누적.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

from ..candlestore import CandleStore, rows_to_5m
from ..config import settings
from ..hub import hub
from ..market import KR_FUT_OPEN, epoch, market_open, now_kst, session_bar_times
from ..series import FLOW_ID, TOP, SeriesDef
from .kis_client import client

_TR_INDEX_MIN = "FHKUP03500200"     # 업종 지수 분봉 (OHLC)
_TR_FUT_MIN = "FHKIF03020200"       # 선물옵션 분봉
_TR_INVESTOR = "FHPTJ04030000"      # 시장별 투자자매매동향(시세) — 스냅샷
_TR_INTEREST = "HHPST070200C0"      # 금리 종합 — 스냅샷

_INDEX_ISCD = {"kospi_fut": "0001", "kosdaq_fut": "1001"}
_FUT_CODE = {"kospi_fut": lambda: settings.kis_kospi_fut_code,
             "kosdaq_fut": lambda: settings.kis_kosdaq_fut_code}

_INST_FIELDS = {
    "institution_sum": "orgn_ntby_tr_pbmn",
    "financial_invest": "scrt_ntby_tr_pbmn",
    "investment_trust": "ivtr_ntby_tr_pbmn",
    "pension": "fund_ntby_tr_pbmn",
    "private_fund": "pe_fund_ntby_tr_pbmn",
    "other_corp": "etc_corp_ntby_tr_pbmn",
}


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


def _hhmm_to_epoch(hhmmss: str) -> int | None:
    """HHMMSS → epoch(과거 시각). 999999/888888 등 센티넬은 None.
    야간선물은 18~28시(예: 253000=01:30)로 표기 → 미래로 계산되면 하루씩 당김."""
    if len(hhmmss) < 4 or not hhmmss[:4].isdigit():
        return None
    hh, mm = int(hhmmss[:2]), int(hhmmss[2:4])
    if mm > 59 or hh > 29:
        return None
    now = now_kst()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    dt = midnight + timedelta(minutes=hh * 60 + mm)
    while dt > now + timedelta(hours=1):
        dt -= timedelta(days=1)
    return epoch(dt)


class KISCandles:
    def __init__(self, defs: list[SeriesDef] | None = None) -> None:
        self.defs = defs or TOP
        self.stores = {d.id: CandleStore(d.decimals, d.market_key) for d in self.defs}
        self._warned: set[str] = set()

    def _warn(self, sid: str, msg: str) -> None:
        if sid not in self._warned:
            self._warned.add(sid)
            print(f"[kis] {sid}: {msg}")

    async def _index_ohlc(self, iscd: str) -> tuple[list[dict], float | None]:
        body = await client.get(_TR_INDEX_MIN, "/uapi/domestic-stock/v1/quotations/inquire-time-indexchartprice", {
            "FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": iscd,
            "FID_INPUT_HOUR_1": "60", "FID_PW_DATA_INCU_YN": "Y", "FID_ETC_CLS_CODE": "0",
        })
        if body.get("rt_cd") != "0":
            raise RuntimeError(body.get("msg1", "err"))
        o1 = body.get("output1") or {}
        raw = []
        for row in body.get("output2", []):
            t = _hhmm_to_epoch(row.get("stck_cntg_hour", ""))
            if t is None:
                continue
            raw.append({"t": t, "o": row["bstp_nmix_oprc"], "h": row["bstp_nmix_hgpr"],
                        "l": row["bstp_nmix_lwpr"], "c": row["bstp_nmix_prpr"]})
        pct = _signed_pct(o1.get("bstp_nmix_prdy_ctrt"), o1.get("prdy_vrss_sign"))
        return rows_to_5m(raw, t="t", o="o", h="h", l="l", c="c"), pct

    async def _fut_ohlc(self, code: str, mkt: str = "F") -> tuple[list[dict], float | None]:
        now = now_kst()
        hhmmss = now.strftime("%H%M%S")
        if mkt == "CM" and now.hour < 8:  # 야간선물 자정 이후는 24~29시로 입력
            hhmmss = f"{now.hour + 24:02d}{now.strftime('%M%S')}"
        body = await client.get(_TR_FUT_MIN, "/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice", {
            "FID_COND_MRKT_DIV_CODE": mkt, "FID_INPUT_ISCD": code, "FID_HOUR_CLS_CODE": "60",
            "FID_PW_DATA_INCU_YN": "N", "FID_FAKE_TICK_INCU_YN": "N",
            "FID_INPUT_DATE_1": now.strftime("%Y%m%d"), "FID_INPUT_HOUR_1": hhmmss,
        })
        if body.get("rt_cd") != "0":
            raise RuntimeError(body.get("msg1", "err"))
        rows = body.get("output2") or []
        if not rows:
            raise RuntimeError(f"빈 응답(종목코드 {code} 확인 필요)")
        o1 = body.get("output1") or {}
        raw = []
        for row in rows:
            t = _hhmm_to_epoch(row.get("stck_cntg_hour", ""))
            if t is None:
                continue
            raw.append({"t": t, "o": row["futs_oprc"], "h": row["futs_hgpr"],
                        "l": row["futs_lwpr"], "c": row["futs_prpr"]})
        pct = _signed_pct(o1.get("futs_prdy_ctrt"), o1.get("prdy_vrss_sign"))
        return rows_to_5m(raw, t="t", o="o", h="h", l="l", c="c"), pct

    async def _ktb3y_tick(self) -> tuple[float | None, float | None]:
        body = await client.get(_TR_INTEREST, "/uapi/domestic-stock/v1/quotations/comp-interest", {
            "FID_COND_MRKT_DIV_CODE": "I", "FID_COND_SCR_DIV_CODE": "20702",
            "FID_DIV_CLS_CODE": "0", "FID_DIV_CLS_CODE1": "1", "DATA_GB": "3",
        })
        if body.get("rt_cd") != "0":
            raise RuntimeError(body.get("msg1", "err"))
        for row in body.get("output1", []):
            if (row.get("indicator_nm") or "").replace(" ", "") == "국고채3년":
                y = _num(row.get("bond_cntg_ert") or row.get("bond_mnrt_prpr"))
                pct = _signed_pct(row.get("prdy_ctrt"), row.get("prdy_vrss_sign"))
                return y or None, pct
        return None, None

    async def _one(self, d: SeriesDef) -> None:
        store = self.stores[d.id]
        label = d.label
        market_key = d.market_key
        change_pct: float | None = None
        try:
            if d.id in _INDEX_ISCD:
                code = _FUT_CODE[d.id]()
                if code:
                    market_key = "kr_futures"
                    now = now_kst()
                    fut_open_min = KR_FUT_OPEN[0] * 60 + KR_FUT_OPEN[1]
                    day_sess = now.weekday() < 5 and (fut_open_min <= now.hour * 60 + now.minute < 15 * 60 + 45)
                    label = ("코스피 선물" if d.id == "kospi_fut" else "코스닥 선물") + ("" if day_sess else "(야간)")
                    bars, change_pct = await self._fut_ohlc(code, "F" if day_sess else "CM")
                else:
                    bars, change_pct = await self._index_ohlc(_INDEX_ISCD[d.id])
                store.set_ohlc(bars)
            elif d.id == "ktb3y":
                y, change_pct = await self._ktb3y_tick()
                if y is not None:
                    store.tick(y)
            else:
                return
        except Exception as e:  # noqa: BLE001
            self._warn(d.id, str(e))

        if not store.has_data():
            return await self._publish_unavailable(d, label, market_key)
        out = store.fill_to_now(flat=not market_open(market_key))
        payload = {
            "label": label, "unit": d.unit, "decimals": d.decimals,
            "bars": out, "price": out[-1]["c"] if out else None,
        }
        if change_pct is not None:
            payload["change_pct"] = change_pct
        await hub.publish(d.id, "candles", payload, market_key=market_key)

    async def _publish_unavailable(self, d: SeriesDef, label: str, market_key: str) -> None:
        await hub.publish(d.id, "candles", {
            "label": label, "unit": d.unit, "decimals": d.decimals,
            "bars": [], "price": None, "unavailable": True,
        }, market_key=market_key)

    async def run(self) -> None:
        while True:
            for d in self.defs:
                await self._one(d)
            await asyncio.sleep(settings.poll_domestic_sec)


class KISFlow:
    """FHPTJ04030000 스냅샷을 5분 버킷에 누적."""

    def __init__(self) -> None:
        self.bars: dict[int, dict] = {}
        self.inst_bars: dict[int, dict] = {}
        self._warned = False

    async def run(self) -> None:
        div = settings.kis_flow_unit_div or 1.0
        while True:
            body = await client.get(_TR_INVESTOR, "/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market", {
                "fid_input_iscd": "KSP", "fid_input_iscd_2": "0001",
            })
            rows = body.get("output") or []
            if body.get("rt_cd") == "0" and rows and market_open("kr_regular"):
                o = rows[0]
                n = now_kst()
                bt = epoch(n.replace(minute=n.minute - n.minute % 5, second=0, microsecond=0))
                self.bars[bt] = {
                    "individual": round(_num(o.get("prsn_ntby_tr_pbmn")) / div, 1),
                    "foreign": round(_num(o.get("frgn_ntby_tr_pbmn")) / div, 1),
                    "institution": round(_num(o.get("orgn_ntby_tr_pbmn")) / div, 1),
                }
                self.inst_bars[bt] = {k: round(_num(o.get(f)) / div, 1) for k, f in _INST_FIELDS.items()}
            elif body.get("rt_cd") != "0" and not self._warned:
                self._warned = True
                print(f"[kis] 투자자매매동향: {body.get('msg1')}")
            await self._publish()
            await asyncio.sleep(settings.poll_domestic_sec)

    async def _publish(self) -> None:
        times = [epoch(t) for t in session_bar_times()]
        bars = [{"t": t, **self.bars[t]} for t in times if t in self.bars]
        cur = bars[-1] if bars else {"individual": 0.0, "foreign": 0.0, "institution": 0.0}
        last_inst = None
        for t in reversed(times):
            if t in self.inst_bars:
                last_inst = self.inst_bars[t]
                break
        await hub.publish(FLOW_ID, "flow", {
            "label": "투자자별 매매동향",
            "bars": bars,
            "current": {k: cur.get(k, 0.0) for k in ("individual", "foreign", "institution")},
            "institution_detail": last_inst or {k: 0.0 for k in _INST_FIELDS},
            "foreign_detail": None,  # 외국증권사 Top-5: 회원사 TR 연동 예정 (2차)
            "unavailable": not bars,  # 장 시작 후 서버를 켠 경우 등
        }, market_key="kr_regular")
