# -*- coding: utf-8 -*-
"""Official Chinese customs declaration element lookup + item enrichment.

The official ``CusMerchElement`` table is keyed by 4–8 digit HS prefixes and
lists the required element names.  It does not contain product-specific values,
so known item values are kept and only transparent, reviewable defaults are
added for the template columns.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..config import ASSETS_DIR

ELEMENTS_PATH = ASSETS_DIR / "customs_elements.json"
SOURCE_URL = "https://online.customs.gov.cn/ociswebserver/pages/cus/#/tgcs/info?paramCode=CusMerchElement"
_DATA: list[dict] | None = None
_BY_HS: dict[str, list[dict]] | None = None

BRANDS = ("KUBOTA", "KOMATSU", "HITACHI", "CAT", "CATERPILLAR", "KOBELCO", "SUMITOMO",
          "DOOSAN", "HYUNDAI", "VOLVO", "JCB", "SANY", "XCMG", "LONKING", "LIUGONG")


def _load() -> None:
    global _DATA, _BY_HS
    if _DATA is not None:
        return
    _DATA = []
    _BY_HS = {}
    try:
        raw = json.loads(ELEMENTS_PATH.read_text(encoding="utf-8"))
        rows = raw.get("rows") or []
    except Exception:
        rows = []
    for r in rows:
        hs = re.sub(r"\D", "", str(r.get("hs") or ""))
        if not hs:
            continue
        key = (hs, str(r.get("element") or ""), str(r.get("required") or ""))
        _DATA.append({"hs": hs, "element": key[1], "required": key[2]})
        _BY_HS.setdefault(hs, []).append(_DATA[-1])


def elements_for(hs: str) -> dict:
    """Return the most specific official element rows for a 10-digit HS code."""
    _load()
    hs = re.sub(r"\D", "", str(hs or ""))
    if not hs or not _BY_HS:
        return {"hs": "", "elements": [], "required": [], "element_text": "", "source_url": SOURCE_URL}
    # exact 8-digit first, then progressively shorter prefixes
    for n in (8, 7, 6, 5, 4):
        key = hs[:n]
        rows = _BY_HS.get(key)
        if rows:
            required = [r["element"] for r in rows if str(r.get("required")) == "1"]
            text = "；".join(f"{r['element']}{'*' if str(r.get('required')) == '1' else ''}" for r in rows)
            return {"hs": key, "elements": [r["element"] for r in rows], "required": required,
                    "element_text": text, "source_url": SOURCE_URL}
    return {"hs": "", "elements": [], "required": [], "element_text": "", "source_url": SOURCE_URL}


def _brand(item: dict) -> str:
    for k in ("brand", "brand_name"):
        v = str(item.get(k) or "").strip()
        if v:
            return v
    name = str(item.get("name_en") or item.get("model") or "").upper()
    for b in BRANDS:
        if re.search(rf"\b{re.escape(b)}\b", name):
            return b
    return "无品牌"


def _material(item: dict, hs: str) -> str:
    v = str(item.get("material") or "").strip()
    if v:
        return v
    name = (str(item.get("name_en") or "") + " " + str(item.get("name_zh") or "")).lower()
    if hs.startswith(("8429", "8431")):
        return "钢"
    if hs.startswith(("94016", "94033", "94036", "94035")):
        return "木质"
    if hs.startswith(("94032", "94013", "94015", "94017", "94031")):
        return "金属/软包"
    if hs.startswith(("94037", "94017")):
        return "塑料"
    if hs.startswith(("9003", "9004")):
        return "塑料/金属"
    if hs.startswith(("9018", "9013", "9033", "9027")):
        return "金属/塑料"
    if hs.startswith(("4202",)):
        return "塑料/织物"
    if hs.startswith(("6307",)):
        return "织物"
    if hs.startswith(("3926",)):
        return "塑料"
    if hs.startswith(("4820",)):
        return "纸"
    if hs.startswith(("9608",)):
        return "塑料"
    if hs.startswith(("8205",)):
        return "钢"
    if "wood" in name or "木" in name:
        return "木质"
    if "steel" in name or "metal" in name or "钢" in name or "金属" in name:
        return "金属"
    return "未提供"


def _usage(item: dict, hs: str) -> str:
    v = str(item.get("usage") or "").strip()
    if v:
        return v
    if hs.startswith("8429"):
        return "土方工程"
    if hs.startswith("8431"):
        return "挖掘机/工程机械配套"
    if hs.startswith(("9401", "9403")):
        return "室内使用"
    if hs.startswith(("9003", "9004")):
        return "视力矫正/日常佩戴"
    if hs.startswith(("9018", "9013", "9033", "9027")):
        return "眼科检查/验光"
    if hs.startswith("9608"):
        return "书写"
    if hs.startswith("8205"):
        return "维修"
    if hs.startswith("4202"):
        return "收纳"
    if hs.startswith("6307"):
        return "清洁"
    if hs.startswith("3926"):
        return "展示/收纳"
    return "出口货物"


def _processing(item: dict, hs: str) -> str:
    v = str(item.get("processing") or "").strip()
    if v:
        return v
    if hs.startswith(("8429", "8431")):
        return "焊接/机加工"
    if hs.startswith(("9401", "9403", "9003", "9004")):
        return "组装"
    if hs.startswith("3926"):
        return "注塑"
    if hs.startswith("8205"):
        return "锻造/机加工"
    if hs.startswith("6307"):
        return "缝制"
    if hs.startswith("9608"):
        return "组装"
    return "加工"


def _scenario(item: dict, hs: str) -> str:
    v = str(item.get("scenario") or "").strip()
    if v:
        return v
    if hs.startswith(("8429", "8431")):
        return "工程施工"
    if hs.startswith(("9401", "9403")):
        return "室内/办公"
    if hs.startswith(("9003", "9004")):
        return "日常佩戴"
    if hs.startswith(("9018", "9013", "9033", "9027")):
        return "医疗/验光"
    if hs.startswith(("3926", "4202")):
        return "展示/收纳"
    return "出口"


def enrich(items: list[dict]) -> list[dict]:
    """Attach official element text and template values to each item."""
    for it in items:
        hs = re.sub(r"\D", "", str(it.get("hs_code") or ""))
        el = elements_for(hs)
        it["declaration_elements"] = el["element_text"]
        it["declaration_source"] = el["source_url"] if el["element_text"] else ""
        it["declaration_fields"] = {
            "brand": _brand(it),
            "material": _material(it, hs),
            "usage": _usage(it, hs),
            "processing": _processing(it, hs),
            "scenario": _scenario(it, hs),
            "preference": str(it.get("preference") or ("享受优惠" if "CHAFTA" in str(it.get("preference_eligible") or "").upper() else "不享受优惠")),
        }
        it["declaration_official"] = el["required"]
    return items
