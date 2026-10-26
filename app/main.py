# -*- coding: utf-8 -*-
"""FastAPI application for the Supplier Document Workbench."""
from __future__ import annotations

import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import load_workbook

from .config import (ALLOWED_EXTENSIONS, ASSETS_DIR, DATA_DIR, DEFAULT_TEMPLATE, MAX_UPLOAD_BYTES,
                     OUTPUT_DIR, SCRIPT_DIR, STATIC_DIR, TEMPLATE_DIR, UPLOAD_DIR, load_settings,
                     new_id, now_iso, safe_filename, save_settings)
from .services import codegen, compliance as compliance_service, exporter, parser, template_engine
from .services import jobs as job_service
from .services.merge import aggregate
from .store import (file_sha256, find_supplier, inspect_template, load_state, log_activity, mutate,
                    save_state, snapshot, supplier_documents, supplier_files)

app = FastAPI(title="供应商单证工作台 / Supplier Document Workbench", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def no_store_api(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# local test fixtures (used by the browser E2E and the "载入演示" flow)
_TESTDATA = Path(__file__).resolve().parents[1] / "testdata"
if _TESTDATA.exists():
    app.mount("/testdata", StaticFiles(directory=str(_TESTDATA)), name="testdata")

START_TS = time.time()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _ensure_template(state: dict) -> None:
    if state.get("template"):
        return
    tpl = TEMPLATE_DIR / "template.xlsx"
    if not tpl.exists() and DEFAULT_TEMPLATE.exists():
        shutil.copyfile(DEFAULT_TEMPLATE, tpl)
    if tpl.exists():
        state["template"] = inspect_template(tpl)


def _recompute_analyses(state: dict) -> None:
    suppliers = state.get("suppliers") or []
    docs = [d for d in state.get("documents") or [] if d.get("status") == "parsed"]
    by_supplier: dict[str, Any] = {}
    for s in suppliers:
        sdocs = [d for d in docs if d.get("supplier_id") == s["id"]]
        if sdocs:
            try:
                by_supplier[s["id"]] = aggregate(sdocs, suppliers)
            except Exception as exc:
                by_supplier[s["id"]] = {"items": [], "doc": {}, "totals": {}, "error": f"{type(exc).__name__}: {exc}"}
    try:
        all_analysis = aggregate(docs, suppliers) if docs else None
    except Exception as exc:
        all_analysis = {"items": [], "doc": {}, "totals": {}, "error": f"{type(exc).__name__}: {exc}"}
    state["analyses"] = {"by_supplier": by_supplier, "all": all_analysis, "updated_at": now_iso()}


def _invalidate_compliance(state: dict) -> None:
    state["compliance"] = {"run_at": None, "records": [], "confirmed": {}, "items": {}, "summary": {},
                           "attempts": [], "scope": None, "supplier_id": None, "items_signature": None}


def _items_signature(analysis: dict | None) -> str:
    if not analysis:
        return ""
    import hashlib
    raw = json.dumps([{k: it.get(k) for k in ("id", "name_en", "name_zh", "hs_code", "cartons", "pieces", "amount")}
                      for it in analysis.get("items") or []], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _get_analysis(state: dict, scope: str, supplier_id: str | None) -> dict | None:
    if scope == "supplier" and supplier_id:
        return (state.get("analyses") or {}).get("by_supplier", {}).get(supplier_id)
    return (state.get("analyses") or {}).get("all")


def _supplier_stats(state: dict, sid: str) -> dict:
    files = supplier_files(state, sid)
    analysis = (state.get("analyses") or {}).get("by_supplier", {}).get(sid) or {}
    totals = analysis.get("totals") or {}
    return {
        "files": len(files),
        "parsed_files": sum(1 for f in files if f.get("status") == "parsed"),
        "failed_files": sum(1 for f in files if f.get("status") == "failed"),
        "items": totals.get("items", 0),
        "cartons": totals.get("cartons", 0),
        "amount": totals.get("amount", 0),
        "documents": len(supplier_documents(state, sid)),
    }


def _compliance_gate(state: dict, analysis: dict | None, scope: str, supplier_id: str | None) -> dict:
    comp = state.get("compliance") or {}
    if not comp.get("records"):
        return {"ok": False, "reason": "尚未运行智能补充", "unconfirmed": [], "missing_hs": [],
                "supported": 0, "unsupported": 0, "confirmed": 0, "needs_run": True}
    if comp.get("scope") != scope or (scope == "supplier" and comp.get("supplier_id") != supplier_id):
        return {"ok": False, "reason": "智能补充结果与当前视图不一致，请重新运行", "unconfirmed": [],
                "missing_hs": [], "supported": comp.get("summary", {}).get("supported", 0),
                "unsupported": comp.get("summary", {}).get("unsupported", 0),
                "confirmed": sum(1 for r in comp.get("records") or [] if r.get("confirmed")), "needs_run": True}
    if _items_signature(analysis) != comp.get("items_signature"):
        return {"ok": False, "reason": "单证数据已变化，请重新运行智能补充", "unconfirmed": [],
                "missing_hs": [], "supported": comp.get("summary", {}).get("supported", 0),
                "unsupported": comp.get("summary", {}).get("unsupported", 0),
                "confirmed": sum(1 for r in comp.get("records") or [] if r.get("confirmed")), "needs_run": True}
    _, gate = compliance_service.reconcile(analysis.get("items") or [], comp)
    gate["needs_run"] = False
    gate["scope"] = scope
    return gate


def _compact_structure(st: dict | None) -> dict:
    """Only send the structure summary the UI actually renders.

    Full page text, OCR rows and per-table cell grids can be several hundred KB
    and are the main reason the public first paint felt slow.
    """
    st = st or {}
    pages = st.get("pages") or st.get("sheets") or []
    return {
        "format": st.get("format"),
        "coordinate_engine": st.get("coordinate_engine") or st.get("ocr"),
        "table_count": st.get("table_count") or len(st.get("sheets") or []),
        "pages": [{"page": p.get("page"), "width": p.get("width"), "height": p.get("height"),
                   "tables": len(p.get("tables") or [])} for p in pages],
        "sheets": [{"title": s.get("title"), "dim": s.get("dim"),
                    "merges": len(s.get("merges") or []), "header_row": s.get("header_row")}
                   for s in (st.get("sheets") or [])],
    }


def _compact_record(r: dict) -> dict:
    out = dict(r)
    out["evidence"] = str(out.get("evidence") or "")[:1400]
    out["reason"] = str(out.get("reason") or "")[:700]
    out["caveat"] = str(out.get("caveat") or "")[:400]
    extra = out.get("extra")
    if isinstance(extra, dict):
        extra = dict(extra)
        if "au_evidence" in extra:
            extra["au_evidence"] = str(extra["au_evidence"])[:900]
        out["extra"] = extra
    return out


def _record_stub(r: dict) -> dict:
    """Small record used by the first paint; details are lazy-loaded when the modal opens."""
    return {k: r.get(k) for k in ("id", "item_id", "field", "field_label", "value", "status", "confirmed")}


def _compact_analysis(analysis: dict | None) -> dict:
    a = analysis or {}
    fields = ("id", "no", "name_en", "name_zh", "hs_code", "material", "model", "cartons",
              "pieces_per_carton", "pieces", "unit_price", "amount", "gross_weight", "net_weight",
              "cbm", "length", "width", "height", "origin", "packing", "brand", "usage",
              "processing", "scenario", "preference", "origin_criterion", "confidence", "source")
    return {"items": [{k: it.get(k) for k in fields if k in it} for it in (a.get("items") or [])],
            "totals": a.get("totals") or {}, "doc": a.get("doc") or {}}


def _public_state(scope: str = "all", supplier_id: str | None = None, full_records: bool = False) -> dict:
    state = snapshot()
    # For a single-supplier workspace the aggregate view IS that supplier.
    # Resolve it server-side so the first request already carries the correct
    # compliance gate instead of showing a stale "尚未运行智能补充".
    effective_scope, effective_supplier = scope, supplier_id
    raw_suppliers = state.get("suppliers") or []
    if scope == "all" and not supplier_id and len(raw_suppliers) == 1:
        effective_scope, effective_supplier = "supplier", raw_suppliers[0].get("id")
    s = None
    active_supplier = effective_supplier or state.get("active_supplier_id")
    s = find_supplier(state, active_supplier)
    suppliers = []
    for sup in raw_suppliers:
        item = dict(sup)
        item.update(_supplier_stats(state, sup["id"]))
        item["active"] = bool(s and sup["id"] == s["id"])
        suppliers.append(item)
    analysis = _get_analysis(state, effective_scope, effective_supplier) or _get_analysis(state, "all", None)
    if effective_scope == "supplier" and effective_supplier:
        analysis = _get_analysis(state, "supplier", effective_supplier) or {"items": [], "doc": {}, "totals": {}, "documents": [], "conflicts": []}
    comp = state.get("compliance") or {}
    gate = _compliance_gate(state, analysis, effective_scope, effective_supplier)
    # expose the effective (confirmed-supplement-applied) item view for review/export UI
    analysis_public = analysis
    if analysis and comp.get("records") and comp.get("scope") == effective_scope and comp.get("items_signature") == _items_signature(analysis):
        try:
            effective, _ = compliance_service.reconcile(analysis.get("items") or [], comp)
            analysis_public = dict(analysis)
            analysis_public["items"] = effective
        except Exception:
            analysis_public = analysis
    item_ids = {it.get("id") for it in (analysis_public or {}).get("items") or []}
    records = [r for r in comp.get("records") or [] if r.get("item_id") in item_ids] if comp.get("scope") == effective_scope else []
    if analysis_public:
        doc_public = dict(analysis_public.get("doc") or {})
        if not doc_public.get("coverage"):
            types = {str(d.get("type") or "unknown") for d in (analysis_public.get("documents") or [])}
            doc_public["coverage"] = {
                "packing_list": bool(types & {"packing_list", "combined"}),
                "invoice": bool(types & {"invoice", "combined"}),
                "sales_confirmation": "contract" in types,
                "customs_declaration": bool(analysis_public.get("items") or []),
                "declaration_elements": bool(analysis_public.get("items") or []),
            }
        if effective_scope == "all":
            doc_public["coverage"] = dict(doc_public["coverage"])
            doc_public["coverage"]["customs_declaration"] = False
            doc_public["coverage"]["declaration_elements"] = False
        analysis_public = dict(analysis_public)
        analysis_public["doc"] = doc_public
    public_comp = {
        "run_at": comp.get("run_at"), "summary": comp.get("summary") or {},
        "records": (([_compact_record(r) for r in records]) if full_records else [_record_stub(r) for r in records]),
        "attempts": (comp.get("attempts") or [])[-12:],
        "disclaimer": comp.get("disclaimer") or "", "scope": comp.get("scope"),
        "gate": gate,
    }
    tpl = state.get("template") or {}
    tpl_public = {k: tpl.get(k) for k in ("filename", "hash", "size", "sheet_names", "sheets", "uploaded_at", "path")}
    settings = load_settings()
    llm = settings.get("llm") or {}
    llm_public = {"enabled": bool(llm.get("enabled")), "model": llm.get("model"),
                  "base_url": llm.get("base_url"), "key_configured": bool(llm.get("api_key"))}
    return {
        "version": state.get("version", 1),
        "scope": effective_scope,
        "supplier_id": effective_supplier,
        "active_supplier_id": s["id"] if s else None,
        "suppliers": suppliers,
        "files": state.get("files") or [],
        "documents": [{**{k: d.get(k) for k in ("id", "file_id", "supplier_id", "filename", "type", "format", "status",
                                                "fields", "items", "warnings", "error")},
                       "structure": _compact_structure(d.get("structure") or {})}
                      for d in state.get("documents") or []],
        "analysis": _compact_analysis(analysis_public),
        "compliance": public_comp,
        "template": tpl_public,
        "exports": [{**{k: e.get(k) for k in ("id", "filename", "size", "created_at", "download_url", "duration_ms", "engine")},
                     "validation": {k: (e.get("validation") or {}).get(k) for k in ("ok", "passed", "failed", "warnings")}}
                    for e in (state.get("exports") or [])[:8]],
        "activity": (state.get("activity") or [])[:40],
        "llm": llm_public,
        "engine": {
            "parser": "pdfplumber + openpyxl + RapidOCR",
            "transform": "standard intermediate model + style-safe row rebuild",
            "codegen": "generated Python script executed in a subprocess",
            "llm": "OpenAI-compatible adapter (optional)",
        },
        "gate": gate,
        "server_time": now_iso(),
    }


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    path = STATIC_DIR / "index.html"
    if not path.exists():
        return HTMLResponse("<h1>UI not built yet</h1>", status_code=500)
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict:
    state = snapshot()
    return {"ok": True, "version": app.version, "uptime_sec": int(time.time() - START_TS),
            "template": (state.get("template") or {}).get("filename"), "suppliers": len(state.get("suppliers") or []),
            "engine": "structural-codegen", "server_time": now_iso()}


# ---------------------------------------------------------------------------
# state / template / suppliers
# ---------------------------------------------------------------------------
@app.get("/api/state")
def state_endpoint(scope: str = Query("all"), supplier_id: Optional[str] = Query(None)) -> dict:
    return _public_state(scope, supplier_id)


@app.get("/api/compliance/records")
def compliance_records_endpoint(scope: str = Query("all"), supplier_id: Optional[str] = Query(None)) -> dict:
    """Lazy full evidence cards; keeps the initial /api/state payload small."""
    data = _public_state(scope, supplier_id, full_records=True)
    return {"records": data["compliance"]["records"], "summary": data["compliance"]["summary"],
            "gate": data["gate"], "scope": data["scope"], "supplier_id": data["supplier_id"]}


@app.get("/api/template/inspect")
def template_inspect() -> dict:
    state = snapshot()
    tpl = state.get("template") or {}
    path = Path(tpl.get("path") or TEMPLATE_DIR / "template.xlsx")
    if not path.exists():
        raise HTTPException(404, "模板不存在")
    return {"template": tpl, "mapping": template_engine.inspect_template(path)}


@app.get("/api/template/download")
def template_download() -> FileResponse:
    state = snapshot()
    tpl = state.get("template") or {}
    path = Path(tpl.get("path") or TEMPLATE_DIR / "template.xlsx")
    if not path.exists():
        raise HTTPException(404, "模板不存在")
    return FileResponse(path, filename=tpl.get("filename") or path.name,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/api/template")
async def template_upload(file: UploadFile = File(...)) -> dict:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".xlsx", ".xlsm"}:
        raise HTTPException(400, "模板必须是 .xlsx/.xlsm")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "模板文件过大")
    target = TEMPLATE_DIR / "template.xlsx"
    target.write_bytes(raw)
    try:
        info = inspect_template(target)
    except Exception as exc:
        raise HTTPException(400, f"模板无法读取：{exc}")
    canon = {s["title"].strip() for s in info["sheets"]}
    expected = {"装箱清单", "发票", "申报要素", "销货确认书", "报关单"}
    missing = expected - canon
    if missing:
        raise HTTPException(400, f"模板缺少必要 Sheet：{', '.join(sorted(missing))}")
    def _apply(state):
        state["template"] = info
        log_activity(state, "template", f"上传目标模板 {file.filename}，5 个 Sheet 校验通过")
    mutate(_apply)
    return {"ok": True, "template": info, "mapping": template_engine.inspect_template(target)}


@app.post("/api/suppliers")
def create_supplier(payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "供应商名称不能为空")
    new_sup = {"id": new_id("sup_"), "name": name, "created_at": now_iso(), "color": "gold"}
    def _apply(state):
        state.setdefault("suppliers", []).append(new_sup)
        state["active_supplier_id"] = new_sup["id"]
        log_activity(state, "supplier", f"新建供应商：{name}")
    mutate(_apply)
    return {"ok": True, "supplier": new_sup}


@app.patch("/api/suppliers/{supplier_id}")
def rename_supplier(supplier_id: str, payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    def _apply(state):
        s = find_supplier(state, supplier_id)
        if not s:
            raise HTTPException(404, "供应商不存在")
        old = s["name"]
        s["name"] = name
        state["active_supplier_id"] = supplier_id
        log_activity(state, "supplier", f"重命名供应商：{old} → {name}")
    mutate(_apply)
    return {"ok": True}


@app.delete("/api/suppliers/{supplier_id}")
def delete_supplier(supplier_id: str) -> dict:
    def _apply(state):
        state["suppliers"] = [s for s in state.get("suppliers") or [] if s.get("id") != supplier_id]
        state["files"] = [f for f in state.get("files") or [] if f.get("supplier_id") != supplier_id]
        state["documents"] = [d for d in state.get("documents") or [] if d.get("supplier_id") != supplier_id]
        if state.get("active_supplier_id") == supplier_id:
            state["active_supplier_id"] = (state.get("suppliers") or [{}])[0].get("id")
        _invalidate_compliance(state)
        _recompute_analyses(state)
        log_activity(state, "supplier", "删除供应商及其单证")
    mutate(_apply)
    return {"ok": True}


@app.post("/api/suppliers/{supplier_id}/activate")
def activate_supplier(supplier_id: str) -> dict:
    def _apply(state):
        if not find_supplier(state, supplier_id):
            raise HTTPException(404, "供应商不存在")
        state["active_supplier_id"] = supplier_id
    mutate(_apply)
    return {"ok": True}


@app.post("/api/settings")
def update_settings(payload: dict) -> dict:
    current = load_settings()
    llm = payload.get("llm") or {}
    if "base_url" in llm:
        current["llm"]["base_url"] = str(llm["base_url"]).strip()
    if "model" in llm:
        current["llm"]["model"] = str(llm["model"]).strip()
    if "api_key" in llm and llm["api_key"]:
        current["llm"]["api_key"] = str(llm["api_key"]).strip()
    current["llm"]["enabled"] = bool(current["llm"].get("api_key"))
    save_settings(current)
    return {"ok": True, "llm": {"enabled": current["llm"]["enabled"], "model": current["llm"]["model"],
                                "base_url": current["llm"]["base_url"], "key_configured": bool(current["llm"].get("api_key"))}}


@app.post("/api/self-check")
def self_check() -> dict:
    checks = []
    state = snapshot()
    checks.append({"name": "模板存在", "ok": bool(state.get("template")), "detail": (state.get("template") or {}).get("filename", "")})
    tpl_path = Path((state.get("template") or {}).get("path") or TEMPLATE_DIR / "template.xlsx")
    try:
        mapping = template_engine.inspect_template(tpl_path)
        checks.append({"name": "5-Sheet 映射", "ok": len([s for s in mapping["sheets"] if s["role"] != "unmapped"]) == 5,
                       "detail": ", ".join(f"{s['name']}={s['role']}" for s in mapping["sheets"])})
    except Exception as exc:
        checks.append({"name": "5-Sheet 映射", "ok": False, "detail": str(exc)})
    for mod in ("pdfplumber", "openpyxl", "fitz", "rapidocr_onnxruntime"):
        try:
            __import__(mod)
            checks.append({"name": f"依赖 {mod}", "ok": True, "detail": "已加载"})
        except Exception as exc:
            checks.append({"name": f"依赖 {mod}", "ok": False, "detail": f"{type(exc).__name__}: {exc}"})
    try:
        from .services.compliance import query_tariff
        res = query_tariff("9401790000", timeout=8)
        checks.append({"name": "海关官网实时取证", "ok": bool(res.get("ok")), "detail": f"HTTP {res.get('http_status')} · {len(res.get('rows') or [])} 行 · {res.get('elapsed_ms')} ms"})
    except Exception as exc:
        checks.append({"name": "海关官网实时取证", "ok": False, "detail": str(exc)})
    try:
        from .services.compliance import _fetch_abf_evidence
        abf = _fetch_abf_evidence([])
        checks.append({"name": "ABF ChAFTA 取证", "ok": bool(abf.get("eligibility_quote") or abf.get("psr_quote")), "detail": (abf.get("eligibility_url") or abf.get("psr_url") or "无")})
    except Exception as exc:
        checks.append({"name": "ABF ChAFTA 取证", "ok": False, "detail": str(exc)})
    checks.append({"name": "WPS 公式重算", "ok": True, "detail": "导出时通过 WPS COM 重算并写回缓存值（如本机无 WPS 会降级为公式校验）"})
    llm = load_settings().get("llm") or {}
    checks.append({"name": "LLM 代码生成适配器", "ok": bool(llm.get("api_key")), "detail": "已配置 API Key" if llm.get("api_key") else "未配置，使用确定性结构代码生成器（导出仍可执行）"})
    return {"ok": all(c["ok"] for c in checks if c["name"] not in {"LLM 代码生成适配器"}), "checks": checks, "server_time": now_iso()}


# ---------------------------------------------------------------------------
# upload + parse
# ---------------------------------------------------------------------------
@app.post("/api/upload")
async def upload(supplier_id: str = Form(...), files: list[UploadFile] = File(...)) -> dict:
    state = snapshot()
    if not find_supplier(state, supplier_id):
        raise HTTPException(404, "供应商不存在")
    saved = []
    for f in files:
        filename = safe_filename(f.filename or "upload")
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            saved.append({"filename": filename, "error": f"不支持的类型 {ext}", "ok": False})
            continue
        raw = await f.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            saved.append({"filename": filename, "error": "文件超过 80MB 限制", "ok": False})
            continue
        file_id = new_id("file_")
        stored = UPLOAD_DIR / f"{file_id}_{filename}"
        stored.write_bytes(raw)
        digest = file_sha256(stored)
        saved.append({"ok": True, "file_id": file_id, "filename": filename, "stored_name": stored.name,
                      "path": str(stored), "hash": digest, "size": len(raw), "ext": ext})
    # A new upload replaces the supplier's previous files/analysis. Never append
    # to an existing supplier or carry previous rows into this export.
    if any(s.get("ok") for s in saved):
        old_paths: list[str] = []
        def _clear(state):
            for f in state.get("files") or []:
                if f.get("supplier_id") == supplier_id and f.get("path"):
                    old_paths.append(str(f.get("path")))
            state["files"] = [f for f in state.get("files") or [] if f.get("supplier_id") != supplier_id]
            state["documents"] = [d for d in state.get("documents") or [] if d.get("supplier_id") != supplier_id]
            by = (state.get("analyses") or {}).get("by_supplier") or {}
            by.pop(supplier_id, None)
            _invalidate_compliance(state)
        mutate(_clear)
        for p in old_paths:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass
        backup_dir = DATA_DIR / "supplier_backups" / supplier_id
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
    job = job_service.create("upload", {"supplier_id": supplier_id, "files": [s.get("filename") for s in saved]})

    def _work(job_id: str):
        total = max(1, len([s for s in saved if s.get("ok")]))
        done = 0
        for i, item in enumerate(saved, start=1):
            if not item.get("ok"):
                job_service.log(job_id, f"{item.get('filename')}: {item.get('error')}", progress=5 + int(80 * i / max(1, len(saved))), phase="解析中")
                continue
            job_service.log(job_id, f"正在解析 {item['filename']}（{item['size']} bytes）", progress=5 + int(70 * (i - 1) / total), phase="结构解析")
            dup = None
            st = snapshot()
            for ef in st.get("files") or []:
                if ef.get("hash") == item["hash"]:
                    dup = ef
                    break
            if dup:
                try:
                    Path(item["path"]).unlink(missing_ok=True)
                except Exception:
                    pass
                item["path"] = ""
                def _dup(state):
                    state.setdefault("files", []).append({
                        "id": item["file_id"], "supplier_id": supplier_id, "filename": item["filename"],
                        "stored_name": "", "path": "", "hash": item["hash"],
                        "size": item["size"], "ext": item["ext"], "status": "duplicate", "uploaded_at": now_iso(),
                        "error": f"与已有文件重复（{dup.get('filename')}）", "document_id": None,
                    })
                    log_activity(state, "upload", f"重复文件已跳过：{item['filename']}")
                mutate(_dup)
                done += 1
                job_service.log(job_id, f"{item['filename']} 重复，已按 Hash 去重", phase="去重")
                continue
            result = parser.parse_file(Path(item["path"]), item["filename"])
            # Keep only structured parse results; never retain the uploaded binary.
            try:
                Path(item["path"]).unlink(missing_ok=True)
            except Exception:
                pass
            item["path"] = ""
            doc_id = new_id("doc_")
            file_record = {
                "id": item["file_id"], "supplier_id": supplier_id, "filename": item["filename"],
                "stored_name": "", "path": "", "hash": item["hash"],
                "size": item["size"], "ext": item["ext"], "uploaded_at": now_iso(),
                "status": "parsed" if result.get("ok") else "failed",
                "document_id": doc_id if result.get("ok") else None,
                "error": None if result.get("ok") else result.get("error"),
                "type": result.get("type"), "items_count": len(result.get("items") or []),
            }
            doc_record = {
                "id": doc_id, "file_id": item["file_id"], "supplier_id": supplier_id, "filename": item["filename"],
                "type": result.get("type"), "format": result.get("format"), "status": "parsed" if result.get("ok") else "failed",
                "fields": result.get("fields") or {}, "items": result.get("items") or [],
                "totals": result.get("totals") or {}, "structure": result.get("structure") or {},
                "warnings": result.get("warnings") or [], "error": result.get("error"),
                "text": (result.get("text") or "")[:12000], "created_at": now_iso(),
            }
            def _save(state):
                state.setdefault("files", []).append(file_record)
                if result.get("ok"):
                    state.setdefault("documents", []).append(doc_record)
                    log_activity(state, "upload", f"{item['filename']} 解析成功，{len(doc_record['items'])} 行货物")
                else:
                    log_activity(state, "upload", f"{item['filename']} 解析失败：{result.get('error')}")
            mutate(_save)
            done += 1
            job_service.log(job_id, f"{item['filename']} 解析{'成功' if result.get('ok') else '失败'}，{len(result.get('items') or [])} 行",
                            progress=5 + int(75 * i / total), phase="解析完成")
        job_service.log(job_id, "正在合并同一供应商的装箱单/发票并去重", progress=86, phase="标准化合并")
        def _final(state):
            _recompute_analyses(state)
            _invalidate_compliance(state)
            analysis = (state.get("analyses") or {}).get("by_supplier", {}).get(supplier_id) or {}
            log_activity(state, "merge", f"合并完成：{analysis.get('totals', {}).get('items', 0)} 行货物，去重 {analysis.get('totals', {}).get('duplicates_removed', 0)} 行")
            return analysis
        analysis = mutate(_final)
        job_service.log(job_id, f"完成：{analysis.get('totals', {}).get('items', 0)} 行货物，去重 {analysis.get('totals', {}).get('duplicates_removed', 0)} 行", progress=100, phase="完成")
        return {"supplier_id": supplier_id, "items": analysis.get("totals", {}).get("items", 0),
                "duplicates_removed": analysis.get("totals", {}).get("duplicates_removed", 0),
                "files_processed": done, "analysis": analysis}

    job_service.run(job["id"], _work, "upload")
    return {"ok": True, "job_id": job["id"], "accepted": saved}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = job_service.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return job_service.public(job) or {}


@app.post("/api/identify")
def identify(payload: dict) -> dict:
    scope = payload.get("scope") or "supplier"
    supplier_id = payload.get("supplier_id")
    st = snapshot()
    targets = [f for f in st.get("files") or [] if scope == "all" or f.get("supplier_id") == supplier_id]
    parsed = []
    for f in targets:
        path = Path(f.get("path") or "")
        if not path.exists():
            continue
        result = parser.parse_file(path, f.get("filename") or path.name)
        parsed.append((f, result))
    def _apply(state):
        by_file = {d.get("file_id") for d in state.get("documents") or [] if d.get("file_id")}
        state["documents"] = [d for d in state.get("documents") or [] if d.get("file_id") not in {f.get("id") for f, _ in parsed}]
        for f, result in parsed:
            f_id = f.get("id")
            doc_id = new_id("doc_")
            for rec in state.get("files") or []:
                if rec.get("id") == f_id:
                    rec["status"] = "parsed" if result.get("ok") else "failed"
                    rec["error"] = None if result.get("ok") else result.get("error")
                    rec["type"] = result.get("type")
                    rec["items_count"] = len(result.get("items") or [])
                    rec["document_id"] = doc_id if result.get("ok") else None
            if result.get("ok"):
                state.setdefault("documents", []).append({
                    "id": doc_id, "file_id": f_id, "supplier_id": f.get("supplier_id"),
                    "filename": f.get("filename"), "type": result.get("type"), "format": result.get("format"),
                    "status": "parsed", "fields": result.get("fields") or {}, "items": result.get("items") or [],
                    "totals": result.get("totals") or {}, "structure": result.get("structure") or {},
                    "warnings": result.get("warnings") or [], "error": None,
                    "text": (result.get("text") or "")[:12000], "created_at": now_iso(),
                })
        _recompute_analyses(state)
        _invalidate_compliance(state)
        log_activity(state, "identify", f"重新解析 {len(parsed)} 份文件并重建标准数据模型")
    mutate(_apply)
    state = snapshot()
    return {"ok": True, "analysis": _get_analysis(state, scope, supplier_id), "reparsed": len(parsed)}


# ---------------------------------------------------------------------------
# compliance
# ---------------------------------------------------------------------------
@app.post("/api/compliance/run")
def run_compliance(payload: dict) -> dict:
    scope = payload.get("scope") or "all"
    supplier_id = payload.get("supplier_id")
    state = snapshot()
    analysis = _get_analysis(state, scope, supplier_id)
    if not analysis or not analysis.get("items"):
        raise HTTPException(400, "当前视图没有可补充的货物行")
    job = job_service.create("compliance", {"scope": scope, "supplier_id": supplier_id})

    def _work(job_id: str):
        job_service.log(job_id, "读取目标 Sheet 与标准货物行", progress=8, phase="准备")
        items = analysis.get("items") or []
        job_service.log(job_id, f"开始查询 online.customs.gov.cn（{len(items)} 个商品）与 ABF ChAFTA 规则", progress=25, phase="官方取证")
        settings = load_settings()
        result = compliance_service.run_compliance(items, settings)
        job_service.log(job_id, f"取证完成：{result['summary']['supported']} 条 supported / {result['summary']['unsupported']} 条 unsupported",
                        progress=82, phase="证据整理")
        result["scope"] = scope
        result["supplier_id"] = supplier_id
        result["items_signature"] = _items_signature(analysis)
        result["confirmed"] = {}
        def _save(state):
            state["compliance"] = result
            log_activity(state, "compliance", f"智能补充完成：{result['summary']['supported']} 条支持，{result['summary']['unsupported']} 条置灰")
        mutate(_save)
        job_service.log(job_id, "溯源卡片已生成，等待人工确认", progress=100, phase="完成")
        return {"summary": result["summary"], "scope": scope, "supplier_id": supplier_id}

    job_service.run(job["id"], _work, "compliance")
    return {"ok": True, "job_id": job["id"]}


@app.post("/api/compliance/confirm")
def confirm_compliance(payload: dict) -> dict:
    ids = payload.get("ids") or []
    value = bool(payload.get("confirmed", True))
    scope = payload.get("scope") or "all"
    supplier_id = payload.get("supplier_id")
    def _apply(state):
        comp = state.get("compliance") or {}
        compliance_service.confirm(comp, ids, value)
        state["compliance"] = comp
        log_activity(state, "confirm", f"{'确认' if value else '取消确认'} {len(ids)} 条溯源记录")
    mutate(_apply)
    st = snapshot()
    analysis = _get_analysis(st, scope, supplier_id)
    return {"ok": True, "gate": _compliance_gate(st, analysis, scope, supplier_id)}


@app.post("/api/compliance/manual")
def manual_evidence(payload: dict) -> dict:
    """Allow the user to attach an authoritative manual citation for a missing HS code."""
    item_id = payload.get("item_id")
    code = str(payload.get("hs_code") or "").strip()
    url = str(payload.get("source_url") or "").strip()
    evidence = str(payload.get("matched_evidence") or "").strip()
    if not (item_id and code and url and evidence):
        raise HTTPException(400, "item_id / hs_code / source_url / matched_evidence 均不能为空")
    res = compliance_service.query_tariff(code)
    if not res.get("ok"):
        raise HTTPException(400, "该 HS 编码未在海关官网税号库中查到，不能作为有据补充")
    row = next((r for r in res["rows"] if str(r.get("codeTs")) == re.sub(r"\D", "", code)), None)
    if not row:
        raise HTTPException(400, "海关官网未精确匹配该 10 位编码")
    rec = {
        "id": new_id("cmp_manual_"), "item_id": item_id, "item_name": payload.get("item_name", ""),
        "field": "hs_code", "field_label": "HS 编码", "value": code,
        "original_value": payload.get("original_value", ""), "status": "supported",
        "source_url": url, "retrieved_at": now_iso(), "matched_evidence": evidence,
        "reason": "用户提供的官方溯源证据；编码同时经 online.customs.gov.cn 税号库校验。",
        "confidence": "manual", "caveat": compliance_service.CUSTOMS_DISCLAIMER, "confirmed": True,
        "extra": {"gName": row.get("gName"), "impOrdinaryRate": row.get("impOrdinaryRate")},
    }
    def _apply(state):
        comp = state.get("compliance") or {}
        comp.setdefault("records", []).append(rec)
        state["compliance"] = comp
        log_activity(state, "manual", f"人工补充 HS {code} 并通过官网校验")
    mutate(_apply)
    return {"ok": True, "record": rec}


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
@app.post("/api/export")
def export_endpoint(payload: dict) -> dict:
    scope = payload.get("scope") or "all"
    supplier_id = payload.get("supplier_id")
    acknowledge = bool(payload.get("acknowledge_unsupported", False))
    state = snapshot()
    analysis = _get_analysis(state, scope, supplier_id)
    if not analysis or not analysis.get("items"):
        raise HTTPException(400, "当前视图没有可导出的货物行")
    tpl = state.get("template") or {}
    tpl_path = Path(tpl.get("path") or TEMPLATE_DIR / "template.xlsx")
    if not tpl_path.exists():
        raise HTTPException(400, "目标模板不存在")
    gate = _compliance_gate(state, analysis, scope, supplier_id)
    if gate.get("needs_run"):
        raise HTTPException(409, gate.get("reason") or "请先运行智能补充")
    job = job_service.create("export", {"scope": scope, "supplier_id": supplier_id})

    def _work(job_id: str):
        job_service.log(job_id, "校验合规确认门禁", progress=8, phase="门禁")
        try:
            rec = exporter.export(analysis, state.get("compliance") or {}, tpl_path, load_settings(),
                                  acknowledge_unsupported=acknowledge,
                                  output_name=str(payload.get("output_name") or ""))
        except exporter.ExportBlocked as exc:
            job_service.update(job_id, status="failed", phase="合规阻断", message=str(exc),
                               error=str(exc), gate=exc.gate, progress=100,
                               result={"blocked": True, "gate": exc.gate, "error": str(exc)})
            return {"blocked": True, "gate": exc.gate, "error": str(exc)}
        def _save(state):
            state.setdefault("exports", []).insert(0, rec)
            state["exports"] = state["exports"][:50]
            log_activity(state, "export", f"导出成功：{rec['filename']}（{rec['size']} bytes，校验 {rec['validation']['passed']} 项通过）")
        mutate(_save)
        job_service.log(job_id, f"导出完成：{rec['filename']}", progress=100, phase="完成")
        return {"export": rec}
    job_service.run(job["id"], _work, "export")
    return {"ok": True, "job_id": job["id"]}


@app.get("/api/download/{export_id}")
def download(export_id: str) -> FileResponse:
    state = snapshot()
    rec = next((e for e in state.get("exports") or [] if e.get("id") == export_id), None)
    if not rec:
        raise HTTPException(404, "导出记录不存在")
    path = Path(rec["path"])
    if not path.exists():
        raise HTTPException(404, "文件已被移除")
    return FileResponse(path, filename=rec["filename"],
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/script/{export_id}")
def download_script(export_id: str) -> FileResponse:
    state = snapshot()
    rec = next((e for e in state.get("exports") or [] if e.get("id") == export_id), None)
    if not rec:
        raise HTTPException(404, "导出记录不存在")
    path = Path(rec.get("script_path") or "")
    if not path.exists():
        raise HTTPException(404, "脚本不存在")
    return FileResponse(path, filename=path.name, media_type="text/x-python")


@app.get("/api/exports/{export_id}")
def export_detail(export_id: str) -> dict:
    state = snapshot()
    rec = next((e for e in state.get("exports") or [] if e.get("id") == export_id), None)
    if not rec:
        raise HTTPException(404, "导出记录不存在")
    return rec


@app.get("/api/demo/load")
def demo_load() -> dict:
    """Load the bundled heterogeneous fixtures through the real parse pipeline."""
    testdata = Path(__file__).resolve().parents[1] / "testdata"
    groups = {
        "宁波豪迈家居（演示）": ["supplier_a_ningbo_homeline/packing_list.pdf", "supplier_a_ningbo_homeline/commercial_invoice.pdf"],
        "佛山日出家具（演示）": ["supplier_b_foshan_sunrise/packing_list.xlsx", "supplier_b_foshan_sunrise/commercial_invoice.xlsx"],
        "广州常青藤五金（演示）": ["supplier_c_guangzhou_evergreen/packing_list_scan.png"],
    }
    state = snapshot()
    if any("演示" in s.get("name", "") for s in state.get("suppliers") or []):
        return {"ok": True, "message": "演示数据已存在", "suppliers": [s["id"] for s in state["suppliers"] if "演示" in s["name"]]}
    created = []
    for name, rels in groups.items():
        sup = {"id": new_id("sup_"), "name": name, "created_at": now_iso(), "color": "gold"}
        created.append(sup)
        docs = []
        for rel in rels:
            p = testdata / rel
            if not p.exists():
                continue
            res = parser.parse_file(p, p.name)
            if not res.get("ok"):
                continue
            docs.append({
                "id": new_id("doc_"), "file_id": None, "supplier_id": sup["id"], "filename": p.name,
                "type": res.get("type"), "format": res.get("format"), "status": "parsed",
                "fields": res.get("fields") or {}, "items": res.get("items") or [],
                "totals": res.get("totals") or {}, "structure": res.get("structure") or {},
                "warnings": res.get("warnings") or [], "text": (res.get("text") or "")[:12000], "created_at": now_iso(),
            })
        def _add(state, sup=sup, docs=docs):
            state.setdefault("suppliers", []).append(sup)
            state.setdefault("documents", []).extend(docs)
            state["active_supplier_id"] = sup["id"]
            _recompute_analyses(state)
            _invalidate_compliance(state)
            log_activity(state, "demo", f"载入演示供应商 {sup['name']}（{len(docs)} 份单证）")
        mutate(_add)
    return {"ok": True, "suppliers": [s["id"] for s in created], "message": "演示单证已通过真实解析管线载入"}


@app.exception_handler(404)
async def not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": str(exc.detail)}, status_code=404)
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8") if (STATIC_DIR / "index.html").exists() else "Not found", status_code=404)


def _bootstrap(state: dict) -> None:
    _ensure_template(state)
    if not state.get("analyses"):
        _recompute_analyses(state)


with __import__("contextlib").suppress(Exception):
    # The workbench keeps structured rows only. Never retain uploaded binaries,
    # supplier backup folders or old backup JSON files.
    shutil.rmtree(DATA_DIR / "supplier_backups", ignore_errors=True)
    for p in DATA_DIR.glob("backup_*.json"):
        p.unlink(missing_ok=True)
    for p in UPLOAD_DIR.glob("*"):
        if p.is_file():
            p.unlink(missing_ok=True)
    mutate(_bootstrap)
