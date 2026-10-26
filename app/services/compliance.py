# -*- coding: utf-8 -*-
"""Authority-first compliance supplement pipeline.

Only fields requested by the platform are considered. Every proposed value must
carry a real official source URL, a retrieval timestamp and a verbatim evidence
snippet. Anything that cannot be verified stays ``unsupported`` and is never
replaced by a guess.
"""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..config import DATA_DIR, RESEARCH_DIR, now_iso
from . import au_tariff, declaration

CUSTOMS_QUERY_URL = "https://online.customs.gov.cn/ociswebserver/ocis/taxRateQuery/query/queryImpTariffRate"
CUSTOMS_AGREEMENT_URL = "https://online.customs.gov.cn/ociswebserver/ocis/taxRateQuery/query/queryAgreementRate"
CUSTOMS_COUNTRY_AGREEMENT_URL = "https://online.customs.gov.cn/ociswebserver/ocis/taxRateQuery/query/queryCountryAgreementRate"
CUSTOMS_PAGE_URL = "https://online.customs.gov.cn/ociswebserver/pages/jckspsl/index.html"
CUSTOMS_DETAIL_URL = "https://online.customs.gov.cn/ociswebserver/pages/jckspsl/detail.html"
CUSTOMS_DISCLAIMER = "网上及微信发布的归类及税率信息仅供参考……用户应以实际通关、办理海关手续时相关海关的解释和要求为准。"
ABF_CHINA_URL = "https://www.abf.gov.au/importing-exporting-and-manufacturing/fta/free-trade-agreements/china"
ABF_FTA_URL = "https://www.abf.gov.au/importing-exporting-and-manufacturing/fta"
ABF_GUIDE_PDF_URL = "https://www.abf.gov.au/free-trade-agreements/files/instructions-guidelines-australia-china-fta.pdf"

CACHE_PATH = DATA_DIR / "compliance_cache.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def _cache_get(key: str, ttl_hours: int = 24 * 7) -> Any:
    cache = _load_cache()
    rec = cache.get(key)
    if not rec:
        return None
    try:
        ts = datetime.fromisoformat(rec.get("_ts"))
    except Exception:
        return None
    if datetime.now() - ts > timedelta(hours=ttl_hours):
        return None
    return rec.get("data")


def _cache_put(key: str, data: Any) -> None:
    cache = _load_cache()
    cache[key] = {"_ts": datetime.now().isoformat(timespec="seconds"), "data": data}
    _save_cache(cache)


def _http_post_form(url: str, param: dict, timeout: int = 12) -> tuple[int, str, str | None]:
    body = urllib.parse.urlencode({"param": json.dumps(param, ensure_ascii=False, separators=(",", ":"))}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": CUSTOMS_PAGE_URL,
        "Origin": "https://online.customs.gov.cn",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    })
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, r.read().decode("utf-8", "replace"), None
    except urllib.error.HTTPError as exc:
        return exc.code, "", f"HTTP {exc.code}"
    except Exception as exc:
        return 0, "", f"{type(exc).__name__}: {exc}"


def _http_get(url: str, timeout: int = 15) -> tuple[int, str, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-AU,en;q=0.9,zh-CN;q=0.8"})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            ctype = r.headers.get("Content-Type", "")
            return r.status, r.read().decode("utf-8", "replace") if "text" in ctype or "json" in ctype else "", None
    except urllib.error.HTTPError as exc:
        return exc.code, "", f"HTTP {exc.code}"
    except Exception as exc:
        return 0, "", f"{type(exc).__name__}: {exc}"


def _repair_customs(raw: str) -> dict:
    try:
        outer = json.loads(raw)
    except Exception:
        return {"statue": 0, "message": "响应不是 JSON", "data": []}
    res = outer.get("res", "")
    if isinstance(res, dict):
        return res
    if not isinstance(res, str):
        return {"statue": 0, "message": "响应无 res 字段", "data": []}
    s = res.strip().replace("\r", "").replace("\n", "")
    s = re.sub(r'([{,]\s*)(statue|message|totalCount|data)\s*:', r'\1"\2":', s)
    try:
        return json.loads(s)
    except Exception:
        # best-effort: extract data array
        m = re.search(r'"data"\s*:\s*(\[.*\])\s*}?\s*$', s)
        if m:
            try:
                return {"statue": 1, "data": json.loads(m.group(1))}
            except Exception:
                pass
        return {"statue": 0, "message": "响应解析失败", "data": [], "raw": s[:800]}


def query_tariff(code: str, timeout: int = 12) -> dict:
    """Query official China tariff lines by 4-10 digit code or name."""
    code = re.sub(r"\D", "", str(code or ""))[:10]
    key = f"tariff:{code}:{_today()}"
    cached = _cache_get(key)
    if cached:
        cached = dict(cached)
        cached["cache_hit"] = True
        return cached
    payload = {"gName": "", "codeTs": code, "sysDate": _today(), "nextPage": 1, "pageSize": "80"}
    t0 = time.time()
    status, raw, err = _http_post_form(CUSTOMS_QUERY_URL, payload, timeout=timeout)
    parsed = _repair_customs(raw) if status == 200 else {"statue": 0, "message": err or "网络不可用", "data": []}
    data = [r for r in (parsed.get("data") or []) if isinstance(r, dict) and r.get("codeTs")]
    out = {
        "ok": bool(status == 200 and data),
        "http_status": status,
        "url": CUSTOMS_QUERY_URL,
        "query": payload,
        "rows": data,
        "message": parsed.get("message", ""),
        "error": err,
        "elapsed_ms": int((time.time() - t0) * 1000),
        "retrieved_at": now_iso(),
        "cache_hit": False,
    }
    if data:
        _cache_put(key, out)
    return out


def agreement_rates(code: str, timeout: int = 12) -> dict:
    code = re.sub(r"\D", "", str(code or ""))[:10]
    key = f"agreement:{code}:{_today()}"
    cached = _cache_get(key)
    if cached:
        return dict(cached, cache_hit=True)
    t0 = time.time()
    status, raw, err = _http_post_form(CUSTOMS_AGREEMENT_URL, {"codeTs": code, "sysDate": _today()}, timeout=timeout)
    parsed = _repair_customs(raw) if status == 200 else {"data": []}
    rows = parsed.get("data") or []
    result = {"ok": bool(rows), "rows": rows, "http_status": status, "error": err, "elapsed_ms": int((time.time() - t0) * 1000)}
    if rows:
        _cache_put(key, result)
    return result


def _fallback_hs(entity: str, hs: str = "") -> list[dict]:
    try:
        records = json.loads((RESEARCH_DIR / "evidence.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    en = (entity or "").lower()
    for r in records:
        if r.get("status") != "supported":
            continue
        if r.get("kind") != "hs_code":
            continue
        if hs and str(r.get("hs_code")) == str(hs):
            out.append(r)
        elif en and (en in (r.get("entity") or "").lower() or (r.get("entity") or "").lower() in en):
            out.append(r)
    return out


def _candidate_codes(item: dict) -> list[str]:
    text = f"{item.get('name_en','')} {item.get('name_zh','')} {item.get('material','')} {item.get('model','')}".lower()
    out = []
    is_seat = any(k in text for k in ["chair", "seat", "stool", "bench", "sofa", "椅", "凳", "座具", "沙发"])
    is_metal = any(k in text for k in ["metal", "steel", "aluminum", "aluminium", "iron", "金属", "钢", "铝", "铁"])
    is_wood = any(k in text for k in ["wood", "timber", "oak", "acacia", "mdf", "木"])
    is_uphol = any(k in text for k in ["upholster", "padded", "leather", "pu ", "软垫", "皮"])
    is_furniture = any(k in text for k in ["furniture", "table", "desk", "cabinet", "shelf", "rack", "stand", "bed", "drawer", "家具", "桌", "柜", "架", "床"])
    if is_seat and is_metal and is_uphol:
        out += ["9401719000", "9401790000"]
    elif is_seat and is_metal:
        out += ["9401790000", "9401719000"]
    elif is_seat and is_wood:
        out += ["9401690090", "9401690000"]
    elif is_furniture and is_metal:
        out += ["9403200000", "7326909000"]
    elif is_furniture and is_wood:
        out += ["9403609990", "9403600000"]
    elif is_seat:
        out += ["9401790000", "9401690090"]
    elif is_furniture:
        out += ["9403609990", "9403200000"]
    return list(dict.fromkeys(out))


def _name_match_score(item: dict, row: dict) -> int:
    g = (row.get("gName") or "").lower()
    en = (item.get("name_en") or "").lower()
    zh = item.get("name_zh") or ""
    mat = (item.get("material") or "").lower()
    score = 0
    if any(k in g for k in ["坐具", "椅", "凳", "家具", "桌", "架", "柜"]) and any(k in en + zh for k in ["chair", "seat", "bench", "table", "rack", "shelf", "stand", "椅", "桌", "架"]):
        score += 2
    if ("金属" in g and any(k in mat + en + zh for k in ["metal", "steel", "aluminum", "aluminium", "金属", "钢", "铝"])) or ("木" in g and any(k in mat + en + zh for k in ["wood", "timber", "木"])):
        score += 3
    if "软垫" in g and any(k in mat + en + zh for k in ["upholster", "leather", "padded", "pu", "软垫", "皮"]):
        score += 2
    if "吊扇" in g and "fan" in en:
        score += 5
    if "其他" in g:
        score += 3
    if any(k in g for k in ["天然漆", "大漆", "濒危", "红木", "柚木", "花梨", "紫檀"]):
        text_all = (en + zh + mat).lower()
        if "天然漆" in g or "大漆" in g:
            if "lacquer" not in text_all and "漆" not in text_all:
                score -= 3
        if "濒危" in g and "非濒危" not in g:
            if not any(k in text_all for k in ["endangered", "rosewood", "teak", "红木", "柚木", "花梨", "紫檀"]):
                score -= 4
        if any(k in g for k in ["红木", "柚木", "花梨", "紫檀"]) and not any(k in text_all for k in ["rosewood", "teak", "红木", "柚木", "花梨", "紫檀"]):
            score -= 3
    if "金属" in g and any(k in (en + zh + mat).lower() for k in ["wood", "木"]):
        score -= 1
    if "木" in g and any(k in (en + zh + mat).lower() for k in ["metal", "steel", "aluminum", "金属", "钢", "铝"]):
        score -= 1
    return score


def _select_candidate(item: dict, rows: list[dict]) -> dict | None:
    if not rows:
        return None
    source_hs = re.sub(r"\D", "", str(item.get("hs_code") or ""))
    if source_hs:
        for r in rows:
            if str(r.get("codeTs")) == source_hs:
                return r
    best = None
    best_score = -1
    for r in rows:
        score = _name_match_score(item, r)
        if score > best_score:
            best, best_score = r, score
    if best_score <= 0:
        return None
    return best


def _evidence_record(item: dict, record_id: str, field: str, value: str, status: str, *, source_url: str,
                     evidence: str, reason: str, original: str = "", confidence: str = "verified",
                     caveat: str = "", extra: dict | None = None) -> dict:
    return {
        "id": record_id,
        "item_id": item.get("id"),
        "item_name": item.get("name_en") or item.get("name_zh"),
        "field": field,
        "field_label": {
            "hs_code": "HS 编码", "declaration_elements": "申报要素",
            "product_name_en": "英文品名", "product_name_zh": "中文品名",
            "origin_criterion": "ChAFTA 原产地标准", "preference_eligible": "优惠资格",
            "au_hs_code": "澳洲参考税号",
        }.get(field, field),
        "value": value,
        "original_value": original,
        "status": status,
        "source_url": source_url,
        "retrieved_at": now_iso(),
        "matched_evidence": evidence,
        "reason": reason,
        "confidence": confidence,
        "caveat": caveat,
        "confirmed": False,
        "extra": extra or {},
    }


def _hs_proposal(item: dict, idx: int, attempts: list[dict]) -> dict:
    rid = f"cmp_{item.get('id')}_hs"
    source_hs = re.sub(r"\D", "", str(item.get("hs_code") or ""))
    candidates = []
    if source_hs:
        candidates.append(source_hs)
    candidates += _candidate_codes(item)
    seen = []
    for code in candidates:
        if code and code not in seen:
            seen.append(code)
    for code in seen:
        for prefix_len in (10, 8, 6, 4):
            q = code[:prefix_len]
            if not q:
                continue
            res = query_tariff(q)
            attempts.append({"kind": "customs", "url": res.get("url"), "query": q, "http_status": res.get("http_status"),
                             "elapsed_ms": res.get("elapsed_ms"), "rows": len(res.get("rows") or []),
                             "error": res.get("error"), "cache_hit": res.get("cache_hit")})
            if res.get("rows"):
                selected = _select_candidate(item, res["rows"])
                if selected:
                    selected_code = str(selected.get("codeTs"))
                    evidence = json.dumps(selected, ensure_ascii=False, separators=(",", ":"))
                    status = "supported"
                    confidence = "verified" if source_hs and selected_code == source_hs else "candidate"
                    reason = (
                        f"中国海关官网税率查询返回官方 10 位税号 {selected_code}（{selected.get('gName','')}）。"
                        + ("与源单证 HS 完全一致，已核验。" if confidence == "verified" else
                           f"源单证 HS {source_hs or '缺失'} 与官方 10 位税号不一致/不完整，系统仅提出候选归类，需人工确认，最终归类以海关为准。")
                    )
                    return _evidence_record(
                        item, rid, "hs_code", selected_code, status,
                        source_url=CUSTOMS_PAGE_URL, evidence=evidence, reason=reason,
                        original=source_hs, confidence=confidence,
                        caveat=CUSTOMS_DISCLAIMER,
                        extra={"gName": selected.get("gName"), "impOrdinaryRate": selected.get("impOrdinaryRate"),
                               "impDiscountRate": selected.get("impDiscountRate"), "queryCode": q,
                               "source_page": CUSTOMS_DETAIL_URL},
                    )
            # if exact row not found, continue with shorter prefix; stop at 4
    # fallback to the pre-captured official evidence from the research sprint
    for rec in _fallback_hs(item.get("name_en") or item.get("name_zh") or "", source_hs):
        attempts.append({"kind": "fallback_evidence", "url": rec.get("source_url"), "http_status": "cached", "rows": 1})
        return _evidence_record(
            item, rid, "hs_code", str(rec.get("hs_code")), "supported",
            source_url=rec.get("source_url"), evidence=rec.get("matched_evidence"),
            reason=(rec.get("reason") or "") + "（实时接口不可用时使用已留存的官方取证记录）",
            original=source_hs, confidence="cached",
            caveat=CUSTOMS_DISCLAIMER, extra={"cache": True},
        )
    return _evidence_record(
        item, rid, "hs_code", "", "unsupported",
        source_url=CUSTOMS_PAGE_URL,
        evidence="未获得可引用的官方税号行。" if source_hs else "源单证未提供 HS 编码，且官网查询未返回可匹配的 10 位税号。",
        reason="已尝试 online.customs.gov.cn 税率查询接口；没有可匹配的官方记录，字段保持 unsupported，绝不猜测。",
        original=source_hs, confidence="unsupported",
        caveat=CUSTOMS_DISCLAIMER,
    )


CN_TERMS = {
    "excavator": ["挖掘机"], "digger": ["挖掘机"], "挖掘机": ["挖掘机"], "挖机": ["挖掘机"],
    "bucket": ["铲斗", "戽斗", "斗"], "挖斗": ["铲斗", "戽斗", "斗"], "铲斗": ["铲斗", "戽斗", "斗"],
    "ripper": ["松土器", "零件"], "松土器": ["松土器", "零件"], "scarifier": ["松土器", "零件"],
    "auger": ["钻", "零件"], "螺旋钻": ["钻", "零件"], "钻孔": ["钻", "零件"],
    "fork": ["货叉", "叉", "零件"], "货叉": ["货叉", "叉", "零件"],
    "breaker": ["破碎锤", "锤", "零件"], "hammer": ["锤", "零件"], "破碎锤": ["破碎锤", "锤", "零件"],
    "grapple": ["抓斗", "夹斗", "斗"], "抓斗": ["抓斗", "夹斗", "斗"],
    "cabinet": ["柜", "家具"], "柜": ["柜", "家具"], "家具": ["家具"],
    "chair": ["椅", "坐具"], "seat": ["椅", "坐具"], "椅": ["椅", "坐具"],
    "table": ["桌", "家具"], "桌": ["桌", "家具"],
    "sunglass": ["太阳镜", "眼镜"], "眼镜": ["眼镜"], "spectacle": ["眼镜", "镜架"],
    "frame": ["镜架", "框架"], "镜架": ["镜架", "框架"],
    "lamp": ["灯", "灯具"], "slit": ["裂隙灯", "灯"], "ophthalmic": ["眼科", "验光"],
    "optometry": ["验光", "眼科"], "lens": ["镜片", "透镜"], "透镜": ["透镜", "镜片"],
}


def _cn_terms(item: dict, au: dict | None) -> list[str]:
    text = " ".join(str(item.get(k) or "") for k in ("name_en", "name_zh", "material", "model"))
    terms: list[str] = []
    for x in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        if x not in terms:
            terms.append(x)
    low = text.lower()
    for en, cn in CN_TERMS.items():
        if re.search(rf"\b{re.escape(en)}", low) or (en in text and re.search(r"[\u4e00-\u9fff]", en)):
            for c in cn:
                if c not in terms:
                    terms.append(c)
    if au:
        desc = (au.get("row") or {}).get("desc_full", "") or (au.get("row") or {}).get("desc", "")
        if "other" in desc.lower() and "其他" not in terms:
            terms.append("其他")
        if "零件" not in terms and any(x in low for x in ("attachment", "part", "配件", "附件")):
            terms.append("零件")
    return terms


def _cn_score(item: dict, row: dict, au: dict | None, source_hs: str) -> int:
    g = row.get("gName") or ""
    score = 0
    for t in _cn_terms(item, au):
        if t and t in g:
            score += 10 if len(t) >= 2 else 4
    desc = ((au or {}).get("row") or {}).get("desc_full", "") or ((au or {}).get("row") or {}).get("desc", "")
    if "other" in desc.lower() and "其他" in g:
        score += 4
    if any(x in g for x in ("农用", "轮胎", "履带", "客运", "货运")) and not any(
            x in (str(item.get("name_en")) + str(item.get("name_zh")) + str(item.get("material"))).lower()
            for x in ("tyre", "tire", "track", "轮", "履带", "农用")):
        score -= 3
    specific = ("差速器", "驱动桥", "车桥", "变速箱", "制动", "离合", "矿用", "电铲")
    if any(x in g for x in specific) and not any(
            x in (str(item.get("name_en")) + str(item.get("name_zh")) + str(item.get("material"))).lower()
            for x in specific):
        score -= 12
    if "其他" in g and "零件" in g:
        score += 3
    if row.get("codeTs", "").endswith(("9900", "9000", "1990")):
        score += 1
    if source_hs and row.get("codeTs", "").startswith(source_hs[:6]):
        score += 2
    if g.endswith("其他") or "其他" in g:
        score += 1
    return score


def _pick_china_row(item: dict, au: dict | None, source_hs: str, attempts: list[dict]) -> tuple[dict | None, str]:
    # 1) the source line is already a Chinese 10-digit code and exists in the official tariff
    if source_hs:
        res = query_tariff(source_hs)
        attempts.append({"kind": "customs", "url": res.get("url"), "query": source_hs, "http_status": res.get("http_status"),
                         "rows": len(res.get("rows") or []), "error": res.get("error"), "cache_hit": res.get("cache_hit")})
        exact = next((r for r in res.get("rows") or [] if str(r.get("codeTs")) == source_hs), None)
        if exact:
            return exact, "中国海关官网 · 源单证 10 位编码精确命中"
        if res.get("rows"):
            best = max(res["rows"], key=lambda r: _cn_score(item, r, au, source_hs))
            return best, "中国海关官网 · 源编码前缀匹配"
    # 2) match on the Australian HS6 (the rule: Australia first, China mapping second)
    prefixes = []
    for p in ((au or {}).get("hs6"), (source_hs or "")[:6], (source_hs or "")[:4]):
        if p and p not in prefixes:
            prefixes.append(p)
    for p in prefixes:
        res = query_tariff(p)
        attempts.append({"kind": "customs", "url": res.get("url"), "query": p, "http_status": res.get("http_status"),
                         "rows": len(res.get("rows") or []), "error": res.get("error"), "cache_hit": res.get("cache_hit")})
        rows = res.get("rows") or []
        if rows:
            best = max(rows, key=lambda r: _cn_score(item, r, au, source_hs))
            return best, f"中国海关官网 · 以澳洲 HS6 {p} 映射"
    return None, "中国海关官网未找到对应 10 位编码"


def _au_first_records(item: dict, idx: int, abf_evidence: dict) -> list[dict]:
    attempts: list[dict] = []
    au = au_tariff.classify_au(item)
    source_hs = re.sub(r"\D", "", str(item.get("hs_code") or ""))[:10]
    china, china_method = _pick_china_row(item, au, source_hs, attempts)
    records: list[dict] = []

    au_hs = str(au.get("au_hs") or "")
    path = au.get("path") or "China-only"
    if au_hs:
        if path == "ChAFTA":
            au_reason = (
                f"中澳协定（ChAFTA）命中：{au.get('method')} → AU {au_hs}；"
                f"2026 优惠税率 {au.get('chafta_rate') or '未列明'}；PSR {au.get('psr') or '未取得'}；"
                f"MFN {au.get('mfn') or '—'}。该税号作为澳洲参考。"
            )
            au_conf = "ChAFTA"
        elif path == "ABF":
            au_reason = (
                f"ChAFTA 无优惠条目，回退 ABF 进口税则：{au.get('method')} → AU {au_hs}；"
                f"ABF 一般税率 {au.get('mfn') or (au.get('abf') or {}).get('rate') or '—'}；"
                "该税号作为澳洲参考，不宣称 ChAFTA 优惠。"
            )
            au_conf = "ABF fallback"
        else:
            au_reason = (
                f"澳洲参考税号：{au.get('method')} → AU {au_hs}；"
                "ChAFTA 未列明、ABF 未确认该 8 位行；仅作平台参考，不宣称优惠。"
            )
            au_conf = "AU reference"
        records.append(_evidence_record(
            item, f"cmp_{item.get('id')}_au", "au_hs_code", au_hs, "supported",
            source_url=au.get("source_url") or au_tariff.AU_SOURCE_URL,
            evidence=au.get("evidence") or "",
            reason=au_reason,
            confidence=au_conf,
            caveat="澳洲税号为参考；最终展示与导出采用中国出口 10 位编码，并以中国海关归类为准。",
            extra={"au_method": au.get("method"), "au_path": path,
                   "chafta_ok": bool(au.get("chafta_ok")), "abf_ok": bool(au.get("abf_ok")),
                   "chafta_rate": au.get("chafta_rate"),
                   "psr": au.get("psr"), "mfn": au.get("mfn"),
                   "abf_url": (au.get("abf") or {}).get("source_url", "")},
        ))
    else:
        records.append(_evidence_record(
            item, f"cmp_{item.get('id')}_au", "au_hs_code", "", "unsupported",
            source_url=au_tariff.AU_SOURCE_URL,
            evidence=au.get("evidence") or "澳洲税则数据中没有可匹配行。",
            reason="澳洲先行归类未找到可核对的 8 位税号；不猜测，继续用中国海关侧编码校验。",
            confidence="unsupported",
            caveat="未生成澳洲归类值。",
        ))

    # ---- final Chinese HS record (China authoritative) ----
    if china:
        final_hs = str(china.get("codeTs"))
        au6 = (au_hs or "")[:6]
        aligned = bool(au6) and final_hs[:6] == au6
        if not au6:
            alignment = "china_only"
            align_text = "澳洲侧无可比对编码，最终以中国海关编码为准"
        elif aligned:
            alignment = "aligned_6"
            align_text = f"澳洲与中国的 6 位 HS 一致（{au6}）"
        else:
            alignment = "china_authoritative"
            align_text = f"澳洲 HS6 {au6} 与中国 HS6 {final_hs[:6]} 不一致，按规则以中国编码为准"
        records.append(_evidence_record(
            item, f"cmp_{item.get('id')}_hs", "hs_code", final_hs, "supported",
            source_url=CUSTOMS_PAGE_URL,
            evidence=json.dumps(china, ensure_ascii=False, separators=(",", ":")),
            reason=(
                f"中国出口编码为主：{china_method} → {final_hs}（{china.get('gName', '')}）。"
                f"澳洲参考：{path} / AU {au_hs or '—'}"
                f"（ChAFTA {au.get('chafta_rate') or '未列明'}，PSR {au.get('psr') or '—'}）。{align_text}。"
            ),
            original=source_hs,
            confidence="verified" if (source_hs and final_hs == source_hs) else "candidate",
            caveat=CUSTOMS_DISCLAIMER,
            extra={
                "au_hs": au_hs, "au_desc": ((au.get("row") or {}).get("desc_full") or (au.get("row") or {}).get("desc") or ""),
                "au_path": path, "chafta_ok": bool(au.get("chafta_ok")), "abf_ok": bool(au.get("abf_ok")),
                "au_method": au.get("method"), "chafta_rate": au.get("chafta_rate"), "psr": au.get("psr"),
                "mfn": au.get("mfn"), "alignment": alignment, "china_method": china_method,
                "au_source_url": au.get("source_url"), "au_evidence": (au.get("evidence") or "")[:1200],
                "abf": au.get("abf"),
            },
        ))
    else:
        records.append(_evidence_record(
            item, f"cmp_{item.get('id')}_hs", "hs_code", "", "unsupported",
            source_url=CUSTOMS_PAGE_URL,
            evidence="中国海关官网未返回可匹配的 10 位税号。",
            reason=(
                f"澳洲先行：AU {au_hs or '未找到'}（{au.get('method')}）；"
                f"但中国海关官网未找到对应 10 位编码，字段保持 unsupported，绝不猜测。"
            ),
            original=source_hs, confidence="unsupported", caveat=CUSTOMS_DISCLAIMER,
            extra={"au_hs": au_hs, "au_method": au.get("method")},
        ))

    # ---- ChAFTA origin / preference from the official Australian schedule ----
    chafta = au.get("chafta_rate") or ""
    psr = au.get("psr") or ""
    row = au.get("row") or {}
    if chafta:
        records.append(_evidence_record(
            item, f"cmp_{item.get('id')}_origin", "origin_criterion",
            psr or "ChAFTA PSR (见 Annex II)", "supported",
            source_url=au.get("source_url") or au_tariff.AU_SOURCE_URL,
            evidence=json.dumps({k: row.get(k) for k in ("hs", "desc", "mfn", "chafta", "psr")}, ensure_ascii=False),
            reason=f"澳洲 ChAFTA 税则行 {row.get('hs')}：2026 优惠税率 {chafta}，产品特定原产地规则（PSR）为 {psr or '未列明'}。",
            confidence="ChAFTA schedule",
            caveat="PSR 是原产地判定标准，最终以 ChAFTA 原产地证书 / ABF Origin Advice 为准。",
        ))
        records.append(_evidence_record(
            item, f"cmp_{item.get('id')}_pref", "preference_eligible",
            f"ChAFTA 2026 优惠税率 {chafta}（PSR {psr or 'Annex II'}）；须满足中国原产、证书/声明及直运要求",
            "supported", source_url=au.get("source_url") or au_tariff.AU_SOURCE_URL,
            evidence=json.dumps({k: row.get(k) for k in ("hs", "desc", "mfn", "chafta", "psr")}, ensure_ascii=False),
            reason="官方 ChAFTA 税则行存在优惠税率；这是澳大利亚进口侧的优惠税率，不是中国进口税率。",
            confidence="ChAFTA schedule",
            caveat="优惠税率适用前提：满足 PSR、原产地证书/声明与直运规则。",
        ))
    elif au.get("abf"):
        abf = au["abf"]
        records.append(_evidence_record(
            item, f"cmp_{item.get('id')}_origin", "origin_criterion", "", "unsupported",
            source_url=abf.get("source_url") or au.get("source_url"),
            evidence=abf.get("evidence") or "",
            reason="ChAFTA 批量税则中没有该行，但 ABF Working Tariff 存在该进口税号；具体 PSR 未在该页给出，保持 unsupported。",
            confidence="unsupported",
            caveat="未虚构 CTH/RVC；需查 ChAFTA Annex II 或申请 ABF Origin Advice。",
        ))
        records.append(_evidence_record(
            item, f"cmp_{item.get('id')}_pref", "preference_eligible",
            f"ABF 一般税率 {abf.get('rate') or au.get('mfn') or '—'}；ChAFTA 无优先条目",
            "supported", source_url=abf.get("source_url") or au.get("source_url"),
            evidence=abf.get("evidence") or "",
            reason="ChAFTA 数据未列明该税号，按 ABF Working Tariff 一般税率处理；仅作进口税率参考，不宣称已获 ChAFTA 优惠。",
            confidence="ABF general tariff",
            caveat="这是 ABF 一般税率，不是 ChAFTA 优惠税率。",
        ))
    else:
        # keep the ABF guidance cards when no AU row exists
        records.extend(_abf_records(item, idx, abf_evidence))

    decl_hs = str(china.get("codeTs")) if china else (source_hs or au_hs)
    el = declaration.elements_for(decl_hs)
    if el.get("element_text"):
        records.append(_evidence_record(
            item, f"cmp_{item.get('id')}_decl", "declaration_elements", el["element_text"], "supported",
            source_url=el.get("source_url") or declaration.SOURCE_URL,
            evidence=json.dumps({"hs": el.get("hs"), "elements": el.get("elements"),
                                 "required": el.get("required")}, ensure_ascii=False),
            reason=(f"中国海关官方申报要素表（CusMerchElement）按 {decl_hs} 匹配到 "
                    f"{el.get('hs')} 组：{el.get('element_text')}。导出时只填已知产品值；"
                    "官方要素只规定必填项，不提供产品材质/用途等具体值，缺失值不编造。"),
            confidence="official CusMerchElement",
            caveat="申报要素以实际通关时海关解释为准；产品值需与发票/箱单/合同一致。",
        ))
    else:
        records.append(_evidence_record(
            item, f"cmp_{item.get('id')}_decl", "declaration_elements", "", "unsupported",
            source_url=declaration.SOURCE_URL,
            evidence="中国海关官方申报要素表未找到对应 HS 分组。",
            reason="官方 CusMerchElement 表未匹配到该 HS 的申报要素，字段保持 unsupported。",
            confidence="unsupported", caveat="未生成任何申报要素，避免编造。",
        ))
    return records


def _abf_records(item: dict, idx: int, abf_evidence: dict) -> list[dict]:
    records = []
    origin_quote = abf_evidence.get("psr_quote") or "A PSR sets out the following criteria that apply either solely or in conjunction to a good: change of tariff classification (CTC); regional value content (RVC); or specific manufacturing or processing operation rules."
    origin_url = abf_evidence.get("psr_url") or ABF_GUIDE_PDF_URL
    records.append(_evidence_record(
        item, f"cmp_{item.get('id')}_origin", "origin_criterion",
        "按 ChAFTA 产品特定原产地规则（CTC / RVC / 特定加工工序）判定；具体 PSR 值需核对 Annex II",
        "supported", source_url=origin_url, evidence=origin_quote,
        reason="ABF 官方《ChAFTA Rules of Origin — Instruction and Guideline》明确 PSR 由 CTC/RVC/特定加工工序组成；未取得该 HS 行对应的具体 PSR 值时，仅提供标准框架，不虚构 CTC/RVC 结论。",
        confidence="guidance", caveat="该字段为官方规则框架，不等于已完成原产地判定；最终以 ABF Origin Advice / 原产地证书为准。",
    ))
    elig_quote = abf_evidence.get("eligibility_quote") or "To be eligible for ChAFTA preferential rates, the following requirements must be met: the goods are Chinese originating; the importer claiming preferential treatment satisfies the documentary requirements; and the goods meet the consignment provisions."
    records.append(_evidence_record(
        item, f"cmp_{item.get('id')}_pref", "preference_eligible",
        "CONDITIONAL — 须满足 ChAFTA 原产资格、原产地证书/声明及直运规则（澳大利亚进口优惠税率以 ABF Working Tariff 为准）",
        "supported", source_url=abf_evidence.get("eligibility_url") or ABF_GUIDE_PDF_URL, evidence=elig_quote,
        reason="ABF 官方指南列明 ChAFTA 优惠税率的三项前提；本平台未取得澳大利亚 Working Tariff Schedule 12 的具体税率，因此只给出资格条件，不宣称已获得优惠税率。",
        confidence="guidance", caveat="中国海关官网的 0% 协定税率是中国进口侧优惠，不是澳大利亚进口税率；不得混用。",
    ))
    return records


def _fetch_abf_evidence(attempts: list[dict]) -> dict:
    cached = _cache_get("abf:chafta:guidance", ttl_hours=24 * 7)
    if cached:
        return dict(cached, cache_hit=True)
    out = {}
    # HTML: eligibility framework
    t0 = time.time()
    status, text, err = _http_get(ABF_FTA_URL, timeout=15)
    attempts.append({"kind": "abf", "url": ABF_FTA_URL, "http_status": status, "elapsed_ms": int((time.time() - t0) * 1000), "error": err})
    if status == 200 and text:
        m = re.search(r"Australia has preferential arrangements[^<]{0,500}", text, re.I)
        if m:
            out["eligibility_quote"] = re.sub(r"\s+", " ", m.group(0))[:500]
            out["eligibility_url"] = ABF_FTA_URL
    # PDF: PSR criteria + eligibility
    t0 = time.time()
    req = urllib.request.Request(ABF_GUIDE_PDF_URL, headers={"User-Agent": UA})
    try:
        data = urllib.request.urlopen(req, timeout=25, context=ssl.create_default_context()).read()
        attempts.append({"kind": "abf_pdf", "url": ABF_GUIDE_PDF_URL, "http_status": 200, "elapsed_ms": int((time.time() - t0) * 1000), "bytes": len(data)})
        tmp = DATA_DIR / "abf_guide.pdf"
        tmp.write_bytes(data)
        import fitz
        doc = fitz.open(str(tmp))
        full = "\n".join(p.get_text() for p in doc)
        m = re.search(r"A PSR sets out the following criteria[^\n]*(?:\n[^\n]*){0,4}", full)
        if m:
            out["psr_quote"] = re.sub(r"\s+", " ", m.group(0)).strip()[:800]
            out["psr_url"] = ABF_GUIDE_PDF_URL
        m = re.search(r"To be eligible for ChAFTA preferential rates[^\n]*(?:\n[^\n]*){0,5}", full)
        if m:
            out["eligibility_quote"] = re.sub(r"\s+", " ", m.group(0)).strip()[:800]
            out["eligibility_url"] = ABF_GUIDE_PDF_URL
        m = re.search(r"8\.6\.1\.[^\n]*(?:\n[^\n]*){0,4}", full)
        if m:
            out["psr_interaction_quote"] = re.sub(r"\s+", " ", m.group(0)).strip()[:800]
    except Exception as exc:
        attempts.append({"kind": "abf_pdf", "url": ABF_GUIDE_PDF_URL, "http_status": 0, "elapsed_ms": int((time.time() - t0) * 1000), "error": f"{type(exc).__name__}: {exc}"})
    if not out.get("psr_quote") or not out.get("eligibility_quote"):
        # bundled fallback, clearly marked
        try:
            for r in json.loads((RESEARCH_DIR / "evidence.json").read_text(encoding="utf-8")):
                if r.get("status") == "supported" and r.get("kind") == "origin_criterion":
                    out.setdefault("psr_quote", r.get("matched_evidence"))
                    out.setdefault("psr_url", r.get("source_url"))
                if r.get("status") == "supported" and r.get("kind") == "preference_eligible" and "ABF" in (r.get("source_url") or ""):
                    out.setdefault("eligibility_quote", r.get("matched_evidence"))
                    out.setdefault("eligibility_url", r.get("source_url"))
        except Exception:
            pass
    out["retrieved_at"] = now_iso()
    if out:
        _cache_put("abf:chafta:guidance", out)
    return out


def run_compliance(items: list[dict], settings: dict | None = None) -> dict:
    """Build supplement proposals for every item. Does not mutate items."""
    started = time.time()
    attempts: list[dict] = []
    abf = _fetch_abf_evidence(attempts)
    records: list[dict] = []
    for idx, item in enumerate(items, start=1):
        records.extend(_au_first_records(item, idx, abf))
        # product name supplementation is only allowed when a side is genuinely missing
        if not item.get("name_en") and item.get("name_zh"):
            records.append(_evidence_record(
                item, f"cmp_{item.get('id')}_en", "product_name_en", "", "unsupported",
                source_url="", evidence="源单证只有中文品名，未取得官方英文品名。",
                reason="没有可引用的官方英文品名，保持 unsupported。", confidence="unsupported"))
        if not item.get("name_zh") and item.get("name_en"):
            records.append(_evidence_record(
                item, f"cmp_{item.get('id')}_zh", "product_name_zh", "", "unsupported",
                source_url="", evidence="源单证只有英文品名，未取得官方中文品名。",
                reason="没有可引用的官方中文品名，保持 unsupported。", confidence="unsupported"))
    summary = {
        "records": len(records),
        "supported": sum(1 for r in records if r["status"] == "supported"),
        "unsupported": sum(1 for r in records if r["status"] == "unsupported"),
        "items": len(items),
        "elapsed_ms": int((time.time() - started) * 1000),
        "live_requests": len(attempts),
    }
    return {
        "run_at": now_iso(),
        "records": records,
        "summary": summary,
        "attempts": attempts,
        "abf": abf,
        "disclaimer": CUSTOMS_DISCLAIMER + " | 中国海关 0% 协定税率仅指中国进口侧，不是澳大利亚进口税率。",
    }


def reconcile(items: list[dict], compliance: dict) -> tuple[list[dict], dict]:
    """Apply confirmed supplements to items and compute the export gate."""
    by_item: dict[str, dict] = {}
    for r in compliance.get("records") or []:
        if r.get("item_id"):
            by_item.setdefault(r["item_id"], {})[r.get("field")] = r
    out = []
    missing_hs = []
    unconfirmed = []
    unsupported_required = []
    for it in items:
        item = dict(it)
        recs = by_item.get(item.get("id"), {})
        supplements = {}
        for field, rec in recs.items():
            supplements[field] = {
                "record_id": rec["id"], "status": rec["status"], "value": rec.get("value"),
                "confirmed": bool(rec.get("confirmed")), "confidence": rec.get("confidence"),
                "source_url": rec.get("source_url"), "retrieved_at": rec.get("retrieved_at"),
            }
            if rec["status"] == "supported" and rec.get("value"):
                if not rec.get("confirmed"):
                    unconfirmed.append({"item_id": item.get("id"), "field": field, "record_id": rec["id"]})
                else:
                    if field == "hs_code":
                        item["hs_code"] = rec.get("value")
                        item["hs_verified"] = rec.get("confidence") in {"verified", "candidate", "cached"}
                    elif field in {"origin_criterion", "preference_eligible"}:
                        item[field] = rec.get("value")
                    elif field in {"product_name_en", "product_name_zh"}:
                        item[field] = rec.get("value")
            elif rec["status"] == "unsupported" and field in {"hs_code", "declaration_elements"}:
                unsupported_required.append({"item_id": item.get("id"), "field": field, "record_id": rec["id"]})
        item["supplements"] = supplements
        item["compliance_status"] = "supported" if any(v["status"] == "supported" for v in supplements.values()) else "unsupported"
        if not item.get("hs_code"):
            missing_hs.append(item.get("id"))
        out.append(item)
    gate = {
        "ok": not unconfirmed and not missing_hs,
        "unconfirmed": unconfirmed,
        "missing_hs": missing_hs,
        "unsupported_required": unsupported_required,
        "supported": sum(1 for r in compliance.get("records") or [] if r.get("status") == "supported"),
        "unsupported": sum(1 for r in compliance.get("records") or [] if r.get("status") == "unsupported"),
        "confirmed": sum(1 for r in compliance.get("records") or [] if r.get("confirmed")),
        "compliance_run_at": compliance.get("run_at"),
    }
    return out, gate


def confirm(compliance: dict, ids: list[str], value: bool = True) -> dict:
    idset = set(ids or [])
    for r in compliance.get("records") or []:
        if r.get("id") in idset:
            r["confirmed"] = bool(value)
            r["confirmed_at"] = now_iso()
    return compliance
