# -*- coding: utf-8 -*-
"""Unit-level regression for the Australia-first tariff classifier (no network)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.au_tariff import classify_au, load_dataset  # noqa: E402

rows = load_dataset()
assert len(rows) > 9000, len(rows)
by_hs = {r["hs"]: r for r in rows}
assert by_hs["84314100"]["chafta"] == "0%"
assert by_hs["84314100"]["psr"] == "CTH"
assert by_hs["84295219"]["mfn"] == "8%"

cases = {
    "KUBOTA EXCAVATOR": "84295219",
    "200MM BUCKET": "84314100",
    "1200MM BUCKET": "84314100",
    "RIPPER": "84314999",
    "AUGER": "84314999",
    "FORK": "84314999",
    "二手挖掘机": "84295219",
    "挖斗": "84314100",
    "松土器": "84314999",
    "螺旋钻": "84314999",
    "货叉": "84314999",
}
for name, expected in cases.items():
    item = {"name_en": name if not any("\u4e00" <= ch <= "\u9fff" for ch in name) else "",
            "name_zh": name if any("\u4e00" <= ch <= "\u9fff" for ch in name) else "",
            "hs_code": ""}
    got = classify_au(item)
    assert got["au_hs"] == expected, (name, got)
    assert got["chafta_rate"] == "0%", (name, got)
    assert got["psr"] == "CTH", (name, got)
print("AU-first classifier OK:", len(cases), "cases")
