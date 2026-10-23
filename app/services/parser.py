# -*- coding: utf-8 -*-
"""Structure-aware extraction for PDF / XLSX / image supplier documents.

The parser deliberately keeps the *layout* (page boxes, table grid, coordinates,
merged-cell metadata) instead of flattening everything to text.  The resulting
``structure`` object is what gets sent to the code-generation / LLM stage.
"""
from __future__ import annotations

import re
import statistics
import json
from pathlib import Path
from typing import Any

from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# field vocabulary
# ---------------------------------------------------------------------------
FIELD_SYNONYMS: dict[str, list[str]] = {
    "no": ["no.", "no", "序号", "项号", "s/n", "serial no"],
    "model": ["model", "型号", "item no", "item no.", "货号", "sku", "art no", "product code", "款号"],
    "name_en": [
        "english description", "description of goods", "item description", "product description",
        "description", "英文品名", "品名英文", "product name", "commodity", "goods description",
    ],
    "name_zh": ["中文品名", "品名", "货物名称", "商品名称", "产品名称", "品名及规格"],
    "hs_code": ["hs code", "hs_code", "hs编码", "海关编码", "商品编码", "税则号", "hs", "产品海关编码"],
    "material": ["materials", "material", "材质", "材料", "产品材质"],
    "cartons": ["外箱数量", "箱数", "cartons", "ctns", "carton", "packages", "件数", "package count", "货箱编号", "箱号", "箱数*"],
    "pieces_per_carton": ["每箱件数", "number of pieces", "pieces per carton", "pcs/ctn", "qty/ctn", "每箱数量", "pcs per carton", "单箱产品申报数量", "单箱数量", "每箱申报数量"],
    "pieces": ["计价件数", "total pieces", "total qty", "total quantity", "pieces", "pcs", "数量", "quantity", "qty", "产品申报总数量", "总数量"],
    "unit_price": ["unit price", "price", "单价", "unit price(usd)", "price/usd", "产品申报单价", "申报单价"],
    "amount": ["total amount", "amount", "金额", "总金额", "total price", "total value", "产品申报总价值", "申报总价值", "总价值"],
    "gross_weight": ["gross weight", "g.w.", "g.w", "gw", "毛重", "gross", "产品重量", "单件重量", "重量(kg)", "重量（kg）"],
    "net_weight": ["net weight", "n.w.", "n.w", "nw", "净重", "net"],
    "cbm": ["cbm", "volume", "方数", "体积", "measurement"],
    "dimensions": ["l*w*h", "l×w×h", "meas", "measurement(cm)", "尺寸", "外箱尺寸"],
    "length": ["length", "长", "l", "产品长度"],
    "width": ["width", "宽", "w", "产品宽度"],
    "height": ["height", "高", "h", "产品高度"],
    "packing": ["packing type", "packing", "包装类型", "包装方式", "包装"],
    "brand": ["brand", "品牌", "产品品牌"],
    "origin": ["origin", "原产国", "产地"],
    "usage": ["usage", "用途", "产品用途"],
    "processing": ["processing", "加工工艺", "工艺"],
    "scenario": ["适用场景", "scene", "application", "应用场景"],
    "supplier_name": ["供应商", "supplier", "vendor", "供应商名称"],
}

KEY_FIELDS = {"name_en", "name_zh", "hs_code", "pieces", "cartons", "unit_price", "amount", "gross_weight"}

SINGLE_LETTERS = {"l": "length", "m": "width", "h": "height", "w": "width"}


def _norm(text: Any) -> str:
    if text is None:
        return ""
    s = str(text).replace("\u00a0", " ").replace("\u3000", " ")
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _strip_punct(s: str) -> str:
    return re.sub(r"[\s:：._\-/()\[\]（）]+", "", s)


def field_scores(text: Any) -> dict[str, int]:
    """Return canonical field -> match confidence for a header cell."""
    raw = _norm(text)
    if not raw:
        return {}
    compact = _strip_punct(raw)
    out: dict[str, int] = {}
    for field, syns in FIELD_SYNONYMS.items():
        best = 0
        for syn in syns:
            ns = _norm(syn)
            cs = _strip_punct(ns)
            if not cs:
                continue
            if field in {"length", "width", "height"} and cs in SINGLE_LETTERS:
                if compact == cs:
                    best = max(best, 120)
                continue
            if compact == cs:
                best = max(best, 120)
            elif cs in compact:
                # generic words get a lower score so sub-headers win
                weight = 55 if len(cs) >= 4 else 35
                best = max(best, weight + min(len(cs), 12))
        if best:
            out[field] = best
    # 'quantity' without carton context generally means total pieces
    if "cartons" in out and "pieces" in out:
        if "箱" not in raw and "carton" not in raw and "ctn" not in raw:
            out.pop("cartons", None)
    return out


def best_field(text: Any) -> tuple[str | None, int]:
    scores = field_scores(text)
    if not scores:
        return None, 0
    field = max(scores, key=lambda k: scores[k])
    return field, scores[field]


def _num(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    s = str(value)
    s = s.replace("\u00a0", " ").replace(",", "").replace("，", "")
    s = re.sub(r"(?i)(usd|rmb|cny|aud|sgd|eur|hkd|kg|kgs|pcs|ctns|cartons|cbm|m3|m³)", "", s)
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _int(value: Any) -> int:
    n = _num(value)
    if n is None:
        return 0
    return int(round(n))


def normalize_hs(value: Any) -> str:
    if value is None:
        return ""
    s = str(value)
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 10:
        return digits[:10]
    m = re.search(r"\b(\d{4})[.\s]?(\d{2})[.\s]?(\d{2})[.\s]?(\d{0,2})\b", s)
    if m:
        return "".join(g for g in m.groups() if g)
    return s.strip()


def normalize_date(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    m = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})", s)
    if m:
        # prefer DD/MM/YYYY when unambiguous, otherwise MM/DD
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        d, mo = (a, b) if a > 12 else (b, a)
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return s


def clean_name(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip(" :：-")
    # drop pure labels
    if _norm(s) in {"total", "total:", "合计", "小计", "subtotal", "description", "品名"}:
        return ""
    return s


CJK_RE = re.compile(r"[\u3400-\u9fff\u3000-\u303f\uff00-\uffef]")


def split_bilingual_name(value: Any) -> tuple[str, str]:
    """Split 'Metal Dining Chair 金属餐椅' into an EN + ZH pair."""
    s = clean_name(value)
    if not s:
        return "", ""
    has_cjk = bool(re.search(r"[\u3400-\u9fff]", s))
    has_latin = bool(re.search(r"[A-Za-z]", s))
    if not (has_cjk and has_latin):
        return (s if has_latin and not has_cjk else ""), (s if has_cjk else "")
    zh = "".join(re.findall(r"[\u3400-\u9fff]+", s))
    en = re.sub(r"[\u3400-\u9fff]+", " ", s)
    en = re.sub(r"[，、。；：（）【】]+", " ", en)
    en = re.sub(r"\s+", " ", en).strip(" -/|,;")
    return en, zh


def _clean_value(key: str, value: Any) -> str:
    if value is None:
        return ""
    s = str(value).replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip(" :：|/-")
    # remove leading label fragments
    labels = {
        "destination": ["destination", "port of discharge", "目的港", "目的地"],
        "loading_port": ["port of loading", "loading port", "装运港", "起运港", "from"],
        "consignee": ["buyer / 收货人", "buyer", "consignee", "收货人", "买方"],
        "supplier_name": ["seller", "shipper", "exporter", "supplier", "卖方", "供应商", "发货人"],
        "contract_no": ["contract no.", "contract no", "contract number", "合同号码", "合同号", "no."],
        "invoice_no": ["invoice no.", "invoice no", "invoice number", "发票号码", "发票号"],
        "date": ["date", "日期", "invoice date"],
        "incoterm": ["incoterm", "trade terms", "价格条款", "成交方式"],
        "packing": ["packing", "packing type", "包装方式", "包装类型"],
        "signed_at": ["signed at", "签署地"],
    }.get(key, [])
    low = s.lower()
    for lab in labels:
        lab_low = lab.lower()
        if low.startswith(lab_low):
            s = s[len(lab):].lstrip(" :：/|-")
            low = s.lower()
    # take a sensible segment if a whole metadata row got captured
    if "|" in s:
        parts = [p.strip() for p in s.split("|") if p.strip()]
        for p in parts:
            pl = p.lower()
            if any(pl.startswith(lab.lower()) for lab in labels):
                continue
            s = p
            break
    # inline label inside a concatenated row
    for lab in labels:
        m = re.search(rf"(?i)(?:^|\s){re.escape(lab)}\s*[:：]\s*([^|]+)", s)
        if m:
            s = m.group(1).strip(" :：|/-")
            break
    if key in {"destination", "loading_port"}:
        s = re.split(r"(?i)\s{2,}(?:PAYMENT|ORIGIN|PORT|DESTINATION|TERMS)\b", s)[0].strip()
        s = re.split(r"(?i)\s+(?:PAYMENT|ORIGIN|TERMS)\s*[:：]", s)[0].strip()
        s = re.split(r"(?i)\s+(?:PAYMENT|ORIGIN|TERMS)\b", s)[0].strip()
        if key == "loading_port":
            s = re.split(r"(?i)\s+DESTINATION\s*[:：]", s)[0].strip()
            s = re.split(r"(?i)\s+DESTINATION\b", s)[0].strip()
        s = re.sub(r"(?i)\s+(?:DESTINATION|PORT OF DISCHARGE)\s*[:：].*$", "", s).strip(" :：|/-")
        # if the value contains the whole metadata line, pick the labelled fragment
        lab = "PORT OF LOADING|装运港|起运港" if key == "loading_port" else "DESTINATION|目的地|PORT OF DISCHARGE"
        m = re.search(rf"(?i)(?:{lab})\s*[:：]?\s*([^|\n]+?)(?=\s{{2,}}(?:PAYMENT|ORIGIN|PORT|DESTINATION|TERMS|PAYMENT)|$)", s)
        if m:
            s = m.group(1).strip(" :：|/-")
        s = re.sub(r"(?i)\b(PAYMENT|ORIGIN|TERMS)\s*[:：].*$", "", s).strip(" :：|/-")
    if key == "packing":
        s = re.sub(r"(?i)\bSHIPPING\s*MARK\b.*$", "", s)
        s = re.sub(r"(?i)\bORIGIN\b.*$", "", s)
        s = re.sub(r"\s*/\s*", " / ", s)
        s = re.sub(r"(?i)EXPORT\s*CARTON", "EXPORT CARTON", s)
    if key == "contract_no":
        s = re.sub(r"(?i)^(NO\.?|CONTRACT\s*NO\.?)\s*[:：]?\s*", "", s)
    if key == "consignee":
        s = re.split(r"(?i)\s+Date\s*[:：]?", s)[0].strip()
    return s[:160].strip()


def detect_company(text: str) -> str:
    if not text:
        return ""
    # prefer explicit seller/shipper lines
    for line in [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]:
        if re.match(r"(?i)^(seller|shipper|exporter|supplier|卖方|供应商|发货人)\s*[:：]", line):
            v = re.sub(r"(?i)^(seller|shipper|exporter|supplier|卖方|供应商|发货人)\s*[:：]\s*", "", line)
            v = re.split(r"\s{2,}|\||CONTRACT|INVOICE|BUYER", v)[0].strip()
            if v:
                return v[:140]
    patterns = [
        r"([A-Z][A-Z0-9&.,'()\- ]{2,90}?(?:CO\.,?\s*LTD\.?|CO\.,?\s*LIMITED|COMPANY LIMITED|LIMITED|LTD\.?))",
        r"([\u4e00-\u9fa5（）()A-Za-z0-9 ]{2,50}(?:有限公司|有限责任公司|股份有限公司|公司))",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            cand = re.sub(r"\s+", " ", m.group(1)).strip(" .,-")
            if len(cand) >= 4 and not re.search(r"(?i)INVOICE|CONTRACT|PACKING|TOTAL|BUYER|SELLER", cand):
                return cand[:140]
    return ""


def looks_numeric_row(row: list[Any]) -> bool:
    nums = 0
    for v in row:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            nums += 1
        elif isinstance(v, str) and re.fullmatch(r"\s*[\d,.\-]+\s*", v or ""):
            nums += 1
    return nums >= max(2, len(row) // 3)


# ---------------------------------------------------------------------------
# table analysis
# ---------------------------------------------------------------------------
def row_text(row: list[Any]) -> str:
    return " ".join(str(v) for v in row if v is not None)


def is_total_row(row: list[Any]) -> bool:
    t = _norm(row_text(row))
    if not t:
        return False
    patterns = ["total", "subtotal", "grand total", "合计", "总计", "小计", "合 计", "t o t a l"]
    if any(p in t for p in patterns):
        # avoid treating an item description containing 'total' as total
        return True
    return False


def is_empty_row(row: list[Any]) -> bool:
    return all(v is None or (isinstance(v, str) and not v.strip()) for v in row)


def header_candidates(grid: list[list[Any]]) -> list[dict]:
    out = []
    limit = min(len(grid), 45)
    for i in range(limit):
        row = grid[i]
        hits: dict[str, int] = {}
        for cell in row:
            for f, s in field_scores(cell).items():
                hits[f] = max(hits.get(f, 0), s)
        if len(hits) < 3:
            continue
        key_hits = len(set(hits) & KEY_FIELDS)
        if key_hits < 2:
            continue
        # Row with lots of numbers is data, not header
        if looks_numeric_row(row):
            continue
        score = sum(hits.values()) + 25 * len(hits) + 10 * key_hits
        out.append({"row": i, "hits": hits, "score": score})
    out.sort(key=lambda x: (-x["score"], x["row"]))
    return out


def effective_header(parent: Any, sub: Any) -> str:
    p = _norm(parent)
    s = _norm(sub)
    if s:
        f, sc = best_field(s)
        if f and sc >= 55:
            # a precise sub-header (英文品名/L/CBM/Unit Price) wins over merged parent
            return str(sub)
        if p and s != p:
            return f"{parent} {sub}"
        return str(sub or parent or "")
    return str(parent or "")


def build_columns(grid: list[list[Any]], hi: int, use_sub: bool, doc_type: str) -> tuple[dict[str, int], list[str], int]:
    parent = grid[hi]
    sub = grid[hi + 1] if use_sub and hi + 1 < len(grid) else []
    width = max(len(parent), len(sub))
    headers = [effective_header(parent[c] if c < len(parent) else None, sub[c] if c < len(sub) else None) for c in range(width)]
    candidates = []
    for c, text in enumerate(headers):
        for field, score in field_scores(text).items():
            candidates.append((score, field, c))
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    fields: dict[str, int] = {}
    used_cols: set[int] = set()
    for score, field, c in candidates:
        if field in fields or c in used_cols:
            continue
        fields[field] = c
        used_cols.add(c)
    # doc-type disambiguation: a generic 'quantity' column on a packing list is cartons
    if doc_type == "packing_list" and "cartons" not in fields and "pieces" in fields and "pieces_per_carton" not in fields:
        fields["cartons"] = fields.pop("pieces")
    # name fallback: description column can be zh or en depending on content
    if "name_en" not in fields and "name_zh" in fields:
        fields["name_en"] = fields["name_zh"]
    if "name_zh" not in fields and "name_en" in fields:
        fields["name_zh"] = fields["name_en"]
    return fields, headers, (hi + (2 if use_sub else 1))


def analyze_table(grid: list[list[Any]], source: dict, doc_type_hint: str | None = None) -> dict:
    grid = [list(r) for r in grid if r is not None]
    if len(grid) < 2:
        return {"ok": False, "items": [], "reason": "表格行数不足"}
    tops = header_candidates(grid)
    if not tops:
        return {"ok": False, "items": [], "reason": "未识别到表头（缺少品名/HS/数量/金额等列）"}
    chosen = None
    for cand in tops[:4]:
        hi = cand["row"]
        use_sub = False
        if hi + 1 < len(grid):
            sub_hits: dict[str, int] = {}
            for cell in grid[hi + 1]:
                for f, s in field_scores(cell).items():
                    sub_hits[f] = max(sub_hits.get(f, 0), s)
            if len(sub_hits) >= 2 and not looks_numeric_row(grid[hi + 1]):
                use_sub = True
        # type inference from headers
        text = " ".join(str(c) for c in grid[hi] if c)
        type_hint = doc_type_hint or infer_type(text)
        fields, headers, data_start = build_columns(grid, hi, use_sub, type_hint)
        if len(fields) < 3:
            continue
        has_price = bool({"unit_price", "amount"} & set(fields))
        has_pack = bool({"gross_weight", "net_weight", "cbm", "dimensions", "length", "width", "height", "packing"} & set(fields))
        if has_price and has_pack:
            table_type = "combined"
        elif has_price:
            table_type = "invoice"
        elif has_pack:
            table_type = "packing_list"
        else:
            table_type = type_hint
        items = parse_data_rows(grid, data_start, fields, source, table_type)
        if items:
            chosen = {
                "ok": True, "items": items, "header_row": hi + 1, "header_rows": 2 if use_sub else 1,
                "headers": headers, "columns": {k: v for k, v in fields.items()},
                "data_start": data_start + 1, "doc_type": table_type,
                "score": cand["score"] + len(items) * 6,
            }
            break
    if not chosen:
        return {"ok": False, "items": [], "reason": "表头已定位但数据行无法标准化"}
    return chosen


def infer_type(text: str) -> str:
    t = _norm(text)
    packing = any(k in t for k in ["packing", "装箱", "packing list", "carton", "毛重"])
    invoice = any(k in t for k in ["invoice", "发票", "unit price", "amount", "金额"])
    if packing and invoice:
        return "combined"
    if invoice:
        return "invoice"
    if packing:
        return "packing_list"
    return "unknown"


def parse_data_rows(grid: list[list[Any]], start: int, fields: dict[str, int], source: dict, doc_type: str) -> list[dict]:
    items: list[dict] = []
    blanks = 0
    seq = 0
    last_supplier = ""
    for i in range(start, len(grid)):
        row = grid[i]
        if is_empty_row(row):
            blanks += 1
            if blanks >= 3 and items:
                break
            continue
        blanks = 0
        if is_total_row(row):
            if items:
                break
            continue
        if header_candidates([row]):
            continue
        def get(field: str) -> Any:
            c = fields.get(field)
            if c is None or c >= len(row):
                return None
            return row[c]
        name_en = clean_name(get("name_en"))
        name_zh = clean_name(get("name_zh"))
        if name_en and not name_zh:
            e, z = split_bilingual_name(name_en)
            name_en, name_zh = (e or name_en), z
        elif name_zh and not name_en:
            e, z = split_bilingual_name(name_zh)
            name_en, name_zh = e, (z or name_zh)
        elif name_en and name_zh and (name_en == name_zh or re.search(r"[\u3400-\u9fff]", name_en) or (not re.search(r"[\u3400-\u9fff]", name_zh) and re.search(r"[A-Za-z]", name_zh))):
            e, z = split_bilingual_name(name_en if re.search(r"[\u3400-\u9fff]", name_en) else name_zh)
            name_en = e or name_en
            name_zh = z or name_zh
        model = clean_name(get("model"))
        hs = normalize_hs(get("hs_code"))
        supplier_raw = clean_name(get("supplier_name"))
        if supplier_raw:
            last_supplier = supplier_raw
        else:
            supplier_raw = last_supplier
        dims = clean_name(get("dimensions"))
        l = _num(get("length")) or 0.0
        w = _num(get("width")) or 0.0
        h = _num(get("height")) or 0.0
        if dims and not (l and w and h):
            nums = re.findall(r"\d+(?:\.\d+)?", dims)
            if len(nums) >= 3:
                l, w, h = float(nums[0]), float(nums[1]), float(nums[2])
        cartons = _int(get("cartons"))
        ppc = _int(get("pieces_per_carton"))
        pieces = _int(get("pieces"))
        unit_price = _num(get("unit_price")) or 0.0
        amount = _num(get("amount")) or 0.0
        gross = _num(get("gross_weight")) or 0.0
        net = _num(get("net_weight")) or 0.0
        cbm = _num(get("cbm")) or 0.0
        if not (name_en or name_zh or model):
            continue
        # skip decorative header echo rows
        if _norm(name_en) in {"description", "english description"} and not cartons and not amount:
            continue
        if pieces == 0 and ppc and cartons:
            pieces = ppc * cartons
        if ppc == 0 and pieces and cartons:
            ppc = int(round(pieces / cartons))
        if cartons == 0 and pieces and ppc:
            cartons = int(round(pieces / ppc))
        if amount == 0 and unit_price and pieces:
            amount = round(unit_price * pieces, 2)
        if unit_price == 0 and amount and pieces:
            unit_price = round(amount / pieces, 4)
        if cbm == 0 and l and w and h and cartons:
            cbm = round(l * w * h / 1_000_000 * cartons, 4)
        # discard obvious subtotal decimals stuck in quantity
        if not (cartons or pieces or amount or gross or unit_price):
            # still keep a named item if it is explicitly present (price-only docs)
            if not (name_en or name_zh):
                continue
        seq += 1
        item = {
            "id": f"it_{seq}",
            "no": clean_name(get("no")) or str(seq),
            "model": model,
            "name_en": name_en,
            "name_zh": name_zh,
            "hs_code": hs,
            "material": clean_name(get("material")),
            "brand": clean_name(get("brand")),
            "origin": clean_name(get("origin")),
            "usage": clean_name(get("usage")),
            "processing": clean_name(get("processing")),
            "scenario": clean_name(get("scenario")),
            "row_supplier": supplier_raw,
            "supplier_name_raw": supplier_raw,
            "cartons": cartons,
            "pieces_per_carton": ppc,
            "pieces": pieces,
            "unit_price": unit_price,
            "amount": amount,
            "gross_weight": gross,
            "net_weight": net,
            "cbm": cbm,
            "length": l,
            "width": w,
            "height": h,
            "packing": clean_name(get("packing")),
            "packages": cartons,
            "source_type": doc_type,
            "source_file": source.get("filename", ""),
            "source_page": source.get("page"),
            "source_sheet": source.get("sheet"),
            "raw": {str(k): str(v) for k, v in zip(fields.keys(), [row[c] if c < len(row) else None for c in fields.values()]) if v is not None},
        }
        items.append(item)
    return dedupe_items(items)


def key_for_item(it: dict) -> str:
    en = re.sub(r"[\u3400-\u9fff]+", " ", _norm(it.get("name_en")))
    en = re.sub(r"\s+", " ", en).strip()
    name = en or _norm(it.get("name_zh")) or _norm(it.get("model"))
    return f"{name}|{it.get('hs_code', '')}"


def dedupe_items(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for it in items:
        sig = (
            key_for_item(it), it.get("cartons"), it.get("pieces_per_carton"), it.get("pieces"),
            round(float(it.get("amount") or 0), 2), round(float(it.get("gross_weight") or 0), 3),
        )
        if sig in seen:
            continue
        seen.add(sig)
        out.append(it)
    return out


# ---------------------------------------------------------------------------
# document fields
# ---------------------------------------------------------------------------
LABEL_PATTERNS = {
    "invoice_no": ["invoice no", "invoice number", "发票号码", "发票号", "inv no"],
    "contract_no": ["contract no", "contract number", "合同号码", "合同号", "contract"],
    "date": ["date", "日期", "invoice date"],
    "destination": ["destination", "port of discharge", "目的港", "目的地", "delivery to"],
    "loading_port": ["port of loading", "loading port", "装运港", "起运港", "from"],
    "incoterm": ["incoterm", "trade terms", "价格条款", "成交方式"],
    "vessel": ["vessel", "vessel name", "船名", "船名航次"],
    "bl_no": ["b/l no", "bill of lading", "提单号", "提单号码"],
    "payment_terms": ["payment terms", "付款条件", "payment"],
    "currency": ["currency", "币种"],
    "supplier_name": ["seller", "shipper", "exporter", "supplier", "卖方", "供应商", "发货人"],
    "consignee": ["consignee", "buyer", "收货人", "买方", "to"],
}


def _line_value(text: str, labels: list[str], max_len: int = 120) -> str:
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    for i, line in enumerate(lines):
        low = _norm(line)
        for label in labels:
            lab = _norm(label)
            if not lab:
                continue
            if low.startswith(lab) or re.match(rf"^{re.escape(lab)}\s*[:：]", low):
                # inline value after the label
                rest = re.sub(rf"(?i)^{re.escape(label)}\s*[:：]?\s*", "", line).strip()
                if rest and not _looks_like_label_only(rest):
                    return rest[:max_len]
                # next non-empty line
                for j in range(i + 1, min(i + 3, len(lines))):
                    cand = lines[j].strip()
                    if cand and not _looks_like_label_only(cand):
                        return cand[:max_len]
    return ""


def _looks_like_label_only(s: str) -> bool:
    t = _norm(s)
    return t in {"", ":", "：", "to", "from", "date", "no", "n/a"}


def extract_fields_from_text(text: str, filename: str = "") -> dict:
    text = text or ""
    fields: dict[str, Any] = {}
    m = re.search(r"(?i)(?:invoice\s*(?:no|number)|发票号码?)\s*[.:：]?\s*([A-Z0-9][A-Z0-9\-_/]{2,30})", text)
    if m:
        fields["invoice_no"] = m.group(1).strip()
    m = re.search(r"(?i)(?:contract\s*(?:no|number)|合同号码?)\s*[.:：]?\s*([A-Z0-9][A-Z0-9\-_/]{2,40})", text)
    if m:
        fields["contract_no"] = m.group(1).strip()
    m = re.search(r"(?i)(?:date|日期)\s*[.:：]?\s*((?:20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})|(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}))", text)
    if m:
        fields["date"] = normalize_date(m.group(1))
    for key, labels in {
        "destination": ["destination", "port of discharge", "目的港", "目的地"],
        "loading_port": ["port of loading", "loading port", "装运港", "起运港"],
        "vessel": ["vessel", "船名"],
        "bl_no": ["b/l no", "bill of lading", "提单号"],
        "payment_terms": ["payment terms", "付款条件"],
    }.items():
        v = _line_value(text, labels)
        if v:
            fields[key] = v
    if not fields.get("loading_port"):
        m = re.search(r"(?i)(?:PORT\s+OF\s+LOADING|装运港|起运港)\s*[:：]?\s*([A-Z][A-Z ,()\.\-]{2,60})", text)
        if m:
            fields["loading_port"] = m.group(1).strip(" ,")
    if not fields.get("destination"):
        m = re.search(r"(?i)(?:DESTINATION|PORT\s+OF\s+DISCHARGE|目的地|目的港)\s*[:：]?\s*([A-Z][A-Z ,()\.\-]{2,60})", text)
        if m:
            fields["destination"] = m.group(1).strip(" ,")
    if not fields.get("address"):
        for line in [re.sub(r"\s+", " ", x).strip() for x in text.splitlines()]:
            if len(line) < 18:
                continue
            low = line.lower()
            if low.startswith(("destination", "buyer", "consignee", "origin", "port", "payment", "invoice", "shipping", "total")):
                continue
            if re.search(r"(?i)(ROAD|STREET|DISTRICT|ZHEJIANG|GUANGDONG|PROVINCE|BUSINESS CENTER|BUILDING|AUSTRALIA)", line) and not re.search(r"(?i)INVOICE|PHONE|TEL|EMAIL|BANK|TOTAL", line):
                fields["address"] = re.split(r"(?i)\s+(?:CONTRACT|INVOICE|TEL|EMAIL|DATE)\b", line)[0].strip()
                break
    if not fields.get("buyer_address"):
        lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines()]
        for i, line in enumerate(lines):
            if re.search(r"(?i)(BUYER|CONSIGNEE|收货人|买方)", line):
                for nxt in lines[i + 1:i + 4]:
                    if re.search(r"(?i)(ROAD|STREET|DRIVE|DISTRICT|VIC|AUSTRALIA)", nxt):
                        fields["buyer_address"] = nxt
                        break
                break
    m = re.search(r"(?i)\b(CIF|FOB|CFR|EXW|DDP|DAP|FCA)\b", text)
    if m:
        fields["incoterm"] = m.group(1).upper()
    m = re.search(r"(?i)\b(USD|CNY|RMB|AUD|EUR|HKD|SGD)\b", text)
    if m:
        fields["currency"] = "CNY" if m.group(1).upper() == "RMB" else m.group(1).upper()
    m = re.search(r"(?i)(?:total\s*(?:amount|value)|总金额|合计金额)\s*[.:：]?\s*(?:USD|CNY|\$)?\s*([\d,]+\.\d{2})", text)
    if m:
        fields["total_amount"] = _num(m.group(1)) or 0
    m = re.search(r"(?i)(?:total\s*(?:cartons|packages)|总箱数|合计箱数)\s*[.:：]?\s*([\d,]+)", text)
    if m:
        fields["total_cartons"] = _int(m.group(1))
    m = re.search(r"(?i)(?:total\s*(?:pieces|quantity)|总件数|合计件数)\s*[.:：]?\s*([\d,]+)", text)
    if m:
        fields["total_pieces"] = _int(m.group(1))
    m = re.search(r"(?i)(?:gross\s*weight|毛重|g\.w\.)\s*[.:：]?\s*([\d,]+(?:\.\d+)?)\s*(?:kgs?)?", text)
    if m:
        fields["total_gross"] = _num(m.group(1)) or 0
    m = re.search(r"(?i)(?:net\s*weight|净重|n\.w\.)\s*[.:：]?\s*([\d,]+(?:\.\d+)?)\s*(?:kgs?)?", text)
    if m:
        fields["total_net"] = _num(m.group(1)) or 0
    m = re.search(r"(?i)(?:total\s*(?:cbm|volume)|总体积)\s*[.:：]?\s*([\d,]+(?:\.\d+)?)", text)
    if m:
        fields["total_cbm"] = _num(m.group(1)) or 0
    containers = list(dict.fromkeys(re.findall(r"\b[A-Z]{4}\d{7}\b", text)))
    if containers:
        fields["container_no"] = ", ".join(containers)
    m = re.search(r"(?i)\bCBM\s*[:：]?\s*([\d,]+(?:\.\d+)?)", text)
    if m:
        fields["total_cbm"] = _num(m.group(1)) or 0
    m = re.search(r"(?i)(?:PACKING|包装方式|包装类型)\s*[:：]\s*([^|\n]+)", text)
    if m:
        fields["packing"] = _clean_value("packing", m.group(1))
    # supplier / consignee
    sup = _line_value(text, ["seller", "shipper", "exporter", "supplier", "卖方", "供应商", "发货人"])
    company = detect_company(text)
    if company and (not sup or len(sup) < 4):
        sup = company
    if sup and len(sup) > 3 and not _norm(sup).startswith("address"):
        fields["supplier_name"] = _clean_value("supplier_name", sup)
    elif company:
        fields["supplier_name"] = company
    if fields.get("supplier_name"):
        fields.setdefault("supplier_name_en", fields["supplier_name"])
    mzh = re.search(r"([\u4e00-\u9fa5（）()]{2,40}(?:有限公司|有限责任公司|股份有限公司|公司))", text[:3000])
    if mzh:
        fields["supplier_name_zh"] = mzh.group(1)
    con = _line_value(text, ["consignee", "buyer", "收货人", "买方"])
    if con:
        fields["consignee"] = _clean_value("consignee", con)
    # Address after address label
    addr = _line_value(text, ["address", "地址"])
    if addr:
        fields["address"] = addr
    if not fields.get("date"):
        m = re.search(r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})", text)
        if m:
            fields["date"] = normalize_date(m.group(1))
    # clean metadata and derive country shortcuts
    for key in ("invoice_no", "contract_no", "date", "destination", "loading_port", "incoterm",
                "consignee", "supplier_name", "packing", "vessel", "bl_no", "payment_terms", "address", "buyer_address"):
        if key in fields:
            val = _clean_value(key, fields[key])
            if key == "date":
                val = normalize_date(val)
            fields[key] = val
    dest = fields.get("destination", "")
    if re.search(r"(?i)australia|澳大利亚|澳洲", dest + " " + text[:3000]):
        fields["destination_country"] = "AUSTRALIA"
    if re.search(r"(?i)\bchina\b|中国", text[:3000]):
        fields["origin_country"] = "CHINA"
    if fields.get("destination") and not fields.get("destination_port"):
        fields["destination_port"] = fields["destination"]
    return fields


def extract_fields_from_grid(grid: list[list[Any]]) -> dict:
    """Label/value handling for Excel layouts."""
    fields: dict[str, Any] = {}
    for row in grid:
        cells = [c for c in row]
        for idx, cell in enumerate(cells):
            if cell is None:
                continue
            t = _norm(cell)
            if not t:
                continue
            for key, labels in LABEL_PATTERNS.items():
                if key in fields:
                    continue
                for label in labels:
                    lab = _norm(label)
                    if t == lab or t.startswith(lab + " ") or t.startswith(lab + ":") or t.startswith(lab + "："):
                        # inline after colon
                        rest = re.sub(rf"(?i)^{re.escape(label)}\s*[:：]?\s*", "", str(cell)).strip()
                        if rest and not _looks_like_label_only(rest) and not re.fullmatch(r"(?i)no\.?|date|to|from", rest):
                            fields[key] = rest
                            break
                        for j in range(idx + 1, min(idx + 5, len(cells))):
                            v = cells[j]
                            if isinstance(v, (int, float)) and not isinstance(v, bool):
                                fields[key] = v
                                break
                            if isinstance(v, str) and v.strip():
                                fields[key] = v.strip()
                                break
                        break
    # normalize
    for key in ("invoice_no", "contract_no", "date", "destination", "loading_port", "incoterm",
                "consignee", "supplier_name", "packing"):
        if key in fields:
            val = _clean_value(key, fields[key])
            if key == "date":
                val = normalize_date(val)
            fields[key] = val
    grid_text = "\n".join(" ".join(str(c) for c in row if c is not None) for row in grid)
    company = detect_company(grid_text)
    cur = fields.get("supplier_name", "")
    if company and (not cur or len(cur) > 90 or "|" in str(cur) or "SELLER" in str(cur).upper()):
        fields["supplier_name"] = company
    if fields.get("supplier_name"):
        fields.setdefault("supplier_name_en", fields["supplier_name"])
    mzh = re.search(r"([\u4e00-\u9fa5（）()]{2,40}(?:有限公司|有限责任公司|股份有限公司|公司))", grid_text[:4000])
    if mzh:
        fields["supplier_name_zh"] = mzh.group(1)
    dest = str(fields.get("destination", "")) + " " + grid_text[:4000]
    if re.search(r"(?i)australia|澳大利亚|澳洲", dest):
        fields["destination_country"] = "AUSTRALIA"
    if re.search(r"(?i)\bchina\b|中国", grid_text[:4000]):
        fields["origin_country"] = "CHINA"
    if fields.get("destination") and not fields.get("destination_port"):
        fields["destination_port"] = fields["destination"]
    return fields


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def _safe_extract_tables(page) -> list[list[list[Any]]]:
    tables = []
    for settings in (
        {"vertical_strategy": "lines", "horizontal_strategy": "lines", "intersection_tolerance": 5},
        {"vertical_strategy": "text", "horizontal_strategy": "text", "intersection_tolerance": 6},
    ):
        try:
            got = page.extract_tables(settings)
        except Exception:
            got = []
        for t in got or []:
            if t and len(t) >= 2:
                tables.append(t)
        if tables:
            break
    return tables


def _table_bbox(page, table) -> list[float] | None:
    try:
        found = page.find_tables()
        best = None
        best_area = -1
        for ft in found:
            x0, top, x1, bottom = ft.bbox
            area = (x1 - x0) * (bottom - top)
            if area > best_area:
                best_area = area
                best = [round(x0, 2), round(top, 2), round(x1, 2), round(bottom, 2)]
        return best
    except Exception:
        return None


def parse_pdf(path: Path, filename: str) -> dict:
    import pdfplumber

    pages_meta = []
    sections = []
    all_text = []
    warnings = []
    with pdfplumber.open(str(path)) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            all_text.append(text)
            words = page.extract_words(extra_attrs=["size", "fontname"]) or []
            tables = _safe_extract_tables(page)
            page_type = infer_type(text[:1200])
            page_tables = []
            for tno, table in enumerate(tables):
                source = {"filename": filename, "page": pno, "table": tno + 1}
                res = analyze_table(table, source, page_type if page_type != "unknown" else None)
                page_tables.append({
                    "table": tno + 1,
                    "rows": len(table),
                    "cols": max((len(r) for r in table), default=0),
                    "bbox": _table_bbox(page, table),
                    "header_row": res.get("header_row"),
                    "recognized": bool(res.get("ok")),
                    "reason": res.get("reason"),
                    "headers": res.get("headers", []),
                })
                if res.get("ok"):
                    sec = {
                        "doc_type": res.get("doc_type") or page_type,
                        "items": res["items"],
                        "fields": extract_fields_from_text(text, filename),
                        "page": pno,
                        "table": tno + 1,
                        "headers": res.get("headers", []),
                    }
                    sections.append(sec)
            pages_meta.append({
                "page": pno,
                "width": round(float(page.width), 2),
                "height": round(float(page.height), 2),
                "chars": len(text),
                "words": len(words),
                "tables": page_tables,
                "word_sample": [
                    {"text": w.get("text"), "x0": round(float(w.get("x0", 0)), 1), "top": round(float(w.get("top", 0)), 1)}
                    for w in words[:60]
                ],
            })
    text = "\n\n".join(all_text)
    fields = extract_fields_from_text(text, filename)
    if not sections:
        # fallback: reconstruct lines from words and try a borderless table
        fallback = _parse_borderless_pdf(path, filename)
        if fallback.get("items"):
            sections.append({
                "doc_type": fallback.get("doc_type", "unknown"),
                "items": fallback["items"],
                "fields": fields,
                "page": 1,
                "table": 0,
                "headers": fallback.get("headers", []),
            })
        else:
            warnings.append("未检测到有效表格结构；已尝试坐标行聚类回退")
    if not sections:
        return {
            "ok": False,
            "error": "解析失败：未检测到有效表格结构（PDF 中未找到可标准化的表头/数据行）",
            "type": infer_type(text),
            "fields": fields,
            "items": [],
            "structure": {"format": "pdf", "pages": pages_meta, "chars": len(text), "table_count": sum(len(p["tables"]) for p in pages_meta)},
            "warnings": warnings,
            "text": text[:20000],
        }
    doc = assemble_document(sections, fields, filename, "pdf")
    doc["structure"] = {
        "format": "pdf",
        "pages": pages_meta,
        "table_count": sum(len(p["tables"]) for p in pages_meta),
        "chars": len(text),
        "coordinate_engine": "pdfplumber",
        "warnings": warnings,
    }
    doc["warnings"].extend(warnings)
    doc["text"] = text[:20000]
    return doc


def _parse_borderless_pdf(path: Path, filename: str) -> dict:
    import pdfplumber

    rows = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            words = page.extract_words() or []
            if not words:
                continue
            line_map: dict[int, list] = {}
            for w in words:
                key = int(round(float(w["top"]) / 6))
                line_map.setdefault(key, []).append(w)
            for key in sorted(line_map):
                ws = sorted(line_map[key], key=lambda w: float(w["x0"]))
                rows.append([w["text"] for w in ws])
    if len(rows) < 3:
        return {}
    # try splitting each line into up to 12 cells by x gaps; simplest: keep as one cell
    matrix = [rows[i] for i in range(len(rows))]
    res = analyze_table(matrix, {"filename": filename, "page": 1}, None)
    return res


# ---------------------------------------------------------------------------
# assembling a standardized document
# ---------------------------------------------------------------------------
def _merge_item_fields(a: dict, b: dict, packing_first: bool = True) -> dict:
    out = dict(a)
    qty_fields = {"cartons", "pieces_per_carton", "pieces", "gross_weight", "net_weight", "cbm", "length", "width", "height", "packing"}
    price_fields = {"unit_price", "amount"}
    for k, v in b.items():
        if k in {"id", "raw", "source_file", "source_page", "source_sheet", "source_type", "sources"}:
            continue
        if v in (None, "", 0, 0.0) and out.get(k) not in (None, "", 0, 0.0):
            continue
        if k in qty_fields:
            if packing_first:
                if out.get(k) not in (None, "", 0, 0.0):
                    continue
            else:
                if out.get(k) in (None, "", 0, 0.0):
                    out[k] = v
                continue
        if k in price_fields and out.get(k) not in (None, "", 0, 0.0) and v in (None, "", 0, 0.0):
            continue
        out[k] = v
    sources = list(a.get("sources") or [])
    for s in b.get("sources") or []:
        if s not in sources:
            sources.append(s)
    if not sources:
        for it in (a, b):
            src = {"file": it.get("source_file"), "type": it.get("source_type"), "page": it.get("source_page"), "sheet": it.get("source_sheet")}
            if src["file"] and src not in sources:
                sources.append(src)
    out["sources"] = sources
    return out


def _item_key(it: dict) -> str:
    en = re.sub(r"[\u3400-\u9fff]+", " ", _norm(it.get("name_en")))
    en = re.sub(r"\s+", " ", en).strip()
    return (en or _norm(it.get("name_zh")) or _norm(it.get("model")) or f"hs-{it.get('hs_code', '')}") + "|" + str(it.get("hs_code", ""))


def assemble_document(sections: list[dict], fields: dict, filename: str, fmt: str) -> dict:
    merged_fields = dict(fields)
    for sec in sections:
        for k, v in (sec.get("fields") or {}).items():
            if v not in (None, "", 0, 0.0) and merged_fields.get(k) in (None, "", 0, 0.0):
                merged_fields[k] = v
    packing_items: list[dict] = []
    invoice_items: list[dict] = []
    other_items: list[dict] = []
    for sec in sections:
        st = sec.get("doc_type") or "unknown"
        for it in sec.get("items") or []:
            it = dict(it)
            it["source_type"] = st
            it.setdefault("sources", [])
            if not it["sources"]:
                it["sources"].append({"file": filename, "type": st, "page": sec.get("page"), "sheet": sec.get("page") if fmt == "xlsx" else None})
            if st in {"packing_list", "combined"} and any(it.get(k) for k in ("cartons", "pieces", "gross_weight", "cbm")):
                packing_items.append(it)
            if st in {"invoice", "combined"} and any(it.get(k) for k in ("unit_price", "amount")):
                invoice_items.append(it)
            if st == "unknown":
                other_items.append(it)
    # exact duplicate removal within each bucket
    packing_items = dedupe_items(packing_items)
    invoice_items = dedupe_items(invoice_items)
    other_items = dedupe_items(other_items)

    final: list[dict] = []
    used_invoice: set[int] = set()
    used_packing: set[int] = set()
    if packing_items and invoice_items:
        for pi, pack in enumerate(packing_items):
            key = _item_key(pack)
            match = None
            for ii, inv in enumerate(invoice_items):
                if ii in used_invoice:
                    continue
                ikey = _item_key(inv)
                if not key or not ikey:
                    continue
                if key == ikey or (pack.get("hs_code") and pack.get("hs_code") == inv.get("hs_code") and (
                        _norm(pack.get("name_zh")) == _norm(inv.get("name_zh")) or _norm(pack.get("name_en")) == _norm(inv.get("name_en")))):
                    match = ii
                    break
            if match is not None:
                used_invoice.add(match)
                used_packing.add(pi)
                final.append(_merge_item_fields(pack, invoice_items[match], packing_first=True))
            else:
                used_packing.add(pi)
                final.append(pack)
        for ii, inv in enumerate(invoice_items):
            if ii not in used_invoice:
                final.append(inv)
    else:
        final = packing_items or invoice_items or other_items
    # preserve any leftovers
    for pi, it in enumerate(packing_items):
        if pi not in used_packing and it not in final and not any(it is x for x in final):
            if not any(_item_key(x) == _item_key(it) for x in final):
                final.append(it)
    for it in other_items:
        if not any(_item_key(x) == _item_key(it) for x in final):
            final.append(it)

    # normalize / compute derived fields
    for idx, it in enumerate(final, start=1):
        it["id"] = f"it_{idx:03d}"
        it.setdefault("sources", [])
        it["cartons"] = int(it.get("cartons") or 0)
        it["pieces_per_carton"] = int(it.get("pieces_per_carton") or 0)
        it["pieces"] = int(it.get("pieces") or 0)
        if not it["pieces"] and it["pieces_per_carton"] and it["cartons"]:
            it["pieces"] = it["pieces_per_carton"] * it["cartons"]
        if not it["pieces_per_carton"] and it["pieces"] and it["cartons"]:
            it["pieces_per_carton"] = int(round(it["pieces"] / it["cartons"]))
        it["unit_price"] = round(float(it.get("unit_price") or 0), 4)
        it["amount"] = round(float(it.get("amount") or 0), 2)
        if not it["amount"] and it["unit_price"] and it["pieces"]:
            it["amount"] = round(it["unit_price"] * it["pieces"], 2)
        if not it["unit_price"] and it["amount"] and it["pieces"]:
            it["unit_price"] = round(it["amount"] / it["pieces"], 4)
        it["gross_weight"] = round(float(it.get("gross_weight") or 0), 3)
        it["net_weight"] = round(float(it.get("net_weight") or 0), 3)
        it["cbm"] = round(float(it.get("cbm") or 0), 4)
        if not it["cbm"] and it.get("length") and it.get("width") and it.get("height") and it["cartons"]:
            it["cbm"] = round(float(it["length"]) * float(it["width"]) * float(it["height"]) / 1_000_000 * it["cartons"], 4)
        it["hs_code"] = normalize_hs(it.get("hs_code"))
        it["name_en"] = clean_name(it.get("name_en"))
        it["name_zh"] = clean_name(it.get("name_zh"))
        it["model"] = clean_name(it.get("model"))

    # a product master often repeats a product on several carton lines and only
    # fills the HS column on one of them: copy a 10-digit sibling value, never guess.
    hs_by_name: dict[str, str] = {}
    for it in final:
        name = _norm(it.get("name_en")) or _norm(it.get("name_zh"))
        if name and len(str(it.get("hs_code") or "")) >= 8:
            hs_by_name.setdefault(name, str(it["hs_code"]))
    for it in final:
        if not it.get("hs_code"):
            name = _norm(it.get("name_en")) or _norm(it.get("name_zh"))
            if name and name in hs_by_name:
                it["hs_code"] = hs_by_name[name]
                it["hs_inferred_from_sibling"] = True

    doc_type = "combined" if (packing_items and invoice_items) else (packing_items and "packing_list") or (invoice_items and "invoice") or "unknown"
    totals = {
        "cartons": sum(it["cartons"] for it in final),
        "pieces": sum(it["pieces"] for it in final),
        "amount": round(sum(it["amount"] for it in final), 2),
        "gross_weight": round(sum(it["gross_weight"] for it in final), 3),
        "net_weight": round(sum(it["net_weight"] for it in final), 3),
        "cbm": round(sum(it["cbm"] for it in final), 4),
        "items": len(final),
    }
    merged_fields.setdefault("currency", "USD")
    merged_fields["total_amount"] = totals["amount"] or merged_fields.get("total_amount") or 0
    merged_fields["total_cartons"] = totals["cartons"] or merged_fields.get("total_cartons") or 0
    merged_fields["total_pieces"] = totals["pieces"] or merged_fields.get("total_pieces") or 0
    merged_fields["total_gross"] = totals["gross_weight"] or merged_fields.get("total_gross") or 0
    merged_fields["total_net"] = totals["net_weight"] or merged_fields.get("total_net") or 0
    merged_fields["total_cbm"] = totals["cbm"] or merged_fields.get("total_cbm") or 0
    merged_fields["doc_type"] = doc_type
    merged_fields["filename"] = filename
    merged_fields["format"] = fmt
    if not merged_fields.get("supplier_name"):
        merged_fields["supplier_name"] = ""
    return {
        "ok": True,
        "type": doc_type,
        "format": fmt,
        "fields": merged_fields,
        "items": final,
        "totals": totals,
        "sections": [{k: v for k, v in sec.items() if k != "items"} | {"item_count": len(sec.get("items") or [])} for sec in sections],
        "warnings": [],
        "text": "",
        "structure": {},
    }


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------
def _grid_from_sheet(ws, max_rows: int = 240, max_cols: int = 40) -> list[list[Any]]:
    merged_value: dict[tuple[int, int], Any] = {}
    for rng in ws.merged_cells.ranges:
        v = ws.cell(rng.min_row, rng.min_col).value
        for r in range(rng.min_row, min(rng.max_row, max_rows) + 1):
            for c in range(rng.min_col, min(rng.max_col, max_cols) + 1):
                merged_value[(r, c)] = v
    rows = min(ws.max_row or 1, max_rows)
    cols = min(ws.max_column or 1, max_cols)
    grid = []
    for r in range(1, rows + 1):
        row = []
        for c in range(1, cols + 1):
            v = merged_value.get((r, c), ws.cell(r, c).value)
            row.append(v)
        grid.append(row)
    # trim trailing empty rows/cols
    while grid and is_empty_row(grid[-1]):
        grid.pop()
    if grid:
        width = 0
        for row in grid:
            for i in range(len(row) - 1, -1, -1):
                if row[i] not in (None, ""):
                    width = max(width, i + 1)
                    break
        grid = [row[:width] for row in grid]
    return grid


def parse_excel(path: Path, filename: str) -> dict:
    from openpyxl import load_workbook

    wb = load_workbook(filename=str(path), data_only=True, read_only=False)
    wb_formula = load_workbook(filename=str(path), data_only=False, read_only=False)
    sections = []
    sheets_meta = []
    warnings = []
    all_grid_text: list[str] = []
    for ws in wb.worksheets:
        ws_f = wb_formula[ws.title]
        grid = _grid_from_sheet(ws)
        if not grid:
            continue
        title_text = " ".join(str(c) for c in grid[:4] for c in (c or []) if c)
        grid_text = "\n".join(" | ".join("" if v is None else str(v) for v in row) for row in grid)
        all_grid_text.append(grid_text)
        sheet_type = infer_type(ws.title + " " + title_text)
        if sheet_type == "unknown":
            sheet_type = infer_type(grid_text[:1500])
        res = analyze_table(grid, {"filename": filename, "page": ws.title, "sheet": ws.title}, sheet_type if sheet_type != "unknown" else None)
        sheets_meta.append({
            "title": ws.title,
            "dim": ws.calculate_dimension(),
            "max_row": ws.max_row,
            "max_col": ws.max_column,
            "merges": [str(r) for r in ws.merged_cells.ranges],
            "header_row": res.get("header_row"),
            "headers": res.get("headers", []),
            "recognized": bool(res.get("ok")),
            "reason": res.get("reason"),
            "item_count": len(res.get("items") or []),
            "grid_preview": [[_cell_preview(c) for c in row[:12]] for row in grid[:12]],
            "formula_cells": [
                {"coord": c.coordinate, "formula": c.value}
                for row in ws_f.iter_rows(min_row=1, max_row=min(ws_f.max_row or 1, 80), max_col=min(ws_f.max_column or 1, 24))
                for c in row
                if isinstance(c.value, str) and c.value.startswith("=")
            ][:40],
        })
        if res.get("ok"):
            fields = extract_fields_from_grid(grid)
            fields.update({k: v for k, v in extract_fields_from_text(grid_text, filename).items() if v not in (None, "", 0)})
            sections.append({
                "doc_type": res.get("doc_type") if res.get("doc_type") != "unknown" else sheet_type,
                "items": res["items"],
                "fields": fields,
                "page": ws.title,
                "table": ws.title,
                "headers": res.get("headers", []),
            })
        else:
            warnings.append(f"Sheet《{ws.title}》未识别到有效表格：{res.get('reason')}")
    if not sections:
        return {
            "ok": False,
            "error": "解析失败：未检测到有效表格结构（请确认存在品名/HS/数量/金额等表头）",
            "type": "unknown",
            "fields": {},
            "items": [],
            "structure": {"format": "xlsx", "sheets": sheets_meta},
            "warnings": warnings,
            "text": "\n\n".join(all_grid_text)[:20000],
        }
    # fields from all sheets
    fields = {}
    for sec in sections:
        for k, v in (sec.get("fields") or {}).items():
            if v not in (None, "", 0, 0.0) and fields.get(k) in (None, "", 0, 0.0):
                fields[k] = v
    doc = assemble_document(sections, fields, filename, "xlsx")
    doc["structure"] = {
        "format": "xlsx",
        "sheets": sheets_meta,
        "sheet_count": len(sheets_meta),
        "coordinate_engine": "openpyxl",
        "warnings": warnings,
    }
    doc["warnings"].extend(warnings)
    doc["text"] = "\n\n".join(all_grid_text)[:20000]
    return doc


def _cell_preview(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).replace("\n", " / ")
    return s[:80]


# ---------------------------------------------------------------------------
# images / OCR
# ---------------------------------------------------------------------------
def _ocr_words(path: Path) -> tuple[list[dict], str]:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError("图片 OCR 引擎不可用（rapidocr-onnxruntime 未安装）") from exc
    engine = RapidOCR()
    result, _ = engine(str(path))
    words = []
    for box, text, score in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        words.append({
            "text": str(text),
            "x0": float(min(xs)), "x1": float(max(xs)),
            "top": float(min(ys)), "bottom": float(max(ys)),
            "cx": float(sum(xs) / 4), "cy": float(sum(ys) / 4),
            "score": float(score),
        })
    return words, "rapidocr-onnxruntime"


def _ocr_rows(words: list[dict], y_tol: float = 14.0) -> list[list[dict]]:
    if not words:
        return []
    words = sorted(words, key=lambda w: (w["cy"], w["cx"]))
    rows: list[list[dict]] = []
    for w in words:
        if not rows:
            rows.append([w])
            continue
        center = statistics.mean(x["cy"] for x in rows[-1])
        if abs(w["cy"] - center) <= y_tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    for row in rows:
        row.sort(key=lambda w: w["cx"])
    return rows


def _ocr_matrix(rows: list[list[dict]]) -> list[list[Any]]:
    # infer columns from the widest header-ish row, otherwise cluster all centers
    header_idx = 0
    best = -1
    for i, row in enumerate(rows[:18]):
        text = " ".join(w["text"] for w in row)
        score = sum(len(field_scores(w["text"])) for w in row)
        if "description" in _norm(text) or "品名" in text or "hs" in _norm(text):
            score += 6
        if score > best:
            best = score
            header_idx = i
    header = rows[header_idx] if rows else []
    centers = [w["cx"] for w in header]
    if len(centers) < 3:
        # fall back to clustering all x centers into columns
        all_centers = sorted(w["cx"] for row in rows for w in row)
        centers = []
        for c in all_centers:
            if not centers or c - centers[-1] > 45:
                centers.append(c)
            else:
                centers[-1] = (centers[-1] + c) / 2
    matrix: list[list[Any]] = []
    for row in rows:
        cells = [""] * len(centers)
        for w in row:
            idx = min(range(len(centers)), key=lambda i: abs(centers[i] - w["cx"]))
            cells[idx] = (cells[idx] + " " + w["text"]).strip()
        matrix.append(cells)
    return matrix


def parse_image(path: Path, filename: str) -> dict:
    try:
        words, engine = _ocr_words(path)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"解析失败：{exc}",
            "type": "unknown",
            "fields": {},
            "items": [],
            "structure": {"format": "image", "ocr": "unavailable"},
            "warnings": [str(exc)],
            "text": "",
        }
    rows = _ocr_rows(words)
    matrix = _ocr_matrix(rows)
    full_text = "\n".join(" ".join(w["text"] for w in row) for row in rows)
    doc_type = infer_type(full_text[:1500])
    res = analyze_table(matrix, {"filename": filename, "page": 1, "sheet": None}, doc_type if doc_type != "unknown" else None)
    structure = {
        "format": "image",
        "ocr": engine,
        "width": None,
        "height": None,
        "lines": len(rows),
        "words": len(words),
        "coordinate_engine": "OCR bounding boxes",
        "word_sample": [{"text": w["text"], "x0": round(w["x0"], 1), "top": round(w["top"], 1)} for w in words[:80]],
        "ocr_rows": [[w["text"] for w in row] for row in rows[:40]],
    }
    try:
        from PIL import Image
        with Image.open(path) as im:
            structure["width"], structure["height"] = im.size
    except Exception:
        pass
    if not res.get("ok"):
        return {
            "ok": False,
            "error": "解析失败：图片中未检测到有效表格结构（可尝试更清晰的扫描件）",
            "type": doc_type,
            "fields": extract_fields_from_text(full_text, filename),
            "items": [],
            "structure": structure,
            "warnings": [res.get("reason", "")],
            "text": full_text[:20000],
        }
    fields = extract_fields_from_text(full_text, filename)
    doc = assemble_document([{"doc_type": res.get("doc_type") or doc_type, "items": res["items"], "fields": fields, "page": 1, "headers": res.get("headers", [])}], fields, filename, "image")
    doc["structure"] = structure
    doc["text"] = full_text[:20000]
    return doc


def parse_xls(path: Path, filename: str) -> dict:
    """Legacy Excel (BIFF) support via xlrd, preserving merged-cell values."""
    import xlrd

    book = xlrd.open_workbook(str(path))
    sections = []
    sheets_meta = []
    all_text = []
    warnings = []
    for sh in book.sheets():
        if sh.nrows == 0 or sh.ncols == 0:
            continue
        grid = [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
        # propagate merged-cell anchors so grouped supplier cells are retained
        for rlo, rhi, clo, chi in sh.merged_cells:
            val = grid[rlo][clo] if rlo < len(grid) and clo < len(grid[rlo]) else ""
            for r in range(rlo, min(rhi, len(grid))):
                for c in range(clo, min(chi, len(grid[r]))):
                    grid[r][c] = val
        title_text = " ".join(str(c) for c in grid[:4] for c in c if c not in (None, ""))
        grid_text = "\n".join(" | ".join("" if v is None else str(v) for v in row) for row in grid)
        all_text.append(grid_text)
        sheet_type = infer_type(sh.name + " " + title_text)
        if sheet_type == "unknown":
            sheet_type = infer_type(grid_text[:1500])
        res = analyze_table(grid, {"filename": filename, "page": sh.name, "sheet": sh.name},
                            sheet_type if sheet_type != "unknown" else None)
        sheets_meta.append({
            "title": sh.name, "dim": f"{sh.nrows}R x {sh.ncols}C", "max_row": sh.nrows, "max_col": sh.ncols,
            "merges": [f"{get_column_letter(c1+1)}{r1+1}:{get_column_letter(c2)}{r2}" for r1, r2, c1, c2 in sh.merged_cells][:60],
            "header_row": res.get("header_row"), "headers": res.get("headers", []),
            "recognized": bool(res.get("ok")), "reason": res.get("reason"),
            "item_count": len(res.get("items") or []),
            "grid_preview": [[_cell_preview(c) for c in row[:12]] for row in grid[:12]],
        })
        if res.get("ok"):
            fields = extract_fields_from_grid(grid)
            fields.update({k: v for k, v in extract_fields_from_text(grid_text, filename).items() if v not in (None, "", 0)})
            for k in ("supplier_name", "supplier_name_en", "supplier_name_zh"):
                v = str(fields.get(k) or "")
                if v and (len(v) < 3 or "*" in v or "供应商" in v or v.strip().endswith(":")):
                    fields.pop(k, None)
            # a product master can contain many per-row suppliers; keep the file's
            # platform-level supplier instead of pinning the first person name.
            if fields.get("supplier_name") and not re.search(r"(?i)CO\\.?,?\\s*LTD|LIMITED|COMPANY|有限公司|公司", fields["supplier_name"]):
                fields.pop("supplier_name", None)
            sections.append({
                "doc_type": res.get("doc_type") if res.get("doc_type") != "unknown" else sheet_type,
                "items": res["items"], "fields": fields, "page": sh.name, "table": sh.name,
                "headers": res.get("headers", []),
            })
        else:
            warnings.append(f"Sheet《{sh.name}》未识别到有效表格：{res.get('reason')}")
    if not sections:
        return {
            "ok": False, "error": "解析失败：未检测到有效表格结构（.xls 中未找到品名/HS/数量/金额等表头）",
            "type": "unknown", "fields": {}, "items": [],
            "structure": {"format": "xls", "sheets": sheets_meta}, "warnings": warnings,
            "text": "\n\n".join(all_text)[:20000],
        }
    fields = {}
    for sec in sections:
        for k, v in (sec.get("fields") or {}).items():
            if v not in (None, "", 0, 0.0) and fields.get(k) in (None, "", 0, 0.0):
                fields[k] = v
    doc = assemble_document(sections, fields, filename, "xls")
    doc["structure"] = {"format": "xls", "sheets": sheets_meta, "sheet_count": len(sheets_meta),
                        "coordinate_engine": "xlrd", "warnings": warnings}
    doc["warnings"].extend(warnings)
    doc["text"] = "\n\n".join(all_text)[:20000]
    return doc


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def parse_file(path: Path, filename: str) -> dict:
    ext = path.suffix.lower()
    try:
        if ext in {".xlsx", ".xlsm"}:
            return parse_excel(path, filename)
        if ext == ".xls":
            return parse_xls(path, filename)
        if ext == ".pdf":
            return parse_pdf(path, filename)
        if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            return parse_image(path, filename)
        return {"ok": False, "error": f"不支持的文件类型：{ext}", "items": [], "fields": {}, "structure": {}, "type": "unknown", "warnings": [], "text": ""}
    except Exception as exc:
        return {
            "ok": False,
            "error": f"解析失败：{type(exc).__name__}: {exc}",
            "type": "unknown",
            "fields": {},
            "items": [],
            "structure": {"format": ext.lstrip(".")},
            "warnings": [str(exc)],
            "text": "",
        }
