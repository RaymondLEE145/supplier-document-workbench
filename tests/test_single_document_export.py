# -*- coding: utf-8 -*-
"""Regression: single-document uploads must not populate unrelated sheets."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openpyxl import load_workbook

from app.services import parser, merge, template_engine

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "assets" / "template.xlsx"
OUT = ROOT / "data" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

CASES = {
    "packing_only": ROOT / "testdata/supplier_b_foshan_sunrise/packing_list.xlsx",
    "invoice_only": ROOT / "testdata/supplier_b_foshan_sunrise/commercial_invoice.xlsx",
}


def blank(ws, row, col):
    v = ws.cell(row=row, column=col).value
    return v in (None, "")


def run(name: str, path: Path) -> dict:
    doc = parser.parse_file(path, path.name)
    if not doc.get("ok"):
        raise SystemExit(f"parse failed {name}: {doc.get('error')}")
    analysis = merge.aggregate([{**doc, "file_id": "f1", "supplier_id": "s1", "filename": path.name, "status": "parsed"}],
                               [{"id": "s1", "name": "TEST"}])
    coverage = analysis["coverage"]
    payload = {"doc": analysis["doc"], "items": analysis["items"], "coverage": coverage}
    out = OUT / f"single_{name}.xlsx"
    template_engine.fill_workbook(TPL, payload, out)
    wb = load_workbook(out, data_only=False)
    report = {"case": name, "type": doc.get("type"), "items": len(analysis["items"]),
              "coverage": coverage, "file": str(out)}
    packing = next(s for s in wb.worksheets if "装箱" in s.title)
    invoice = next(s for s in wb.worksheets if "发票" in s.title)
    sales = next(s for s in wb.worksheets if "销售" in s.title or "销货" in s.title)
    customs = next(s for s in wb.worksheets if "报关" in s.title)
    decl = next(s for s in wb.worksheets if "申报" in s.title)
    report["packing_C6"] = packing["C6"].value
    report["invoice_J10"] = invoice["J10"].value
    report["sales_H21"] = sales["H21"].value
    report["customs_B20"] = customs["B20"].value
    report["decl_C5"] = decl["C5"].value
    if name == "packing_only":
        assert coverage["packing_list"] and not coverage["invoice"], coverage
        assert packing["C6"].value, "packing sheet not filled"
        for label, ws, coord in (("invoice", invoice, "J10"), ("sales", sales, "H21"),
                                 ("customs", customs, "B20"), ("decl", decl, "C5")):
            assert blank(ws, int("".join(filter(str.isdigit, coord))), ws[coord].column), f"{label} not blank: {ws[coord].value}"
    if name == "invoice_only":
        assert coverage["invoice"] and not coverage["packing_list"], coverage
        assert invoice["J10"].value not in (None, ""), "invoice amount missing"
        for label, ws, coord in (("packing", packing, "C6"), ("sales", sales, "H21"),
                                 ("customs", customs, "B20"), ("decl", decl, "C5")):
            assert blank(ws, int("".join(filter(str.isdigit, coord))), ws[coord].column), f"{label} not blank: {ws[coord].value}"
    return report


if __name__ == "__main__":
    reports = [run(k, v) for k, v in CASES.items()]
    print(json.dumps(reports, ensure_ascii=False, indent=1))
