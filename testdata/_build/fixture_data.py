# -*- coding: utf-8 -*-
"""Authoritative data for the supplier-document fixture set.

This module is pure stdlib.  Every value that must appear in the rendered
documents (PDF / XLSX / PNG) and in manifest.json comes from here, so the
source documents, the manifest and the tests cannot drift apart.

Fixture narrative
-----------------
Three (fictional) Chinese furniture/hardware exporters ship to Melbourne,
Australia under CIF terms in April 2026:

  * Supplier A - NINGBO HOMELINE IMP.&EXP. CO., LTD   (PDF documents)
  * Supplier B - FOSHAN SUNRISE FURNITURE CO., LTD    (XLSX documents)
  * Supplier C - GUANGZHOU EVERGREEN HARDWARE CO., LTD (PNG packing list)

Supplier B line 3 is intentionally identical to Supplier A line 1 so that the
platform's cross-supplier de-duplication can be tested.  Supplier B line 2
deliberately has no HS code (data-quality test case).
"""

from decimal import Decimal, ROUND_HALF_UP

CURRENCY = "USD"
ORIGIN_COUNTRY = "CHINA"
INCOTERM = "CIF"
INCOTERM_FULL = "CIF MELBOURNE"
DESTINATION = {
    "city": "MELBOURNE",
    "country": "AUSTRALIA",
    "country_zh": "澳大利亚",
    "port": "MELBOURNE, AUSTRALIA",
}

ITEM_KEYS = ["A-1", "A-2", "A-3", "B-1", "B-2", "B-3", "C-1", "C-2", "C-3"]


def round2(value):
    """Round half up to 2 decimals (avoids Python banker's rounding)."""
    return float(Decimal(str(float(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def money(value):
    return f"{float(value):,.2f}"


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

SUPPLIERS = {
    "supplier_a": {
        "id": "supplier_a",
        "code": "A",
        "slug": "supplier_a_ningbo_homeline",
        "name_en": "NINGBO HOMELINE IMP.&EXP. CO., LTD",
        "name_zh": "宁波豪迈进出口有限公司",
        "address_en": "ROOM 1608, HAISU BUSINESS CENTER, NO. 588 NANZHAN ROAD, HAISHU DISTRICT, NINGBO, ZHEJIANG, CHINA",
        "address_zh": "中国浙江省宁波市海曙区南站路588号海曙商务中心1608室",
        "tel": "+86-574-8732-6688",
        "email": "sales@homeline-nb.com",
        "contact": "MS. LILY CHEN",
        "contact_zh": "陈丽丽",
        "contract_no": "HL-2026-0408",
        "invoice_no": "HL-INV-260408",
        "doc_date": "2026-04-08",
        "doc_date_text": "2026/04/08",
        "port_of_loading": "NINGBO, CHINA",
        "port_of_loading_zh": "中国宁波",
        "incoterm": INCOTERM_FULL,
        "payment": "T/T",
        "origin": ORIGIN_COUNTRY,
        "shipping_mark": "N/M",
        "buyer_en": "MELBOURNE HOME IMPORTS PTY LTD",
        "buyer_zh": "墨尔本家居进口有限公司",
        "buyer_address": "UNIT 5, 88 LOGISTICS DRIVE, TRUGANINA VIC 3029, AUSTRALIA",
        "bank": "BANK OF CHINA NINGBO BRANCH  SWIFT: BKCHCNBJ95N  A/C NO.: 3901 6688 0012 3456",
        "document_format": "pdf",
    },
    "supplier_b": {
        "id": "supplier_b",
        "code": "B",
        "slug": "supplier_b_foshan_sunrise",
        "name_en": "FOSHAN SUNRISE FURNITURE CO., LTD",
        "name_zh": "佛山市日出家具有限公司",
        "address_en": "NO. 18 SHUNDE INDUSTRIAL ROAD, LELIU TOWN, SHUNDE DISTRICT, FOSHAN, GUANGDONG, CHINA",
        "address_zh": "中国广东省佛山市顺德区勒流镇顺德工业路18号",
        "tel": "+86-757-2566-8899",
        "email": "export@sunrise-furniture.cn",
        "contact": "MR. KEVIN LIANG",
        "contact_zh": "梁凯文",
        "contract_no": "FSF-2026-0415",
        "invoice_no": "FSF-INV-260415",
        "doc_date": "2026-04-15",
        "doc_date_text": "2026/04/15",
        "port_of_loading": "SHENZHEN (SHEKOU), CHINA",
        "port_of_loading_zh": "中国深圳（蛇口）",
        "incoterm": INCOTERM_FULL,
        "payment": "T/T",
        "origin": ORIGIN_COUNTRY,
        "shipping_mark": "N/M",
        "buyer_en": "AUSTRALIAN HOME & TRADE PTY LTD",
        "buyer_zh": "澳洲家居贸易有限公司",
        "buyer_address": "12 DOCKLANDS DRIVE, MELBOURNE VIC 3008, AUSTRALIA",
        "bank": "BANK OF CHINA FOSHAN BRANCH  SWIFT: BKCHCNBJ44A  A/C NO.: 6789 0012 3456 789",
        "document_format": "xlsx",
    },
    "supplier_c": {
        "id": "supplier_c",
        "code": "C",
        "slug": "supplier_c_guangzhou_evergreen",
        "name_en": "GUANGZHOU EVERGREEN HARDWARE CO., LTD",
        "name_zh": "广州常青五金制品有限公司",
        "address_en": "NO. 66 HUANAN ROAD, PANYU DISTRICT, GUANGZHOU, GUANGDONG, CHINA",
        "address_zh": "中国广东省广州市番禺区华南路66号",
        "tel": "+86-20-8477-6600",
        "email": "info@evergreen-hw.cn",
        "contact": "MS. GRACE WU",
        "contact_zh": "吴嘉丽",
        "contract_no": "GEG-2026-0420",
        "invoice_no": "GEG-INV-260420",
        "doc_date": "2026-04-20",
        "doc_date_text": "2026/04/20",
        "port_of_loading": "GUANGZHOU (NANSHA), CHINA",
        "port_of_loading_zh": "中国广州（南沙）",
        "incoterm": INCOTERM_FULL,
        "payment": "T/T",
        "origin": ORIGIN_COUNTRY,
        "shipping_mark": "N/M",
        "buyer_en": "SOUTHERN CROSS FURNITURE PTY LTD",
        "buyer_zh": "南十字家具有限公司",
        "buyer_address": "45 INDUSTRIAL AVENUE, DANDENONG VIC 3175, AUSTRALIA",
        "bank": None,
        "document_format": "png",
    },
}


# ---------------------------------------------------------------------------
# Line items (source-of-truth values)
# ---------------------------------------------------------------------------

_RAW_ITEMS = [
    # ---------------- Supplier A - PDF ----------------
    dict(
        key="A-1", supplier="supplier_a", line_no=1,
        name_en="Metal Dining Chair", name_zh="金属餐椅", model="DC-2018",
        hs_code="9401790000",
        material_en="Steel frame + PU leather", material_zh="钢制框架 + PU皮",
        cartons=120, pieces_per_carton=6, unit_price=18.50,
        gross_weight_kg=2340, net_weight_kg=2100, dims=(62, 48, 92),
        packing_en="Export carton", packing_zh="出口纸箱",
        brand="HOMELINE",
        use_en="Indoor dining seating", use_zh="室内餐厅座椅",
        process_en="Cutting, welding, polishing, powder coating, assembly",
        process_zh="下料、焊接、抛光、喷涂、组装",
        scenario_en="Home dining room / restaurant", scenario_zh="家庭餐厅 / 餐厅",
    ),
    dict(
        key="A-2", supplier="supplier_a", line_no=2,
        name_en="Wooden Side Table", name_zh="木制边几", model="ST-330",
        hs_code="9403600000",
        material_en="MDF + oak veneer", material_zh="密度板 + 橡木贴皮",
        cartons=80, pieces_per_carton=4, unit_price=24.00,
        gross_weight_kg=1180, net_weight_kg=1050, dims=(55, 45, 70),
        packing_en="Export carton", packing_zh="出口纸箱",
        brand="HOMELINE",
        use_en="Living room side table", use_zh="客厅边几",
        process_en="Panel cutting, edge banding, sanding, lacquering, assembly",
        process_zh="开料、封边、打磨、喷漆、组装",
        scenario_en="Living room", scenario_zh="客厅",
    ),
    dict(
        key="A-3", supplier="supplier_a", line_no=3,
        name_en="Steel Storage Rack", name_zh="钢制储物架", model="SR-905",
        hs_code="7326909000",
        material_en="Powder-coated steel tube", material_zh="喷涂钢管",
        cartons=65, pieces_per_carton=2, unit_price=46.00,
        gross_weight_kg=3250, net_weight_kg=3100, dims=(120, 40, 15),
        packing_en="Export carton", packing_zh="出口纸箱",
        brand="HOMELINE",
        use_en="Warehouse storage", use_zh="仓储收纳",
        process_en="Tube cutting, welding, powder coating, assembly",
        process_zh="切管、焊接、喷涂、组装",
        scenario_en="Warehouse / garage", scenario_zh="仓库 / 车库",
    ),
    # ---------------- Supplier B - XLSX ----------------
    dict(
        key="B-1", supplier="supplier_b", line_no=1,
        name_en="Outdoor Bench", name_zh="户外长椅", model="OB-120",
        hs_code="9401690000",
        material_en="Acacia wood + steel legs", material_zh="相思木 + 钢脚",
        cartons=50, pieces_per_carton=3, unit_price=58.00,
        gross_weight_kg=1680, net_weight_kg=1500, dims=(155, 45, 40),
        packing_en="Export carton", packing_zh="出口纸箱",
        brand="SUNRISE",
        use_en="Outdoor garden seating", use_zh="户外花园座椅",
        process_en="Wood cutting, sanding, oil coating, assembly",
        process_zh="木材开料、打磨、涂油、组装",
        scenario_en="Garden / patio", scenario_zh="花园 / 庭院",
    ),
    dict(
        key="B-2", supplier="supplier_b", line_no=2,
        name_en="Aluminum Folding Chair", name_zh="铝合金折叠椅", model="AF-77",
        # INTENTIONAL DATA-QUALITY CASE: HS code omitted in both B documents.
        hs_code=None,
        material_en="Aluminum alloy + textilene", material_zh="铝合金 + 特斯林布",
        cartons=40, pieces_per_carton=8, unit_price=12.50,
        gross_weight_kg=560, net_weight_kg=480, dims=(58, 38, 105),
        packing_en="Export carton", packing_zh="出口纸箱",
        brand="SUNRISE",
        use_en="Outdoor portable seating", use_zh="户外便携座椅",
        process_en="Aluminum cutting, bending, anodizing, fabric sewing, assembly",
        process_zh="铝材切割、折弯、氧化、缝布、组装",
        scenario_en="Camping / balcony", scenario_zh="露营 / 阳台",
    ),
    dict(
        key="B-3", supplier="supplier_b", line_no=3,
        # INTENTIONAL CROSS-SUPPLIER DUPLICATE of A-1: same product, model,
        # HS code, cartons, pieces/carton, total pieces, unit price and amount.
        name_en="Metal Dining Chair", name_zh="金属餐椅", model="DC-2018",
        hs_code="9401790000",
        material_en="Steel frame + PU leather", material_zh="钢制框架 + PU皮",
        cartons=120, pieces_per_carton=6, unit_price=18.50,
        gross_weight_kg=2340, net_weight_kg=2100, dims=(62, 48, 92),
        packing_en="Export carton", packing_zh="出口纸箱",
        brand="SUNRISE",
        use_en="Indoor dining seating", use_zh="室内餐厅座椅",
        process_en="Cutting, welding, polishing, powder coating, assembly",
        process_zh="下料、焊接、抛光、喷涂、组装",
        scenario_en="Home dining room / restaurant", scenario_zh="家庭餐厅 / 餐厅",
    ),
    # ---------------- Supplier C - PNG ----------------
    dict(
        key="C-1", supplier="supplier_c", line_no=1,
        name_en="Wrought Iron Plant Stand", name_zh="铁艺花架", model="PS-210",
        hs_code="7326209000",
        material_en="Steel wire + powder coating", material_zh="铁线 + 喷涂",
        cartons=30, pieces_per_carton=4, unit_price=9.80,
        gross_weight_kg=300, net_weight_kg=240, dims=(42, 32, 68),
        packing_en="Export carton", packing_zh="出口纸箱",
        brand="EVERGREEN",
        use_en="Indoor / outdoor plant display", use_zh="花木摆放",
        process_en="Wire bending, welding, powder coating",
        process_zh="铁线折弯、焊接、喷涂",
        scenario_en="Garden / balcony", scenario_zh="花园 / 阳台",
    ),
    dict(
        key="C-2", supplier="supplier_c", line_no=2,
        name_en="Teak Outdoor Bench", name_zh="柚木户外长椅", model="TB-150",
        hs_code="9401690000",
        material_en="Teak wood", material_zh="柚木",
        cartons=25, pieces_per_carton=2, unit_price=74.00,
        gross_weight_kg=1010, net_weight_kg=900, dims=(150, 60, 45),
        packing_en="Export carton", packing_zh="出口纸箱",
        brand="EVERGREEN",
        use_en="Outdoor garden seating", use_zh="户外花园座椅",
        process_en="Wood cutting, sanding, oil coating, assembly",
        process_zh="木材开料、打磨、涂油、组装",
        scenario_en="Garden / patio", scenario_zh="花园 / 庭院",
    ),
    dict(
        key="C-3", supplier="supplier_c", line_no=3,
        name_en="Aluminum Folding Table", name_zh="铝合金折叠桌", model="AT-80",
        hs_code="9403200000",
        material_en="Aluminum alloy", material_zh="铝合金",
        cartons=60, pieces_per_carton=5, unit_price=15.60,
        gross_weight_kg=1020, net_weight_kg=900, dims=(70, 25, 55),
        packing_en="Export carton", packing_zh="出口纸箱",
        brand="EVERGREEN",
        use_en="Outdoor camping table", use_zh="户外露营桌",
        process_en="Aluminum cutting, stamping, anodizing, assembly",
        process_zh="铝材切割、冲压、氧化、组装",
        scenario_en="Camping / picnic", scenario_zh="露营 / 野餐",
    ),
]


def build_items():
    """Return enriched item dicts (computed totals, CBM, text helpers)."""
    items = []
    for raw in _RAW_ITEMS:
        it = dict(raw)
        l, w, h = it["dims"]
        it["dimensions_cm"] = {"l": l, "w": w, "h": h}
        it["dimensions_text"] = "{}\u00d7{}\u00d7{}".format(l, w, h)
        it["total_pieces"] = it["cartons"] * it["pieces_per_carton"]
        it["amount"] = round2(it["unit_price"] * it["total_pieces"])
        volume_m3 = (l * w * h) / 1_000_000.0
        it["cbm_per_carton"] = round(volume_m3, 6)
        it["cbm"] = round2(volume_m3 * it["cartons"])
        it["hs_code_missing"] = it["hs_code"] is None
        it["currency"] = CURRENCY
        it["preferential_tariff"] = "CHAFTA 0%"
        it["origin_country"] = ORIGIN_COUNTRY
        it["price_source"] = "packing_list+invoice" if it["supplier"] != "supplier_c" else "manifest_only_no_invoice"
        items.append(it)
    return items


ITEMS = build_items()

# Expected fixed values, asserted by the verifier so a data edit cannot
# silently invalidate the published fixture set.
EXPECTED_TOTALS = {
    "supplier_a": {"cartons": 265, "total_pieces": 1170, "amount": 26980.00,
                   "gross_weight_kg": 6770, "net_weight_kg": 6250, "cbm": 51.40, "item_count": 3},
    "supplier_b": {"cartons": 210, "total_pieces": 1190, "amount": 26020.00,
                   "gross_weight_kg": 4580, "net_weight_kg": 4080, "cbm": 56.07, "item_count": 3},
    "supplier_c": {"cartons": 115, "total_pieces": 470, "amount": 9556.00,
                   "gross_weight_kg": 2330, "net_weight_kg": 2040, "cbm": 18.65, "item_count": 3},
}
EXPECTED_GRAND_TOTALS = {
    "cartons": 590, "total_pieces": 2830, "amount": 62556.00,
    "gross_weight_kg": 13680, "net_weight_kg": 12370, "cbm": 126.12, "item_count": 9,
    "document_count": 5, "supplier_count": 3,
}


def items_for(supplier_id):
    return [it for it in ITEMS if it["supplier"] == supplier_id]


def supplier_totals(supplier_id):
    lst = items_for(supplier_id)
    return {
        "cartons": sum(it["cartons"] for it in lst),
        "total_pieces": sum(it["total_pieces"] for it in lst),
        "amount": round2(sum(it["amount"] for it in lst)),
        "gross_weight_kg": sum(it["gross_weight_kg"] for it in lst),
        "net_weight_kg": sum(it["net_weight_kg"] for it in lst),
        "cbm": round2(sum(it["cbm"] for it in lst)),
        "item_count": len(lst),
    }


def grand_totals():
    suppliers = list(SUPPLIERS.keys())
    return {
        "cartons": sum(supplier_totals(s)["cartons"] for s in suppliers),
        "total_pieces": sum(supplier_totals(s)["total_pieces"] for s in suppliers),
        "amount": round2(sum(supplier_totals(s)["amount"] for s in suppliers)),
        "gross_weight_kg": sum(supplier_totals(s)["gross_weight_kg"] for s in suppliers),
        "net_weight_kg": sum(supplier_totals(s)["net_weight_kg"] for s in suppliers),
        "cbm": round2(sum(supplier_totals(s)["cbm"] for s in suppliers)),
        "item_count": sum(supplier_totals(s)["item_count"] for s in suppliers),
        "document_count": 5,
        "supplier_count": len(suppliers),
    }


# ---------------------------------------------------------------------------
# English amount in words (for "SAY TOTAL" lines)
# ---------------------------------------------------------------------------

_ONES = ["ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE",
         "TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN",
         "SEVENTEEN", "EIGHTEEN", "NINETEEN"]
_TENS = ["", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY"]


def _below_thousand(n):
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else "-" + _ONES[n % 10])
    return _ONES[n // 100] + " HUNDRED" + ("" if n % 100 == 0 else " AND " + _below_thousand(n % 100))


def amount_in_words(amount):
    cents = int(round(float(amount) * 100))
    dollars, cent = divmod(cents, 100)
    parts = []
    if dollars >= 1_000_000:
        parts.append(_below_thousand(dollars // 1_000_000) + " MILLION")
        dollars %= 1_000_000
    if dollars >= 1_000:
        parts.append(_below_thousand(dollars // 1_000) + " THOUSAND")
        dollars %= 1_000
    if dollars:
        parts.append(_below_thousand(dollars))
    text = " ".join(parts) if parts else "ZERO"
    if cent:
        text += " AND CENTS " + _below_thousand(cent)
    return text


# ---------------------------------------------------------------------------
# Document definitions
# ---------------------------------------------------------------------------

DOC_DIR = {k: "testdata/" + v["slug"] for k, v in SUPPLIERS.items()}

DOCUMENTS = [
    {"id": "doc_a_packing", "supplier_id": "supplier_a", "doc_type": "packing_list",
     "doc_type_zh": "装箱清单", "format": "pdf", "filename": "packing_list.pdf"},
    {"id": "doc_a_invoice", "supplier_id": "supplier_a", "doc_type": "commercial_invoice",
     "doc_type_zh": "商业发票", "format": "pdf", "filename": "commercial_invoice.pdf"},
    {"id": "doc_b_packing", "supplier_id": "supplier_b", "doc_type": "packing_list",
     "doc_type_zh": "装箱清单", "format": "xlsx", "filename": "packing_list.xlsx"},
    {"id": "doc_b_invoice", "supplier_id": "supplier_b", "doc_type": "commercial_invoice",
     "doc_type_zh": "商业发票", "format": "xlsx", "filename": "commercial_invoice.xlsx"},
    {"id": "doc_c_packing", "supplier_id": "supplier_c", "doc_type": "packing_list",
     "doc_type_zh": "装箱清单", "format": "png", "filename": "packing_list_scan.png"},
]

DOC_ITEM_KEYS = {d["id"]: [it["key"] for it in items_for(d["supplier_id"])] for d in DOCUMENTS}


def document_path(doc):
    return DOC_DIR[doc["supplier_id"]] + "/" + doc["filename"]


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def _extraction_expectations(doc):
    """Static per-document expectations that do not depend on the renderer."""
    sup = SUPPLIERS[doc["supplier_id"]]
    keys = DOC_ITEM_KEYS[doc["id"]]
    items = [it for it in ITEMS if it["key"] in keys]
    if doc["format"] in ("pdf", "png"):
        common = {
            "item_count": len(items),
            "expected_item_keys": keys,
            "expected_names_en": [it["name_en"] for it in items],
            "expected_names_zh": [it["name_zh"] for it in items],
            "expected_hs_codes": [it["hs_code"] for it in items if it["hs_code"]],
        }
        if doc["format"] == "pdf":
            common.update({
                "text_extractable": True,
                "text_layer": "real text (embedded TrueType font with ToUnicode CMap), not a rasterised image",
                "languages": ["EN", "ZH"],
                "page_count": 1,
                "required_keywords": [sup["name_en"], sup["contract_no"], sup["invoice_no"],
                                      "HS CODE", "CBM", "TOTAL"],
                "expected_total_strings": [str(supplier_totals(doc["supplier_id"])["cartons"]),
                                            str(supplier_totals(doc["supplier_id"])["total_pieces"]),
                                            money(supplier_totals(doc["supplier_id"])["amount"])
                                            if doc["doc_type"] == "commercial_invoice" else
                                            "{:,}".format(supplier_totals(doc["supplier_id"])["gross_weight_kg"]),
                                            "{:.2f}".format(supplier_totals(doc["supplier_id"])["cbm"])],
            })
        else:
            common.update({
                "text_extractable": False,
                "text_layer": "none - raster image; parser must run OCR",
                "image_size_px": {"width": 1800, "height": 1150},
                "image_mode": "RGB",
                "ocr_keywords": [sup["name_en"], sup["contract_no"], sup["invoice_no"],
                                 "PACKING LIST", "HS CODE", "CBM", "TOTAL"],
            })
        return common

    # XLSX
    totals = supplier_totals(doc["supplier_id"])
    if doc["doc_type"] == "packing_list":
        return {
            "sheet_names": ["Packing List"],
            "layout": "different from Supplier A: two title rows at the top, cartons column before description, no separate model column",
            "title_rows": [1, 2],
            "header_row": 4,
            "data_rows": [5, 6, 7],
            "totals_row": 8,
            "item_count": 3,
            "expected_item_keys": keys,
            "expected_names_en": [it["name_en"] for it in items],
            "expected_names_zh": [it["name_zh"] for it in items],
            "expected_hs_codes": [it["hs_code"] for it in items if it["hs_code"]],
            "missing_hs_item_keys": [it["key"] for it in items if it["hs_code"] is None],
            "columns": [
                {"col": "A", "header": "NO.", "meaning": "line_no"},
                {"col": "B", "header": "CARTONS 箱数", "meaning": "cartons"},
                {"col": "C", "header": "DESCRIPTION 英文品名", "meaning": "name_en"},
                {"col": "D", "header": "中文品名", "meaning": "name_zh"},
                {"col": "E", "header": "HS CODE 海关编码", "meaning": "hs_code"},
                {"col": "F", "header": "MATERIAL 材质", "meaning": "materials"},
                {"col": "G", "header": "PCS/CTN 每箱件数", "meaning": "pieces_per_carton"},
                {"col": "H", "header": "TOTAL PCS 总件数", "meaning": "total_pieces"},
                {"col": "I", "header": "N.W.(KGS) 净重", "meaning": "net_weight_kg"},
                {"col": "J", "header": "G.W.(KGS) 毛重", "meaning": "gross_weight_kg"},
                {"col": "K", "header": "MEAS.(CM) L*W*H 外箱尺寸", "meaning": "dimensions_cm"},
                {"col": "L", "header": "CBM 方数", "meaning": "cbm"},
                {"col": "M", "header": "PACKING 包装类型", "meaning": "packing_type"},
            ],
            "expected_totals": totals,
        }
    return {
        "sheet_names": ["Commercial Invoice"],
        "layout": "different from Supplier A: two title rows, MODEL column before HS CODE, cartons/pieces columns reordered",
        "title_rows": [1, 2],
        "header_row": 5,
        "data_rows": [6, 7, 8],
        "totals_row": 9,
        "item_count": 3,
        "expected_item_keys": keys,
        "expected_names_en": [it["name_en"] for it in items],
        "expected_names_zh": [it["name_zh"] for it in items],
        "expected_hs_codes": [it["hs_code"] for it in items if it["hs_code"]],
        "missing_hs_item_keys": [it["key"] for it in items if it["hs_code"] is None],
        "columns": [
            {"col": "A", "header": "NO.", "meaning": "line_no"},
            {"col": "B", "header": "DESCRIPTION 英文品名", "meaning": "name_en"},
            {"col": "C", "header": "中文品名", "meaning": "name_zh"},
            {"col": "D", "header": "MODEL 型号", "meaning": "model"},
            {"col": "E", "header": "HS CODE 海关编码", "meaning": "hs_code"},
            {"col": "F", "header": "MATERIAL 材质", "meaning": "materials"},
            {"col": "G", "header": "CARTONS 箱数", "meaning": "cartons"},
            {"col": "H", "header": "PCS/CTN 每箱件数", "meaning": "pieces_per_carton"},
            {"col": "I", "header": "TOTAL PCS 计价件数", "meaning": "total_pieces"},
            {"col": "J", "header": "UNIT PRICE(USD) 单价", "meaning": "unit_price"},
            {"col": "K", "header": "AMOUNT(USD) 金额", "meaning": "amount"},
        ],
        "expected_totals": totals,
    }


def _item_manifest(it):
    docs = [d["id"] for d in DOCUMENTS
            if d["supplier_id"] == it["supplier"]]
    return {
        "key": it["key"],
        "supplier_id": it["supplier"],
        "supplier_code": SUPPLIERS[it["supplier"]]["code"],
        "line_no": it["line_no"],
        "source_documents": docs,
        "name_en": it["name_en"],
        "name_zh": it["name_zh"],
        "model": it["model"],
        "hs_code": it["hs_code"],
        "hs_code_missing": it["hs_code_missing"],
        "materials_en": it["material_en"],
        "materials_zh": it["material_zh"],
        "brand": it["brand"],
        "use_en": it["use_en"],
        "use_zh": it["use_zh"],
        "process_en": it["process_en"],
        "process_zh": it["process_zh"],
        "scenario_en": it["scenario_en"],
        "scenario_zh": it["scenario_zh"],
        "preferential_tariff": it["preferential_tariff"],
        "cartons": it["cartons"],
        "pieces_per_carton": it["pieces_per_carton"],
        "total_pieces": it["total_pieces"],
        "unit_price": it["unit_price"],
        "amount": it["amount"],
        "currency": it["currency"],
        "gross_weight_kg": it["gross_weight_kg"],
        "net_weight_kg": it["net_weight_kg"],
        "cbm_per_carton": it["cbm_per_carton"],
        "cbm": it["cbm"],
        "dimensions_cm": it["dimensions_cm"],
        "dimensions_text": it["dimensions_text"],
        "packing_type_en": it["packing_en"],
        "packing_type_zh": it["packing_zh"],
        "origin_country": it["origin_country"],
        "price_source": it["price_source"],
    }


def _duplicate_definition():
    a = next(it for it in ITEMS if it["key"] == "A-1")
    b = next(it for it in ITEMS if it["key"] == "B-3")
    match_fields = ["name_en", "model", "hs_code", "cartons", "pieces_per_carton",
                    "total_pieces", "unit_price", "amount", "gross_weight_kg", "net_weight_kg",
                    "dimensions_cm", "cbm"]
    return {
        "id": "dup-metal-dining-chair",
        "item_keys": ["A-1", "B-3"],
        "description": "Supplier A line 1 and Supplier B line 3 are deliberately identical "
                       "(same product, model, HS code, cartons, pieces/carton, total pieces, "
                       "unit price and amount) so that cross-supplier de-duplication can be tested.",
        "match_fields": match_fields,
        "identical_values": {
            "name_en": a["name_en"], "name_zh": a["name_zh"], "model": a["model"],
            "hs_code": a["hs_code"], "cartons": a["cartons"],
            "pieces_per_carton": a["pieces_per_carton"], "total_pieces": a["total_pieces"],
            "unit_price": a["unit_price"], "amount": a["amount"],
            "gross_weight_kg": a["gross_weight_kg"], "net_weight_kg": a["net_weight_kg"],
            "dimensions_cm": a["dimensions_cm"], "cbm": a["cbm"],
        },
        "expected_behaviour": "Both source lines must still be extracted (6 supplier lines total), "
                               "but the canonical item list should collapse them into one item and "
                               "keep both source occurrences.",
    }


def data_quality_cases():
    return {
        "missing_hs_code": {
            "item_key": "B-2",
            "product": "Aluminum Folding Chair / 铝合金折叠椅",
            "documents": ["doc_b_packing", "doc_b_invoice"],
            "expected_behaviour": "The line must still be extracted from both Supplier B files with "
                                   "hs_code = null; validation should flag a missing/invalid HS code and "
                                   "must not silently merge the line with another item.",
        },
        "cross_supplier_duplicate": {
            "duplicate_id": "dup-metal-dining-chair",
            "item_keys": ["A-1", "B-3"],
            "expected_behaviour": "De-duplicate by product/HS/quantity/amount; keep both source occurrences.",
        },
        "two_title_rows": {
            "documents": ["doc_b_packing", "doc_b_invoice"],
            "expected_behaviour": "Header detection must skip the two title rows (company name + document title) "
                                   "and find the real column header row (row 4 / row 5).",
        },
        "text_pdf_vs_scanned_png": {
            "documents": ["doc_a_packing", "doc_a_invoice", "doc_c_packing"],
            "expected_behaviour": "Supplier A PDFs expose a real text layer; Supplier C PNG has no text layer "
                                   "and requires OCR.",
        },
        "mixed_en_zh": {
            "documents": ["doc_a_packing", "doc_a_invoice", "doc_b_packing", "doc_b_invoice", "doc_c_packing"],
            "expected_behaviour": "Both English and Simplified Chinese labels/content are present and must be "
                                   "extracted; product names exist in both languages.",
        },
    }


def template_mapping():
    return {
        "workbook": "repo/assets/template.xlsx",
        "sheets": {
            "packing_list": "装箱清单",
            "commercial_invoice": "发票",
            "declaration_elements": "申报要素",
            "sales_confirmation": "销货确认书",
            "customs_declaration": "报关单 ",
        },
        "sheet_name_note": "The customs-declaration worksheet title is '报关单 ' with a trailing space, "
                            "matching the provided template exactly.",
        "population_expectations": {
            "装箱清单": "supplier packing list fields: description EN/ZH, HS code, materials, cartons, "
                        "pieces per carton, dimensions L*W*H, CBM, gross weight, packing type; total row.",
            "发票": "supplier commercial invoice fields: description EN/ZH, HS code, materials, cartons, "
                    "pieces/carton, total pieces, unit price, amount; total row; contract/invoice no; date.",
            "申报要素": "per-item brand, product name EN/ZH, HS code, model, material, use, process, "
                        "scenario, preferential tariff; contract no, destination, date.",
            "销货确认书": "seller/buyer blocks, contract no, date, items with quantity/unit price/amount, "
                          "CIF term, destination, payment T/T.",
            "报关单 ": "contract no, destination country 澳大利亚, incoterm CIF, cartons, pieces, gross/net "
                        "weight, currency USD, origin CHINA.",
        },
    }


def build_manifest(documents):
    """documents: list of document dicts (with runtime metadata) from the builder."""
    suppliers_out = {}
    for sid, sup in SUPPLIERS.items():
        out = {k: v for k, v in sup.items()}
        out["line_item_keys"] = [it["key"] for it in items_for(sid)]
        out["totals"] = supplier_totals(sid)
        out["item_count"] = len(items_for(sid))
        suppliers_out[sid] = out
    return {
        "schema_version": "1.0.0",
        "fixture_set": "supplier-documents-australia-2026-04",
        "description": "Synthetic China -> Australia furniture/hardware export documents for "
                        "end-to-end supplier-document parsing, normalization and de-duplication tests.",
        "disclaimer": "All companies, addresses, contracts and prices are fictional; the data is "
                       "realistic but not taken from any real shipment.",
        "currency": CURRENCY,
        "incoterm": INCOTERM,
        "incoterm_full": INCOTERM_FULL,
        "destination": DESTINATION,
        "origin_country": ORIGIN_COUNTRY,
        "trade_lane": "CHINA -> AUSTRALIA",
        "supplier_count": len(SUPPLIERS),
        "document_count": len(documents),
        "item_count": len(ITEMS),
        "suppliers": suppliers_out,
        "documents": documents,
        "items": [_item_manifest(it) for it in ITEMS],
        "totals_by_supplier": {sid: supplier_totals(sid) for sid in SUPPLIERS},
        "grand_totals": grand_totals(),
        "duplicates": [_duplicate_definition()],
        "data_quality_cases": data_quality_cases(),
        "template_mapping": template_mapping(),
        "aggregation_notes": {
            "cbm": "Per-line CBM = round_half_up(L*W*H/1,000,000 * cartons, 2); totals are sums of the "
                    "rounded per-line values, so tests can add the manifest line values and match the totals.",
            "cbm_per_carton": "cbm_per_carton = L*W*H/1,000,000 rounded to 6 decimals (exact for cm dimensions).",
            "amount": "amount = round_half_up(unit_price * total_pieces, 2).",
            "weights": "gross/net weights are per line total kilograms.",
            "missing_hs": "B-2 intentionally has hs_code = null in both Supplier B files and in this manifest.",
        },
    }
