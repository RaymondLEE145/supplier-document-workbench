# -*- coding: utf-8 -*-
"""Deterministic, structure-aware Excel template filler.

This module is intentionally self-contained (only openpyxl + stdlib) because the
platform serialises its source into the *generated Python script* that performs
the actual fill.  It rebuilds each sheet from a style snapshot instead of using
openpyxl.insert_rows(), which avoids the classic merged-cell / formula / style
corruption.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# template semantics (the 5-sheet export workbook)
# ---------------------------------------------------------------------------
SHEET_SPECS = {
    "装箱清单": {
        "role": "packing_list",
        "header_end": 5,
        "data_start": 6,
        "base_data_rows": 4,
        "pattern_rows": [6],
        "footer_start": 10,
        "footer_rows": [10, 11, 12],
        "block": 1,
        "columns": {
            "no": 1, "picture": 2, "name_en": 3, "name_zh": 4, "hs_code": 5, "material": 6,
            "cartons": 7, "pieces_per_carton": 8, "length": 9, "width": 10, "height": 11,
            "cbm": 12, "gross_weight": 13, "packing": 14,
        },
        "merges": [],
        "print_cols": 14,
    },
    "发票": {
        "role": "invoice",
        "header_end": 9,
        "data_start": 10,
        "base_data_rows": 2,
        "pattern_rows": [10],
        "footer_start": 12,
        "footer_rows": [12],
        "block": 1,
        "columns": {
            "no": 1, "name_en": 2, "name_zh": 3, "hs_code": 4, "material": 5, "cartons": 6,
            "pieces_per_carton": 7, "pieces": 8, "unit_price": 9, "amount": 10,
        },
        "merges": [],
        "print_cols": 10,
    },
    "申报要素": {
        "role": "declaration_elements",
        "header_end": 4,
        "data_start": 5,
        "base_data_rows": 1,
        "pattern_rows": [5],
        "footer_start": None,
        "footer_rows": [],
        "block": 1,
        "columns": {
            "no": 1, "brand": 2, "name_zh": 3, "hs_code": 4, "model": 5, "material": 6,
            "usage": 7, "processing": 8, "scenario": 9, "preference": 10, "picture": 11,
        },
        "merges": [],
        "print_cols": 11,
    },
    "销货确认书": {
        "role": "sales_confirmation",
        "header_end": 20,
        "data_start": 21,
        "base_data_rows": 2,
        "pattern_rows": [21],
        "footer_start": 23,
        "footer_rows": list(range(23, 43)),
        "block": 1,
        "columns": {
            "no": 1, "name_zh": 3, "model": 4, "unit": 5, "pieces": 6, "unit_price": 7, "amount": 8,
        },
        "merges": [],
        "print_cols": 8,
    },
    "报关单 ": {
        "role": "customs_declaration",
        "header_end": 19,
        "data_start": 20,
        "base_data_rows": 4,  # 2 items * 2 rows
        "pattern_rows": [20, 21],
        "footer_start": 24,
        "footer_rows": [24, 25, 26, 27, 28],
        "block": 2,
        "columns": {
            "no": 1, "hs_code": 2, "name_zh": 4, "model": 5, "unit": 7, "pieces": 9,
            "unit_price": 10, "amount_currency": 11, "origin": 12, "destination": 13,
            "source": 14, "exemption": 16,
        },
        "merges": [
            ("A", "A"), ("B", "C"), ("D", "D"), ("E", "F"), ("G", "G"), ("H", "H"),
            ("I", "I"), ("K", "K"), ("L", "L"), ("M", "M"), ("N", "O"), ("P", "P"),
        ],
        "print_cols": 16,
    },
}

# template names can contain a trailing space (报关单 ) — normalise lookups
SHEET_ALIASES = {
    "装箱清单": "装箱清单", "PACKING LIST": "装箱清单", "PACKING": "装箱清单",
    "发票": "发票", "INVOICE": "发票", "COMMERCIAL INVOICE": "发票",
    "申报要素": "申报要素", "DECLARATION ELEMENTS": "申报要素",
    "销货确认书": "销货确认书", "SALES CONFIRMATION": "销货确认书",
    "报关单": "报关单 ", "报关单 ": "报关单 ", "CUSTOMS DECLARATION": "报关单 ",
}


def _canon_sheet(name: str) -> str | None:
    n = (name or "").strip()
    if n in SHEET_ALIASES:
        return SHEET_ALIASES[n]
    for alias, canon in SHEET_ALIASES.items():
        if alias and alias in n:
            return canon
    return None


def _num(v: Any, default: float = 0.0) -> float:
    if v is None or v == "":
        return default
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v).replace(",", ""))
    return float(m.group(0)) if m else default


def _text(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _cell_style(cell) -> Any:
    try:
        return copy.copy(cell._style)
    except Exception:
        return None


def _capture(ws) -> dict:
    max_row = max(ws.max_row or 1, 1)
    max_col = max(ws.max_column or 1, 1)
    cells: dict[tuple[int, int], dict] = {}
    for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
        for c in row:
            if c.value is None and not c.has_style:
                continue
            cells[(c.row, c.column)] = {
                "value": c.value,
                "style": _cell_style(c),
                "number_format": c.number_format,
            }
    heights = {}
    for k, dim in ws.row_dimensions.items():
        if dim.height is not None:
            heights[int(k)] = dim.height
    merges = []
    for rng in ws.merged_cells.ranges:
        merges.append((rng.min_row, rng.min_col, rng.max_row, rng.max_col))
    return {"cells": cells, "heights": heights, "merges": merges, "max_row": max_row, "max_col": max_col}


def _clear_sheet(ws) -> None:
    for rng in list(ws.merged_cells.ranges):
        ws.unmerge_cells(str(rng))
    try:
        ws._cells.clear()
    except Exception:
        for row in ws.iter_rows():
            for c in row:
                c.value = None
    for key in list(ws.row_dimensions.keys()):
        ws.row_dimensions.pop(key, None)
    # column widths intentionally preserved


def _put(ws, r: int, c: int, snap: dict | None, value: Any = None, has_value: bool = False, wrap: bool | None = None) -> None:
    cell = ws.cell(row=r, column=c)
    if snap and snap.get("style") is not None:
        cell._style = copy.copy(snap["style"])
    if has_value:
        cell.value = value
    if wrap is True:
        al = cell.alignment
        cell.alignment = Alignment(horizontal=al.horizontal, vertical=al.vertical or "center", wrap_text=True,
                                   text_rotation=al.text_rotation, indent=al.indent, shrink_to_fit=al.shrink_to_fit)
    elif wrap is False:
        al = cell.alignment
        cell.alignment = Alignment(horizontal=al.horizontal, vertical=al.vertical, wrap_text=False,
                                   text_rotation=al.text_rotation, indent=al.indent, shrink_to_fit=al.shrink_to_fit)


def _copy_row(ws, snap: dict, src_row: int, dst_row: int, max_col: int, values: dict[int, Any] | None = None,
              wrap_cols: set[int] | None = None, clear_unmapped: bool = False, copy_values: bool = False) -> None:
    values = values or {}
    for c in range(1, max_col + 1):
        s = snap["cells"].get((src_row, c))
        if clear_unmapped and c not in values:
            _put(ws, dst_row, c, s, None, has_value=True, wrap=(c in (wrap_cols or set())))
        elif copy_values and c not in values:
            _put(ws, dst_row, c, s, s.get("value") if s else None, has_value=bool(s and s.get("value") is not None),
                 wrap=(c in (wrap_cols or set())))
        else:
            _put(ws, dst_row, c, s, values.get(c), has_value=(c in values), wrap=(c in (wrap_cols or set())))
    if src_row in snap["heights"]:
        ws.row_dimensions[dst_row].height = snap["heights"][src_row]


def _apply_merges(ws, merges: list[tuple[int, int, int, int]]) -> None:
    for r1, c1, r2, c2 in merges:
        if r1 == r2 and c1 == c2:
            continue
        try:
            ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)
        except Exception:
            pass


def _fill_header(ws, role: str, doc: dict, items: list[dict], layout: dict) -> None:
    if role == "packing_list":
        consignee = _text(doc.get("consignee") or doc.get("buyer"))
        if consignee:
            ws["C3"] = consignee
            ws["C3"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)
        packing = _text(doc.get("packing") or "纸箱包装")
        note_row = layout.get("packing_note_row") or (layout["total_row"] + 2)
        ws[f"A{note_row}"] = f"包装方式：{packing}"
        ws[f"A{note_row}"].alignment = Alignment(horizontal="left", vertical="center")
        # helper totals outside the print area (kept from the original workbook convention)
        total_row = layout["total_row"]
        ws[f"O{total_row}"] = sum(int(i.get("cartons") or 0) for i in items)
        ws[f"P{total_row}"] = sum(int(i.get("pieces") or 0) for i in items)
        for coord in (f"O{total_row}", f"P{total_row}"):
            ws[coord].font = copy.copy(ws[coord].font)
            ws[coord].alignment = Alignment(horizontal="center", vertical="center")
    elif role == "invoice":
        consignee = _text(doc.get("consignee") or doc.get("buyer"))
        if consignee:
            ws["C6"] = consignee
            ws["C6"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)
        # keep the label cells clean, put values in the adjacent value column J
        ws["G3"] = "发 票 号 码    INVOICE NO."
        ws["G4"] = "合 同 号 码 CONTRACT NO."
        ws["G5"] = "日 期  DATE"
        for cell, key in (("J3", "invoice_no"), ("J4", "contract_no"), ("J5", "date")):
            val = _text(doc.get(key))
            if val:
                ws[cell] = val
                ws[cell].font = copy.copy(ws[cell].font)
                ws[cell].font = copy.copy(ws[cell].font)
                ws[cell].alignment = Alignment(horizontal="right", vertical="center")
    elif role == "declaration_elements":
        if doc.get("contract_no"):
            ws["C2"] = _text(doc.get("contract_no"))
            ws["C2"].font = copy.copy(ws["C2"].font)
            ws["C2"].font = copy.copy(ws["C2"].font)
        if doc.get("destination_country"):
            ws["G2"] = _text(doc.get("destination_country"))
            ws["G2"].font = copy.copy(ws["G2"].font)
        if doc.get("date"):
            ws["C3"] = _text(doc.get("date"))
    elif role == "sales_confirmation":
        ws.row_dimensions[3].height = 32
        ws.row_dimensions[4].height = 22
        ws.row_dimensions[5].height = 34
        supplier = _text(doc.get("seller_name") or doc.get("supplier_name"))
        supplier_en = _text(doc.get("seller_name_en") or supplier)
        supplier_zh = _text(doc.get("seller_name_zh") or "")
        if supplier_zh:
            ws["C3"] = supplier_zh
            ws["C3"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            if supplier_en:
                ws["C4"] = supplier_en
                ws["C4"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        elif supplier:
            ws["C3"] = supplier
            ws["C3"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            if supplier_en and supplier_en != supplier:
                ws["C4"] = supplier_en
                ws["C4"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        if doc.get("seller_address"):
            ws["C5"] = _text(doc.get("seller_address"))
            ws["C5"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        ws["G3"] = "NO.:"
        ws["G4"] = "DATE:"
        ws["G5"] = "SIGNED AT:"
        if doc.get("contract_no") or doc.get("invoice_no"):
            ws["H3"] = _text(doc.get("contract_no") or doc.get("invoice_no"))
            ws["H3"].alignment = Alignment(horizontal="right", vertical="center")
        if doc.get("date"):
            ws["H4"] = _text(doc.get("date"))
            ws["H4"].alignment = Alignment(horizontal="right", vertical="center")
        if doc.get("signed_at"):
            ws["H5"] = _text(doc.get("signed_at"))
            ws["H5"].alignment = Alignment(horizontal="right", vertical="center")
        if doc.get("buyer") or doc.get("consignee"):
            ws["C11"] = _text(doc.get("buyer") or doc.get("consignee"))
            ws["C11"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        if doc.get("buyer_address"):
            ws["C12"] = _text(doc.get("buyer_address"))
            ws["C12"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        delta = layout.get("sales_delta", 0)
        if doc.get("packing"):
            ws[f"B{24 + delta}"] = _text(doc.get("packing"))
        ws[f"B{25 + delta}"] = "Time of Shipment: On or before: ASAP"
        if doc.get("loading_port"):
            port = _text(doc.get("loading_port"))
            ws[f"A{26 + delta}"] = f"5.装运口岸和目的地: {port} → {_text(doc.get('destination_country') or 'AUSTRALIA')}"
            ws[f"E{26 + delta}"] = ""
        ws[f"F{26 + delta}"] = _text(doc.get("destination_country") or "AUSTRALIA")
        ws[f"F{26 + delta}"].alignment = Alignment(horizontal="left", vertical="center")
        if doc.get("remarks"):
            ws[f"B{34 + delta}"] = _text(doc.get("remarks"))
        if doc.get("shipping_mark"):
            ws[f"B{30 + delta}"] = _text(doc.get("shipping_mark"))
    elif role == "customs_declaration":
        office = _text(doc.get("customs_office") or "")
        ws["H4"] = office or "(XX海关)"
        if doc.get("pre_entry_no"):
            ws["A4"] = f"预录入编号: {doc['pre_entry_no']}"
        if doc.get("customs_no"):
            ws["E4"] = f" 海关编号: {doc['customs_no']}"
        ws["O4"] = "页码/页数: 1/1"
        ws["A6"] = _text(doc.get("seller_name") or doc.get("supplier_name"))
        ws["E6"] = office or _text(doc.get("loading_port"))
        if doc.get("date"):
            ws["H6"] = _text(doc.get("date"))
            ws["K6"] = _text(doc.get("date"))
        ws["A8"] = _text(doc.get("consignee") or doc.get("buyer"))
        ws["E8"] = _text(doc.get("transport") or "海运")
        if doc.get("vessel"):
            ws["H8"] = _text(doc.get("vessel"))
        if doc.get("bl_no"):
            ws["K8"] = _text(doc.get("bl_no"))
        ws["E10"] = _text(doc.get("supervision_mode") or "一般贸易")
        ws["H10"] = _text(doc.get("tax_mode") or "一般征税")
        if doc.get("license_no"):
            ws["K10"] = _text(doc.get("license_no"))
        ws["A12"] = _text(doc.get("contract_no"))
        ws["E12"] = f"=销货确认书!F{layout.get('sales_port_row', 26)}"
        ws["H12"] = "澳大利亚"
        if doc.get("destination_port"):
            ws["K12"] = _text(doc.get("destination_port"))
        if doc.get("loading_port"):
            ws["N12"] = _text(doc.get("loading_port"))
        ws["A14"] = "纸箱"
        total_cartons = sum(int(i.get("cartons") or 0) for i in items)
        total_gross = sum(_num(i.get("gross_weight")) for i in items)
        total_net = sum(_num(i.get("net_weight")) for i in items)
        ws["E14"] = total_cartons
        ws["F14"] = round(total_gross, 2)
        ws["H14"] = round(total_net, 2)
        ws["J14"] = _text(doc.get("incoterm") or "CIF")
        ws["A16"] = "发票、装箱单、合同"
        containers = _text(doc.get("container_no"))
        ws["A18"] = ("N/M 集装箱标箱数及号码：" + containers) if containers else "N/M"
        ws["A18"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        # align all header value cells
        for coord in ("A6", "E6", "H6", "K6", "N6", "A8", "E8", "H8", "K8", "E10", "H10", "K10",
                      "A12", "E12", "H12", "K12", "N12", "A14", "E14", "F14", "H14", "J14"):
            ws[coord].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    # generic vertical centering on filled value cells
    for row in ws.iter_rows():
        for c in row:
            if c.value is not None and c.alignment and c.alignment.vertical is None:
                c.alignment = Alignment(horizontal=c.alignment.horizontal, vertical="center",
                                        wrap_text=c.alignment.wrap_text)


def _item_name(item: dict) -> str:
    return _text(item.get("name_zh") or item.get("name_en") or item.get("model"))


def _item_model(item: dict) -> str:
    return _text(item.get("model") or "")


def _write_data_rows(ws, spec: dict, items: list[dict], snap: dict) -> dict:
    start = spec["data_start"]
    cols = spec["columns"]
    block = spec["block"]
    pattern_rows = spec["pattern_rows"]
    max_col = max(snap["max_col"], max(cols.values(), default=1))
    for idx, item in enumerate(items):
        base = start + idx * block
        for off, src_row in enumerate(pattern_rows):
            dst = base + off
            h = snap["heights"].get(src_row, 24)
            if spec.get("role") == "invoice":
                h = 32
            elif spec.get("role") == "sales_confirmation":
                h = 34
            elif spec.get("role") == "declaration_elements":
                h = 48
            ws.row_dimensions[dst].height = h
        if block == 1:
            values: dict[int, Any] = {}
            for field, col in cols.items():
                if field == "name_en":
                    val = _text(item.get("name_en") or item.get("name_zh"))
                elif field == "name_zh":
                    val = _text(item.get("name_zh") or item.get("name_en"))
                elif field in {"cartons", "pieces_per_carton", "pieces"}:
                    val = int(item.get(field) or 0)
                elif field in {"unit_price"}:
                    val = round(_num(item.get(field)), 4)
                elif field in {"amount"}:
                    val = round(_num(item.get(field)), 2)
                elif field in {"cbm"}:
                    val = round(_num(item.get(field)), 4)
                elif field in {"gross_weight", "net_weight"}:
                    val = round(_num(item.get(field)), 3)
                elif field in {"length", "width", "height"}:
                    val = round(_num(item.get(field)), 2)
                elif field == "no":
                    val = idx + 1
                elif field == "preference":
                    val = _text(item.get("preference") or item.get("preference_eligible") or item.get("tariff_preference") or "")
                elif field == "picture":
                    continue
                else:
                    val = _text(item.get(field))
                values[col] = val
            _copy_row(ws, snap, pattern_rows[0], base, max_col, values, wrap_cols=set(cols.values()))
        else:
            # 2-row merged block (customs declaration)
            for off, src_row in enumerate(pattern_rows):
                _copy_row(ws, snap, src_row, base + off, max_col, {}, clear_unmapped=True)
            # merges for this block
            for c1, c2 in spec.get("merges", []):
                c1i = _col_index(c1)
                c2i = _col_index(c2)
                try:
                    ws.merge_cells(start_row=base, start_column=c1i, end_row=base + 1, end_column=c2i)
                except Exception:
                    pass
            name = _text(item.get("name_zh") or item.get("name_en"))
            spec_text = _text(item.get("model") or "")
            name_spec = f"{name} / {spec_text}" if name and spec_text else (name or spec_text)
            unit = _text(item.get("unit") or "PCS")
            qty = int(item.get("pieces") or 0)
            unit_price = round(_num(item.get("unit_price")), 4)
            amount = round(_num(item.get("amount")), 2)
            currency = _text(item.get("currency") or "USD")
            origin = _text(item.get("origin") or "中国")
            dest = _text(item.get("destination_country") or "澳大利亚")
            source = _text(item.get("source_province") or item.get("domestic_source") or "")
            exempt = _text(item.get("exemption") or "")
            ws.cell(row=base, column=1, value=idx + 1)
            ws.cell(row=base, column=2, value=_text(item.get("hs_code")))
            ws.cell(row=base, column=4, value=name_spec)
            ws.cell(row=base, column=5, value="")  # spec/model already included in D
            ws.cell(row=base, column=7, value="")
            ws.cell(row=base, column=8, value=unit)
            ws.cell(row=base, column=9, value=qty)
            ws.cell(row=base, column=10, value=unit_price)
            ws.cell(row=base, column=11, value=f"{amount} {currency}")
            ws.cell(row=base, column=12, value=origin)
            ws.cell(row=base, column=13, value=dest)
            ws.cell(row=base, column=14, value=source)
            ws.cell(row=base, column=16, value=exempt)
            # style tweaks for values
            for c in range(1, max_col + 1):
                cell = ws.cell(row=base, column=c)
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            ws.cell(row=base, column=4).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            ws.cell(row=base, column=11).alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
            # merge rows for the value columns (already merged above for A/B..P)
            for c in range(1, max_col + 1):
                try:
                    ws.cell(row=base + 1, column=c)
                except Exception:
                    pass
    return {"data_start": start, "data_end": start + len(items) * block - 1, "count": len(items)}


def _col_index(letter: str) -> int:
    n = 0
    for ch in letter.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def _build_footer(ws, spec: dict, snap: dict, items: list[dict], data_end: int, doc: dict) -> int:
    footer_src = spec.get("footer_rows") or []
    if not footer_src:
        return data_end
    delta = data_end + 1 - spec["footer_start"]
    max_col = max(snap["max_col"], spec.get("print_cols", 1))
    for src_row in footer_src:
        dst = src_row + delta
        _copy_row(ws, snap, src_row, dst, max_col, {}, clear_unmapped=False, copy_values=True)
        if src_row in snap["heights"]:
            ws.row_dimensions[dst].height = snap["heights"][src_row]
    for r1, c1, r2, c2 in snap["merges"]:
        if r1 >= spec["footer_start"]:
            try:
                ws.merge_cells(start_row=r1 + delta, start_column=c1, end_row=r2 + delta, end_column=c2)
            except Exception:
                pass
    return spec["footer_start"] + delta + (max(footer_src) - spec["footer_start"]) if footer_src else data_end


def _set_totals(ws, role: str, spec: dict, items: list[dict], data_start: int, data_end: int, data_count: int) -> int:
    total = data_end + 1
    if role == "packing_list":
        # A{total}:G{total} is merged; CBM and G.W. are the visible totals in this layout.
        ws[f"L{total}"] = round(sum(_num(i.get("cbm")) for i in items), 4)
        ws[f"M{total}"] = round(sum(_num(i.get("gross_weight")) for i in items), 3)
        for coord in (f"L{total}", f"M{total}"):
            fnt = copy.copy(ws[coord].font)
            fnt.bold = True
            ws[coord].font = fnt
            ws[coord].alignment = Alignment(horizontal="center", vertical="center")
            ws[coord].number_format = "0.000" if coord.startswith("L") else "0.00"
        ws[f"O{total}"] = sum(int(i.get("cartons") or 0) for i in items)
        ws[f"P{total}"] = sum(int(i.get("pieces") or 0) for i in items)
    elif role == "invoice":
        ws[f"F{total}"] = sum(int(i.get("cartons") or 0) for i in items)
        ws[f"H{total}"] = sum(int(i.get("pieces") or 0) for i in items)
        ws[f"J{total}"] = round(sum(_num(i.get("amount")) for i in items), 2)
        for coord in (f"F{total}", f"H{total}", f"J{total}"):
            fnt = copy.copy(ws[coord].font)
            fnt.bold = True
            ws[coord].font = fnt
            ws[coord].alignment = Alignment(horizontal="center", vertical="center")
            ws[coord].number_format = "#,##0.00" if coord.startswith("J") else "0"
    elif role == "sales_confirmation":
        ws[f"H{total}"] = round(sum(_num(i.get("amount")) for i in items), 2)
        fnt = copy.copy(ws[f"H{total}"].font)
        fnt.bold = True
        ws[f"H{total}"].font = fnt
        ws[f"H{total}"].alignment = Alignment(horizontal="center", vertical="center")
        ws[f"H{total}"].number_format = "#,##0.00"
    return total


def _format_data(ws, role: str, rows: list[int], spec: dict) -> None:
    cols = spec["columns"]
    for r in rows:
        for field in ("unit_price", "amount"):
            c = cols.get(field)
            if c:
                ws.cell(row=r, column=c).number_format = "#,##0.00"
        for field in ("cartons", "pieces_per_carton", "pieces"):
            c = cols.get(field)
            if c:
                ws.cell(row=r, column=c).number_format = "0"
        for field in ("cbm",):
            c = cols.get(field)
            if c:
                ws.cell(row=r, column=c).number_format = "0.000"
        for field in ("gross_weight", "net_weight"):
            c = cols.get(field)
            if c:
                ws.cell(row=r, column=c).number_format = "0.00"
        if role == "customs_declaration":
            for c in (10, 9, 8):
                ws.cell(row=r, column=c).number_format = "0.00" if c == 10 else "0"


def fill_workbook(template_path: str | Path, payload: dict, output_path: str | Path) -> dict:
    """Fill the 5-sheet template, preserving styles and repairing formulas."""
    template_path = Path(template_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = load_workbook(str(template_path), data_only=False)
    items = payload.get("items") or []
    doc = payload.get("doc") or {}
    if not items:
        raise ValueError("payload.items 为空，无法生成模板")
    report = {"sheets": [], "items": len(items), "formulas": [], "warnings": []}
    totals_by_role = {}
    for ws in wb.worksheets:
        canon = _canon_sheet(ws.title)
        if not canon:
            report["warnings"].append(f"未识别的 Sheet：{ws.title}，已原样保留")
            continue
        spec = SHEET_SPECS[canon]
        snap = _capture(ws)
        _clear_sheet(ws)
        # header
        for r in range(1, spec["header_end"] + 1):
            for c in range(1, max(snap["max_col"], spec["print_cols"]) + 1):
                s = snap["cells"].get((r, c))
                _put(ws, r, c, s, s["value"] if s else None, has_value=bool(s and s["value"] is not None))
            if r in snap["heights"]:
                ws.row_dimensions[r].height = snap["heights"][r]
        for r1, c1, r2, c2 in snap["merges"]:
            if r2 <= spec["header_end"]:
                try:
                    ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)
                except Exception:
                    pass
        if spec["role"] == "sales_confirmation":
            # give the seller/address block room to breathe (template left these unmerged)
            for r in (3, 4, 5):
                try:
                    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
                except Exception:
                    pass
        # data
        layout = _write_data_rows(ws, spec, items, snap)
        # footer
        footer_total_row = _build_footer(ws, spec, snap, items, layout["data_end"], doc)
        total_row = _set_totals(ws, spec["role"], spec, items, spec["data_start"], layout["data_end"], len(items))
        sales_delta = len(items) - 2
        sales_port_row = 26 + sales_delta
        # header values AFTER data layout (some formulas reference sales rows)
        _fill_header(ws, spec["role"], doc, items, {
            "total_row": total_row,
            "spec": spec,
            "packing_note_row": total_row + 2,
            "sales_delta": sales_delta,
            "sales_port_row": sales_port_row,
        })
        _format_data(ws, spec["role"], list(range(layout["data_start"], layout["data_end"] + 1)), spec)
        # formulas
        if spec["role"] == "packing_list":
            for col in ("L", "M"):
                ws[f"{col}{total_row}"] = f"=SUM({col}{layout['data_start']}:{col}{layout['data_end']})"
                report["formulas"].append(f"{ws.title}!{col}{total_row}")
        elif spec["role"] == "invoice":
            for col in ("F", "H", "J"):
                ws[f"{col}{total_row}"] = f"=SUM({col}{layout['data_start']}:{col}{layout['data_end']})"
                report["formulas"].append(f"{ws.title}!{col}{total_row}")
        elif spec["role"] == "sales_confirmation":
            ws[f"H{total_row}"] = f"=SUM(H{layout['data_start']}:H{layout['data_end']})"
            report["formulas"].append(f"{ws.title}!H{total_row}")
        elif spec["role"] == "customs_declaration":
            # preserve same-sheet + cross-sheet formulas
            ws["A10"] = "=A6"
            report["formulas"].append(f"{ws.title}!A10")
            sc = wb["销货确认书"] if "销货确认书" in wb.sheetnames else None
            if sc is not None:
                for idx in range(len(items)):
                    base = layout["data_start"] + idx * 2
                    sc_row = 21 + idx
                    ws.cell(row=base, column=4, value=f"=销货确认书!C{sc_row}")
                    ws.cell(row=base, column=9, value=f"=销货确认书!F{sc_row}")
                    report["formulas"].extend([f"{ws.title}!D{base}", f"{ws.title}!I{base}"])
            ws["E12"] = f"=销货确认书!F{sales_port_row}"
            report["formulas"].append(f"{ws.title}!E12")
        # page setup: fit to one page wide, landscape
        try:
            ws.page_setup.orientation = "landscape"
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 1
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.print_options.horizontalCentered = True
            last = total_row if spec["role"] != "customs_declaration" else footer_total_row
            if spec["role"] == "sales_confirmation":
                last = footer_total_row
            if spec["role"] == "customs_declaration":
                last = footer_total_row
            ws.print_area = f"A1:{get_column_letter(spec['print_cols'])}{max(last, spec['header_end'] + 1)}"
        except Exception:
            pass
        totals_by_role[spec["role"]] = {"total_row": total_row, "data_start": layout["data_start"], "data_end": layout["data_end"]}
        report["sheets"].append({
            "name": ws.title,
            "role": spec["role"],
            "data_rows": len(items),
            "total_row": total_row,
            "merged_cells": len(ws.merged_cells.ranges),
        })
    # sales confirmation totals must be computed after customs formulas reference SC rows
    wb.save(str(output_path))
    report["output"] = str(output_path)
    report["output_size"] = output_path.stat().st_size
    report["sheets_found"] = wb.sheetnames
    report["totals"] = totals_by_role
    return report


# ---------------------------------------------------------------------------
# public helpers
# ---------------------------------------------------------------------------
def inspect_template(template_path: str | Path) -> dict:
    wb = load_workbook(str(template_path), data_only=False)
    sheets = []
    for ws in wb.worksheets:
        canon = _canon_sheet(ws.title)
        spec = SHEET_SPECS.get(canon) if canon else None
        sheets.append({
            "name": ws.title,
            "canonical": canon,
            "dim": ws.calculate_dimension(),
            "role": spec["role"] if spec else "unmapped",
            "header_end": spec["header_end"] if spec else None,
            "data_start": spec["data_start"] if spec else None,
            "columns": ({name: get_column_letter(col) for name, col in spec["columns"].items()} if spec else {}),
            "print_area": str(ws.print_area) if ws.print_area else "",
        })
    return {"filename": Path(template_path).name, "sheets": sheets, "mapping_version": 1}


def _main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: generated_fill.py <template.xlsx> <payload.json> <output.xlsx>")
        return 2
    tpl, payload_path, out = argv[1], argv[2], argv[3]
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    report = fill_workbook(tpl, payload, out)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
