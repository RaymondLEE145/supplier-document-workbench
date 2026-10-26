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
    (("wabi-sabi", "curved sofa", "弧形沙发"), "9401619090"),
    (("sliding door", "推拉门", "断桥"), "7610100000"),
    (("acoustic panel", "吸音板", "mdf"), "4411942900"),
    (("pneumatic", "抽屉床", "structure bed"), "9403509990"),
    (("tencel", "latex", "乳胶床垫"), "9404210090"),
    (("orthopedic", "矫形床垫"), "9404290000"),
    (("ceiling fan", "吊扇", "风扇"), "8414511000"),
    (("led mirror", "镜子", "mirror", "化妆镜"), "7009920000"),
    (("wall decoration", "装饰挂件", "挂件", "装饰"), "4420199090"),
    (("led light", "吊灯", "lighting", "light"), "9405110000"),
    (("sofa set", "真皮沙发", "sofa", "沙发"), "9401619090"),
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
