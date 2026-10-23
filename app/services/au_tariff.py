# -*- coding: utf-8 -*-
"""Australian-first tariff classification.

Source of truth for the Australian side is the official DFAT FTA Portal bulk
download for China (ChAFTA + RCEP tariff outcomes), mirrored locally in
``assets/au_chafta_tariff.json``.  When a line is not listed for ChAFTA we fall
back to the ABF Working Tariff chapter page (Schedule 3) to prove that an
import classification exists.  China's customs 10-digit line is applied
afterwards and always wins when the two countries diverge at 6 digits.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any

from ..config import ASSETS_DIR, DATA_DIR, now_iso

DATASET_PATH = ASSETS_DIR / "au_chafta_tariff.json"
CACHE_DIR = DATA_DIR / "abf_chapters"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
AU_SOURCE_URL = "https://ftaportal.dfat.gov.au/download"
ABF_BASE = "https://www.abf.gov.au/importing-exporting-and-manufacturing/tariff-classification/current-tariff/schedule-3"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"

SECTION_BY_CHAPTER = {
    **{i: "i" for i in range(1, 6)},
    **{i: "ii" for i in range(6, 15)},
    **{i: "iii" for i in range(15, 16)},
    **{i: "iv" for i in range(16, 25)},
    **{i: "v" for i in range(25, 28)},
    **{i: "vi" for i in range(28, 39)},
    **{i: "vii" for i in range(39, 41)},
    **{i: "viii" for i in range(41, 44)},
    **{i: "ix" for i in range(44, 47)},
    **{i: "x" for i in range(47, 50)},
    **{i: "xi" for i in range(50, 64)},
    **{i: "xii" for i in range(64, 68)},
    **{i: "xiii" for i in range(68, 71)},
    **{i: "xiv" for i in range(71, 72)},
    **{i: "xv" for i in range(72, 84)},
    **{i: "xvi" for i in range(84, 86)},
    **{i: "xvii" for i in range(86, 90)},
    **{i: "xviii" for i in range(90, 93)},
    **{i: "xix" for i in range(93, 94)},
    **{i: "xx" for i in range(94, 97)},
    **{i: "xxi" for i in range(97, 98)},
}

_INDEX: list[dict] | None = None
_BY_HS6: dict[str, list[dict]] | None = None
_ABF_TEXT: dict[str, str] = {}

# explicit domain vocabulary for attachments and construction equipment
AU_LEXICON: list[tuple[list[str], str]] = [
    (["excavator", "digger", "挖掘机", "挖机", "二手挖掘机", "二手挖机"], "84295219"),
    (["bucket", "挖斗", "铲斗", "戽斗", "土斗"], "84314100"),
    (["ripper", "scarifier", "松土器", "裂土器", "翻土器"], "84314999"),
    (["auger", "earth drill", "螺旋钻", "钻孔器", "地钻"], "84314999"),
    (["hydraulic breaker", "hydraulic hammer", "breaker", "破碎锤", "液压锤"], "84314999"),
    (["quick coupler", "quick hitch", "快换接头", "快速连接器"], "84314999"),
    (["fork", "pallet fork", "货叉", "叉齿"], "84314999"),
    (["bulldozer blade", "推土铲", "推土板"], "84314200"),
    (["grapple", "grab", "抓斗", "夹斗"], "84314100"),
    (["forklift", "叉车"], "84272010"),
    (["ophthalmic", "optometry", "验光", "眼科"], "90185000"),
    (["sunglasses", "sun glasses", "墨镜", "太阳镜"], "90041000"),
    (["spectacle frame", "eyeglass frame", "镜架", "眼镜架"], "90031100"),
    (["display cabinet", "showcase", "展柜", "展示柜"], "94036099"),
    (["office chair", "dining chair", "seat", "椅子", "座椅", "坐具"], "94017900"),
    (["wooden table", "木桌", "桌子"], "94036099"),
    (["led sign", "illuminated sign", "发光字", "招牌"], "94054010"),
    (["marker pen", "记号笔"], "96082000"),
]

STOP = {"the", "and", "of", "for", "with", "other", "parts", "part", "a", "an", "to", "in", "on", "or", "not", "including", "thereof", "suitable", "use", "principally", "solely"}


def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip().lower())


def _tokens(text: str) -> list[str]:
    out = []
    for x in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", _norm(text)):
        if x in STOP or len(x) < 2:
            continue
        out.append(x[:-1] if x.endswith("s") and len(x) > 4 else x)
    return list(dict.fromkeys(out))


def load_dataset() -> list[dict]:
    global _INDEX, _BY_HS6
    if _INDEX is not None:
        return _INDEX
    try:
        raw = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        _INDEX = raw.get("rows") or []
    except Exception:
        _INDEX = []
    _BY_HS6 = {}
    for r in _INDEX:
        _BY_HS6.setdefault(r.get("hs6") or r.get("hs", "")[:6], []).append(r)
    return _INDEX


def by_hs6(hs: str) -> list[dict]:
    load_dataset()
    return list((_BY_HS6 or {}).get((hs or "")[:6], []))


def row_for_hs8(hs8: str) -> dict | None:
    hs8 = re.sub(r"\D", "", str(hs8 or ""))[:8]
    for r in load_dataset():
        if r.get("hs") == hs8:
            return r
    return None


def _score_row(item: dict, row: dict) -> int:
    text = _norm(" ".join(str(item.get(k) or "") for k in ("name_en", "name_zh", "material", "model")))
    desc = _norm(row.get("desc_full") or row.get("desc") or "")
    q = _tokens(text)
    if not q:
        return 0
    score = 0
    for t in q:
        if len(t) <= 2:
            continue
        if re.search(rf"\b{re.escape(t)}(?:s|es)?\b", desc):
            score += 10
    if row.get("desc") and _norm(row["desc"]) in text:
        score += 6
    if "other" == _norm(row.get("desc")):
        score -= 2
    return score


def _lexicon_code(item: dict) -> str:
    text = _norm(" ".join(str(item.get(k) or "") for k in ("name_en", "name_zh", "material", "model")))
    for words, code in AU_LEXICON:
        if any(w in text for w in words):
            return code
    return ""


def _abf_url(chapter: str) -> str:
    c = int(chapter)
    return f"{ABF_BASE}/section-{SECTION_BY_CHAPTER.get(c, 'xx')}/chapter-{c}"


def abf_lookup(hs8: str) -> dict | None:
    """Prove an 8-digit line exists in ABF Schedule 3, returning a text snippet."""
    hs8 = re.sub(r"\D", "", str(hs8 or ""))[:8]
    if len(hs8) != 8:
        return None
    chapter = hs8[:2]
    url = _abf_url(chapter)
    text = _ABF_TEXT.get(chapter)
    if text is None:
        cache = CACHE_DIR / f"chapter_{chapter}.txt"
        if cache.exists():
            text = cache.read_text(encoding="utf-8", errors="replace")
        else:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
                text = re.sub(r"<[^>]+>", " ", html)
                text = re.sub(r"\s+", " ", text)
                cache.write_text(text, encoding="utf-8")
            except Exception:
                text = ""
        _ABF_TEXT[chapter] = text
    if not text:
        return None
    formatted = f"{hs8[:4]}.{hs8[4:6]}.{hs8[6:8]}"
    for needle in (formatted, hs8):
        idx = text.find(needle)
        if idx >= 0:
            snippet = text[max(0, idx - 120):idx + 420].strip()
            m = re.search(r"\b(Free|\d{1,2}%)\b", snippet)
            return {"hs": hs8, "description": snippet[:300], "rate": m.group(1) if m else "",
                    "source_url": url, "evidence": snippet[:600], "source": "ABF Working Tariff Schedule 3"}
    return None


def classify_au(item: dict) -> dict:
    """Return the Australian classification outcome, ChAFTA rate/PSR and evidence."""
    source_hs = re.sub(r"\D", "", str(item.get("hs_code") or ""))[:10]
    query = " ".join(str(item.get(k) or "") for k in ("name_en", "name_zh", "material", "model"))
    rows = by_hs6(source_hs) if source_hs else []
    selected = None
    method = ""
    # 1) ChAFTA-listed line matching the source HS6
    if rows:
        exact = next((r for r in rows if source_hs and r.get("hs") == source_hs[:8]), None)
        if exact:
            selected, method = exact, "ChAFTA dataset · source HS prefix"
        else:
            best = max(rows, key=lambda r: _score_row(item, r))
            selected, method = best, "ChAFTA dataset · source HS heading"
    # 2) no ChAFTA line for a source HS: prove the same 8-digit line in ABF
    if selected is None and source_hs:
        abf = abf_lookup(source_hs[:8])
        if abf:
            return {"au_hs": source_hs[:8], "hs6": source_hs[:6], "row": None,
                    "method": "ABF Working Tariff Schedule 3 (ChAFTA 无条目)",
                    "source_url": abf["source_url"], "retrieved_at": now_iso(), "evidence": abf["evidence"],
                    "chafta_rate": "", "mfn": abf.get("rate", ""), "psr": "", "abf": abf,
                    "path": "ABF", "chafta_ok": False, "abf_ok": True}
        # a known source code that is not listed in either official AU dataset:
        # allow a same-HS6 vocabulary code (e.g. 9403 furniture) but never cross chapters
        code = _lexicon_code(item)
        if code and code[:6] == source_hs[:6]:
            return {"au_hs": code, "hs6": code[:6], "row": row_for_hs8(code),
                    "method": "AU tariff vocabulary · same HS6 (ChAFTA 未列条目)",
                    "source_url": AU_SOURCE_URL, "retrieved_at": now_iso(),
                    "evidence": f"澳大利亚税则 HS6 {code[:6]} 存在；ChAFTA 批量数据未列出该 8 位行。",
                    "chafta_rate": "", "mfn": "", "psr": "", "abf": None,
                    "path": "AU-reference", "chafta_ok": False, "abf_ok": False}
        return {"au_hs": "", "hs6": source_hs[:6], "row": None, "method": "unsupported",
                "source_url": AU_SOURCE_URL, "retrieved_at": now_iso(),
                "evidence": "ChAFTA 与 ABF 章节中均未确认该 8 位税号。", "chafta_rate": "", "mfn": "", "psr": "", "abf": None,
                "path": "China-only", "chafta_ok": False, "abf_ok": False}
    # 3) explicit attachment / product vocabulary
    if selected is None:
        code = _lexicon_code(item)
        if code:
            selected = row_for_hs8(code)
            method = "AU tariff vocabulary / ABF Schedule 3 code"
    # 4) keyword search over official descriptions only when no source HS exists
    if selected is None and not source_hs and query.strip():
        candidates = []
        for r in load_dataset():
            s = _score_row(item, r)
            if s > 0:
                candidates.append((s, r))
        if candidates:
            candidates.sort(key=lambda x: (-x[0], len(x[1].get("hs", ""))))
            selected, method = candidates[0][1], "ABF/FTA description search"
    if selected and (selected.get("hs") or "").isdigit():
        hs8 = selected["hs"]
        chafta_ok = bool(selected.get("chafta"))
        # ChAFTA first; only if there is no preferential line do we test ABF.
        abf = None if chafta_ok else abf_lookup(hs8)
        path = "ChAFTA" if chafta_ok else ("ABF" if abf else "AU-reference")
        return {
            "au_hs": hs8,
            "hs6": hs8[:6],
            "row": selected,
            "method": method,
            "source_url": AU_SOURCE_URL,
            "retrieved_at": now_iso(),
            "evidence": json.dumps({k: selected.get(k) for k in ("hs", "desc", "desc_full", "mfn", "chafta", "psr", "notes")},
                                   ensure_ascii=False),
            "chafta_rate": selected.get("chafta") or "",
            "mfn": selected.get("mfn") or "",
            "psr": selected.get("psr") or "",
            "abf": abf,
            "path": path,
            "chafta_ok": chafta_ok,
            "abf_ok": bool(abf),
        }
    # 4) no ChAFTA line: derive the 8-digit code from a known source and prove ABF
    if source_hs:
        abf = abf_lookup(source_hs[:8])
        if abf:
            return {"au_hs": source_hs[:8], "hs6": source_hs[:6], "row": None, "method": "ABF Working Tariff Schedule 3",
                    "source_url": abf["source_url"], "retrieved_at": now_iso(), "evidence": abf["evidence"],
                    "chafta_rate": "", "mfn": abf.get("rate", ""), "psr": "", "abf": abf,
                    "path": "ABF", "chafta_ok": False, "abf_ok": True}
    # 5) last resort: lexicon code even if not in the ChAFTA dataset, try ABF proof
    code = _lexicon_code(item)
    if code:
        abf = abf_lookup(code)
        if abf:
            return {"au_hs": code, "hs6": code[:6], "row": None, "method": "AU tariff vocabulary + ABF Working Tariff",
                    "source_url": abf["source_url"], "retrieved_at": now_iso(), "evidence": abf["evidence"],
                    "chafta_rate": "", "mfn": abf.get("rate", ""), "psr": "", "abf": abf,
                    "path": "ABF", "chafta_ok": False, "abf_ok": True}
    return {"au_hs": "", "hs6": (source_hs or "")[:6], "row": None, "method": "unsupported",
            "source_url": AU_SOURCE_URL, "retrieved_at": now_iso(),
            "evidence": "澳大利亚税则数据中未找到可匹配的 8 位税号。", "chafta_rate": "", "mfn": "", "psr": "", "abf": None,
            "path": "China-only", "chafta_ok": False, "abf_ok": False}
