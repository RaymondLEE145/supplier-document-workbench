# -*- coding: utf-8 -*-
"""Regression: single-document uploads only fill document-specific sheets, while customs
declaration and official declaration elements are generated from HS/product data."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openpyxl import load_workbook

from app.services import parser, merge, template_engine, declaration
from app.services.exporter import validate_workbook

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "assets" / "template.xlsx"
OUT = ROOT / "data" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

CASES = {
    "packing_only": ROOT / "testdata/supplier_b_foshan_sunrise/packing_list.xlsx",
    "invoice_only": ROOT / "testdata/supplier_b_foshan_sunrise/commercial_invoice.xlsx",
}


def run(name: str, path: Path) -> dict:
    doc = parser.parse_file(path, path.name)
    assert doc.get("ok"), doc
    analysis = merge.aggregate([{**doc, "file_id": "f1", "supplier_id": "s1", "filename": path.name, "status": "parsed"}],
                               [{"id": "s1", "name": "TEST"}])
    coverage = analysis["coverage"]
    declaration.enrich(analysis["items"])
    payload = {"doc": analysis["doc"], "items": analysis["items"], "coverage": coverage}
    out = OUT / f"single_{name}.xlsx"
    template_engine.fill_workbook(TPL, payload, out)
    wb = load_workbook(out, data_only=False)
    report = {"case": name, "type": doc.get("type"), "items": len(analysis["items"]),
              "coverage": coverage, "file": str(out)}
    packing = wb.worksheets[0]
    invoice = wb.worksheets[1]
    decl = wb.worksheets[2]
    sales = wb.worksheets[3]
    customs = wb.worksheets[4]
    report["packing_C6"] = packing["C6"].value
    report["invoice_J10"] = invoice["J10"].value
    report["decl_C5"] = decl["C5"].value
    report["decl_D5"] = decl["D5"].value
    report["decl_B5"] = decl["B5"].value
    report["decl_F5"] = decl["F5"].value
    report["sales_H21"] = sales["H21"].value
    report["customs_B20"] = customs["B20"].value
    report["customs_D20"] = customs["D20"].value
    report["customs_I20"] = customs["I20"].value
    if name == "packing_only":
        assert coverage["packing_list"] and not coverage["invoice"] and not coverage["sales_confirmation"], coverage
        assert coverage["customs_declaration"] and coverage["declaration_elements"]
        assert packing["C6"].value, "packing sheet not filled"
        assert invoice["J10"].value in (None, ""), "invoice must be blank"
        assert sales["H21"].value in (None, ""), "sales must be blank"
        assert customs["B20"].value, "customs item HS missing"
        assert decl["C5"].value, "declaration name missing"
        assert decl["D5"].value, "declaration HS missing"
    if name == "invoice_only":
        assert coverage["invoice"] and not coverage["packing_list"] and not coverage["sales_confirmation"], coverage
        assert invoice["J10"].value not in (None, ""), "invoice amount missing"
        assert packing["C6"].value in (None, ""), "packing must be blank"
        assert sales["H21"].value in (None, ""), "sales must be blank"
        assert customs["B20"].value, "customs item HS missing"
        assert decl["C5"].value, "declaration name missing"
    v = validate_workbook(TPL, out, payload)
    report["validation"] = {"ok": v["ok"], "passed": v["passed"], "failed": v["failed"], "warnings": v["warnings"]}
    assert v["ok"], [c for c in v["checks"] if not c["ok"]]
    return report


if __name__ == "__main__":
    reports = [run(k, v) for k, v in CASES.items()]
    print(json.dumps(reports, ensure_ascii=False, indent=1))
