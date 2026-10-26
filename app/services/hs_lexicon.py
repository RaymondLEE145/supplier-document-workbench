# -*- coding: utf-8 -*-
"""Product-name -> Chinese HS candidates for packing lists with no HS column.

These are candidate seeds only; the value is verified against the official
China customs tariff endpoint and kept with a reviewable evidence record.
"""
from __future__ import annotations

import re

RULES: list[tuple[tuple[str, ...], str]] = [
    (("bar stool", "吧台椅", "吧椅"), "9401790000"),
    (("office chair", "办公椅", "职员椅"), "9401390000"),
    (("massage chair", "按摩椅"), "9019101000"),
    (("dining chair", "餐椅", "椅子", "chair", "stool"), "9401790000"),
    (("sofa", "沙发"), "9401619090"),
    (("mattress", "床垫"), "9404210090"),
    (("bed", "床"), "9403509990"),
    (("ceiling fan", "吊扇", "风扇"), "8414511000"),
    (("led mirror", "镜子", "mirror", "化妆镜"), "7009920000"),
    (("wall decoration", "装饰挂件", "挂件", "装饰"), "4420199090"),
    (("cabinet", "柜", "橱柜"), "9403609990"),
    (("table", "桌"), "9403609990"),
    (("lamp", "灯", "lighting"), "9405409000"),
    (("sunglass", "太阳镜", "墨镜"), "9004100000"),
    (("spectacle", "眼镜", "镜架"), "9003110000"),
]


def candidates(item: dict) -> list[str]:
    text = " ".join(str(item.get(k) or "") for k in ("name_en", "name_zh", "model")).lower()
    out = []
    for words, code in RULES:
        if any(w in text for w in words) and code not in out:
            out.append(code)
    return out
