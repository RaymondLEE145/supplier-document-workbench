# -*- coding: utf-8 -*-
"""Export orchestration: gate -> payload -> generated script -> WPS recalc -> audit."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from ..config import OUTPUT_DIR, SCRIPT_DIR, new_id, now_iso
from . import codegen
from .compliance import reconcile


class ExportBlocked(Exception):
    def __init__(self, message: str, gate: dict):
        super().__init__(message)
        self.gate = gate


def _city(dest: str) -> str:
    d = str(dest or "").upper()
    for city in ["MELBOURNE", "SYDNEY", "BRISBANE", "PERTH", "ADELAIDE", "FREMANTLE", "HOBART"]:
        if city in d:
            return city
    return str(dest or "").split(",")[0].strip().upper()


def _customs_office(loading_port: str) -> str:
    p = str(loading_port or "").upper()
    for k, v in [("NINGBO", "宁波海关"), ("SHENZHEN", "深圳海关"), ("GUANGZHOU", "广州海关"),
                 ("SHANGHAI", "上海海关"), ("TIANJIN", "天津海关"), ("QINGDAO", "青岛海关"),
                 ("XIAMEN", "厦门海关"), ("DALIAN", "大连海关")]:
        if k in p:
            return v
    return ""


def build_payload(analysis: dict, compliance: dict, *, acknowledge_unsupported: bool = False) -> tuple[dict, dict]:
    items, gate = reconcile(analysis.get("items") or [], compliance or {})
    gate["acknowledge_unsupported"] = bool(acknowledge_unsupported)
    if not gate.get("ok") and not acknowledge_unsupported:
        raise ExportBlocked("合规校验未通过：存在未确认的溯源数据或缺少 HS 编码，已阻断导出。", gate)
    if not items:
        raise ExportBlocked("没有可导出的货物行。", gate)
    doc = dict(analysis.get("doc") or {})
    doc["destination_country"] = doc.get("destination_country") or ""
    doc["destination_port"] = _city(doc.get("destination_port") or doc.get("destination") or "")
    doc["loading_port"] = str(doc.get("loading_port") or "").split(",")[0].strip()
    doc["customs_office"] = doc.get("customs_office") or _customs_office(doc.get("loading_port", ""))
    doc["packing"] = doc.get("packing") or ""
    doc["transport"] = doc.get("transport") or ""
    doc["supervision_mode"] = doc.get("supervision_mode") or ""
    doc["tax_mode"] = doc.get("tax_mode") or ""
    doc["currency"] = doc.get("currency") or ""
    doc["incoterm"] = doc.get("incoterm") or ""
    doc["shipping_mark"] = doc.get("shipping_mark") or ""
    doc["signed_at"] = doc.get("signed_at") or ""
    doc["seller_name_en"] = doc.get("seller_name_en") or doc.get("seller_name") or doc.get("supplier_name")
    doc["seller_address"] = doc.get("seller_address") or ""
    doc["buyer_address"] = doc.get("buyer_address") or ""
    if not doc.get("remarks"):
        doc["remarks"] = ""
    coverage = doc.get("coverage") or analysis.get("coverage") or {}
    if not coverage:
        types = {str(d.get("type") or "unknown") for d in (analysis.get("documents") or [])}
        coverage = {
            "packing_list": bool(types & {"packing_list", "combined"}),
            "invoice": bool(types & {"invoice", "combined"}),
            "sales_confirmation": "contract" in types,
            "customs_declaration": "customs_declaration" in types,
            "declaration_elements": bool(types & {"declaration_elements", "customs_declaration"}),
        }
    coverage = {k: bool(coverage.get(k)) for k in ("packing_list", "invoice", "sales_confirmation",
                                                    "customs_declaration", "declaration_elements")}
    if not any(coverage.values()):
        raise ExportBlocked("未识别到装箱单/发票/合同/报关单，无法确定应填写哪张表；请先识别单证类型。", gate)
    doc["coverage"] = coverage
    for idx, it in enumerate(items, start=1):
        it["no"] = idx
        it["currency"] = it.get("currency") or ""
        it["unit"] = it.get("unit") or ""
        it["origin"] = it.get("origin") or ""
        it["packing"] = it.get("packing") or doc.get("packing") or ""
        pref = it.get("preference_eligible") or ""
        if "CONDITIONAL" in pref.upper():
            it["preference"] = "CONDITIONAL"
        elif "CHAFTA" in pref.upper():
            m = re.search(r"(\d+(?:\.\d+)?%)", pref)
            it["preference"] = "ChAFTA" + ((" " + m.group(1)) if m else "")
        elif "MFN" in pref.upper() or "ABF" in pref.upper():
            it["preference"] = "MFN"
        else:
            it["preference"] = pref[:40]
        it["destination_country"] = it.get("destination_country") or doc.get("destination_country") or ""
    payload = {
        "meta": {
            "generated_at": now_iso(),
            "source_documents": len(analysis.get("documents") or []),
            "suppliers": len(analysis.get("supplier_names") or []),
            "deduplicated": (analysis.get("totals") or {}).get("duplicates_removed", 0),
            "gate": gate,
        },
        "coverage": coverage,
        "doc": doc,
        "items": items,
    }
    return payload, gate


def recalc_with_wps(path: Path, timeout: int = 90) -> dict:
    path = Path(path).resolve()
    ps = f"""
$ErrorActionPreference = 'Stop'
$wps = New-Object -ComObject KET.Application
$wps.Visible = $false
$wps.DisplayAlerts = $false
try {{
  $wb = $wps.Workbooks.Open('{str(path).replace("'", "''")}')
  try {{ $wb.Application.Calculate() }} catch {{ }}
  try {{ $wb.Calculate() }} catch {{ }}
  $wb.Save()
  $wb.Close($false)
  'WPS_OK'
}} finally {{
  try {{ $wps.Quit() }} catch {{ }}
}}
"""
    t0 = time.time()
    try:
        proc = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        ok = proc.returncode == 0 and "WPS_OK" in (proc.stdout or "")
        return {"ok": ok, "elapsed_ms": int((time.time() - t0) * 1000), "stdout": (proc.stdout or "")[-1000:],
                "stderr": (proc.stderr or "")[-2000:], "method": "WPS COM KET.Application"}
    except Exception as exc:
        return {"ok": False, "elapsed_ms": int((time.time() - t0) * 1000), "error": f"{type(exc).__name__}: {exc}", "method": "WPS COM KET.Application"}


def _style_fp(cell) -> tuple:
    return (
        bool(cell.font.bold), cell.font.sz, cell.font.name or "",
        (cell.fill.fgColor.rgb if cell.fill and cell.fill.fill_type else None),
        cell.border.left.style, cell.border.right.style, cell.border.top.style, cell.border.bottom.style,
        cell.number_format,
    )


HEADER_CELLS = {
    "装箱清单": ["A1", "A4", "B4", "C4", "E4", "F4", "G4", "H4", "I4", "M4", "N4"],
    "发票": ["A1", "A8", "B8", "D8", "E8", "F8", "G8", "H8", "I8", "J8"],
    "申报要素": ["A1", "A4", "B4", "C4", "D4", "F4", "J4"],
    "销货确认书": ["A1", "A2", "A18", "C18", "E18", "G18", "H18"],
    "报关单 ": ["A1", "A4", "A5", "B19", "D19", "H19", "J19", "L19", "P19"],
}


def validate_workbook(template_path: Path, output_path: Path, payload: dict) -> dict:
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "", severity: str = "error") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})

    try:
        wb = load_workbook(output_path, data_only=False)
        wbv = load_workbook(output_path, data_only=True)
        tpl = load_workbook(template_path, data_only=False)
    except Exception as exc:
        return {"ok": False, "checks": [{"name": "工作簿可读取", "ok": False, "detail": str(exc), "severity": "error"}]}

    expected_sheets = tpl.sheetnames
    check("5 个 Sheet 完整", wb.sheetnames == expected_sheets, f"实际: {wb.sheetnames}")
    items = payload.get("items") or []
    doc = payload.get("doc") or {}
    coverage = payload.get("coverage") or {}
    n = len(items)

    def sheet(name: str):
        for s in wb.worksheets:
            if s.title.strip() == name.strip():
                return s
        return None

    # header style preservation
    style_diffs = []
    for name, cells in HEADER_CELLS.items():
        ws = sheet(name)
        tws = next((s for s in tpl.worksheets if s.title.strip() == name.strip()), None)
        if not ws or not tws:
            continue
        for coord in cells:
            if _style_fp(ws[coord]) != _style_fp(tws[coord]):
                style_diffs.append(f"{name}!{coord}")
    check("表头样式（字体/底色/边框/数字格式）保持不变", not style_diffs,
          ("差异: " + ", ".join(style_diffs[:12])) if style_diffs else "全部关键表头样式指纹一致")

    # packed data
    ws = sheet("装箱清单")
    if ws and coverage.get("packing_list", True):
        bad = []
        for idx, it in enumerate(items):
            r = 6 + idx
            if str(ws[f"C{r}"].value or "") != str(it.get("name_en") or it.get("name_zh") or ""):
                bad.append(f"C{r}")
            if str(ws[f"D{r}"].value or "") != str(it.get("name_zh") or it.get("name_en") or ""):
                bad.append(f"D{r}")
            if str(ws[f"E{r}"].value or "") != str(it.get("hs_code") or ""):
                bad.append(f"E{r}")
            if int(ws[f"G{r}"].value or 0) != int(it.get("cartons") or 0):
                bad.append(f"G{r}")
        check("装箱清单 品名/HS/箱数 精准回填", not bad, ("错位单元格: " + ", ".join(bad[:12])) if bad else f"{n} 行全部匹配")
        # totals: CBM + G.W. formulas; cartons/pieces helpers in O/P (template convention)
        total_row = 6 + n
        fl = str(ws[f"L{total_row}"].value or "")
        fm = str(ws[f"M{total_row}"].value or "")
        check("装箱清单 CBM/毛重合计公式已重写",
              fl == f"=SUM(L6:L{6 + n - 1})" and fm == f"=SUM(M6:M{6 + n - 1})", f"{fl} | {fm}")
        check("装箱清单 箱数/件数合计（O/P 辅助列）",
              int(ws[f"O{total_row}"].value or 0) == sum(int(i.get("cartons") or 0) for i in items)
              and int(ws[f"P{total_row}"].value or 0) == sum(int(i.get("pieces") or 0) for i in items),
              f"O={ws[f'O{total_row}'].value}, P={ws[f'P{total_row}'].value}")
        cached_l = wbv["装箱清单"][f"L{total_row}"].value
        expected_l = round(sum(float(i.get("cbm") or 0) for i in items), 4)
        check("装箱清单 CBM 合计值可计算", cached_l is None or abs(float(cached_l) - expected_l) < 0.02,
              f"cached={cached_l}, expected={expected_l}", severity="warning")

    # invoice
    ws = sheet("发票")
    if ws and coverage.get("invoice", True):
        bad = []
        for idx, it in enumerate(items):
            r = 10 + idx
            if str(ws[f"B{r}"].value or "") != str(it.get("name_en") or it.get("name_zh") or ""):
                bad.append(f"B{r}")
            if str(ws[f"D{r}"].value or "") != str(it.get("hs_code") or ""):
                bad.append(f"D{r}")
            if round(float(ws[f"J{r}"].value or 0), 2) != round(float(it.get("amount") or 0), 2):
                bad.append(f"J{r}")
        check("发票 品名/HS/金额 精准回填", not bad, ("错位: " + ", ".join(bad[:12])) if bad else f"{n} 行全部匹配")
        formula = str(ws[f"J{10 + n}"].value or "")
        check("发票 金额合计公式已重写", formula == f"=SUM(J10:J{10 + n - 1})", formula)

    # declaration elements
    ws = sheet("申报要素")
    if ws and coverage.get("declaration_elements", True):
        bad = []
        for idx, it in enumerate(items):
            r = 5 + idx
            if str(ws[f"C{r}"].value or "") != str(it.get("name_zh") or it.get("name_en") or ""):
                bad.append(f"C{r}")
            if str(ws[f"D{r}"].value or "") != str(it.get("hs_code") or ""):
                bad.append(f"D{r}")
        check("申报要素 品名/HS 精准回填", not bad, ("错位: " + ", ".join(bad[:12])) if bad else f"{n} 行全部匹配")

    # sales confirmation
    ws = sheet("销货确认书")
    if ws and coverage.get("sales_confirmation", True):
        bad = []
        for idx, it in enumerate(items):
            r = 21 + idx
            if str(ws[f"C{r}"].value or "") != str(it.get("name_zh") or it.get("name_en") or ""):
                bad.append(f"C{r}")
            if int(ws[f"F{r}"].value or 0) != int(it.get("pieces") or 0):
                bad.append(f"F{r}")
            if round(float(ws[f"H{r}"].value or 0), 2) != round(float(it.get("amount") or 0), 2):
                bad.append(f"H{r}")
        check("销货确认书 品名/数量/金额 精准回填", not bad, ("错位: " + ", ".join(bad[:12])) if bad else f"{n} 行全部匹配")
        formula = str(ws[f"H{21 + n}"].value or "")
        check("销货确认书 金额合计公式已重写", formula == f"=SUM(H21:H{20 + n})", formula)
        if doc.get("seller_name") or doc.get("seller_name_zh"):
            expected_sellers = {str(doc.get(k) or "") for k in ("seller_name", "seller_name_zh", "seller_name_en")} - {""}
            check("销货确认书 卖方信息回填", str(ws["C3"].value or "") in expected_sellers,
                  f"C3={ws['C3'].value}; expected one of {sorted(expected_sellers)}")
        if doc.get("contract_no"):
            check("销货确认书 合同号回填", str(ws["H3"].value or "") == str(doc.get("contract_no")), str(ws["H3"].value or ""))

    # customs declaration
    ws = sheet("报关单 ")
    if ws and coverage.get("customs_declaration", True):
        bad = []
        for idx, it in enumerate(items):
            r = 20 + idx * 2
            if str(ws[f"B{r}"].value or "") != str(it.get("hs_code") or ""):
                bad.append(f"B{r}")
            if str(ws[f"H{r}"].value or "").upper() not in {"PCS", "件"} and (it.get("unit") or ""):
                bad.append(f"H{r}")
            if coverage.get("sales_confirmation", True):
                if str(ws[f"I{r}"].value or "") != f"=销货确认书!F{21 + idx}":
                    bad.append(f"I{r}")
                if str(ws[f"D{r}"].value or "") != f"=销货确认书!C{21 + idx}":
                    bad.append(f"D{r}")
            else:
                if str(ws[f"D{r}"].value or "") != str(it.get("name_zh") or it.get("name_en") or ""):
                    bad.append(f"D{r}")
                if str(ws[f"I{r}"].value or "") != str(it.get("pieces") or ""):
                    bad.append(f"I{r}")
        check("报关单 商品项（HS/数量单位/跨表公式）", not bad, ("错位: " + ", ".join(bad[:12])) if bad else f"{n} 个商品项")
        check("报关单 合同号", str(ws["A12"].value or "") == str(doc.get("contract_no") or ""), str(ws["A12"].value or ""))
        check("报关单 贸易国/运抵国", str(ws["H12"].value or "") == str(doc.get("destination_country") or ""), str(ws["H12"].value or ""))
        check("报关单 成交方式", str(ws["J14"].value or "") == str(doc.get("incoterm") or ""), str(ws["J14"].value or ""))
        check("报关单 页码占位已替换", "(XX海关)" != str(ws["H4"].value or "") or not doc.get("customs_office"), str(ws["H4"].value or ""), severity="warning")

    # formulas / errors
    bad_formulas = []
    for s in wb.worksheets:
        for row in s.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    if "#REF!" in c.value or "#VALUE!" in c.value or "#NAME?" in c.value:
                        bad_formulas.append(f"{s.title}!{c.coordinate}")
    check("无损坏公式（#REF!/#VALUE!/#NAME?）", not bad_formulas, ", ".join(bad_formulas[:10]))
    # placeholder / stale sample check
    stale = []
    for s in wb.worksheets:
        for row in s.iter_rows():
            for c in row:
                if c.value in {"JYXD-26-04-8-01", "11090", "9997"}:
                    stale.append(f"{s.title}!{c.coordinate}={c.value}")
    check("无模板示例残留值", not stale, ", ".join(stale[:10]), severity="warning")

    errors = [c for c in checks if not c["ok"] and c["severity"] == "error"]
    warnings = [c for c in checks if not c["ok"] and c["severity"] == "warning"]
    report = {
        "ok": not errors,
        "checks": checks,
        "passed": sum(1 for c in checks if c["ok"]),
        "failed": len(errors),
        "warnings": len(warnings),
        "sheet_names": wb.sheetnames,
        "styles_preserved": not style_diffs,
        "formula_cached_available": (wbv["发票"][f"J{10 + n}"].value is not None
                                     if coverage.get("invoice", True) and n else False),
    }
    return report


def export(analysis: dict, compliance: dict, template_path: Path, state_settings: dict,
           *, acknowledge_unsupported: bool = False, output_name: str = "") -> dict:
    export_id = new_id("exp_")
    payload, gate = build_payload(analysis, compliance, acknowledge_unsupported=acknowledge_unsupported)
    if not output_name:
        supplier = (analysis.get("doc") or {}).get("supplier_name") or "出口文件"
        safe_supplier = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", str(supplier))[:40] or "出口文件"
        output_name = f"出口文件_{safe_supplier}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_name = re.sub(r"[^\w\u4e00-\u9fff.\-]+", "_", Path(output_name).name or "export.xlsx")
    if not output_name.lower().endswith(".xlsx"):
        output_name += ".xlsx"
    output_path = OUTPUT_DIR / f"{export_id}_{output_name}"
    script_path = SCRIPT_DIR / f"generated_fill_{export_id}.py"
    payload_path = SCRIPT_DIR / f"payload_{export_id}.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    tpl_inspection = {"sheets": [{"name": s.title, "dim": s.calculate_dimension()} for s in load_workbook(template_path).worksheets]}
    engine = "structural"
    llm_note = "LLM not configured; deterministic structural code generation used."
    llm_status = {"enabled": False, "used": False, "note": "LLM 未配置（可在设置中填写 API Key）"}
    settings = state_settings or {}
    if (settings.get("llm") or {}).get("enabled") and (settings.get("llm") or {}).get("api_key"):
        # reserved: LLM script generation. Canonical engine remains the safe execution path.
        llm_status = {"enabled": True, "used": False,
                      "note": "LLM 已配置；为保障模板样式/公式可靠性，本次仍由结构代码生成器执行，LLM 脚本可作为预览。"}
    generated = codegen.generate_script(payload, template_path, output_path, script_path, engine=engine, llm_note=llm_note)
    t0 = time.time()
    run = codegen.run_script(script_path, template_path, output_path, timeout=120)
    if not run["ok"]:
        raise RuntimeError(f"生成的填充脚本执行失败：{run['stderr'][-1500:] or run['stdout'][-1500:]}")
    recalc = recalc_with_wps(output_path)
    validation = validate_workbook(template_path, output_path, payload)
    if not validation.get("ok"):
        raise RuntimeError("回填结果校验未通过：" + json.dumps([c for c in validation["checks"] if not c["ok"] and c["severity"] == "error"], ensure_ascii=False)[:2000])
    record = {
        "id": export_id,
        "filename": output_path.name,
        "path": str(output_path),
        "script_path": str(script_path),
        "payload_path": str(payload_path),
        "size": output_path.stat().st_size,
        "created_at": now_iso(),
        "duration_ms": int((time.time() - t0) * 1000),
        "gate": gate,
        "coverage": payload.get("coverage") or {},
        "validation": validation,
        "recalc": recalc,
        "engine": engine,
        "llm": llm_status,
        "script_preview": script_path.read_text(encoding="utf-8")[:12000],
        "download_url": f"/api/download/{export_id}",
        "template": str(template_path),
        "item_count": len(payload["items"]),
    }
    return record
