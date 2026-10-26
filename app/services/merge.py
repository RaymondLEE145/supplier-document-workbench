# -*- coding: utf-8 -*-
"""Merge parsed supplier documents into one standard intermediate model.

Rules:
* a file's own packing list + invoice are already paired by the parser;
* exact duplicate goods lines across suppliers are removed (source list kept);
* same product + same HS but different quantities are aggregated;
* every merged field records its source documents for traceability.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

CJK = re.compile(r"[\u3400-\u9fff]+")


def _norm(v: Any) -> str:
    s = str(v or "").strip().lower()
    s = re.sub(r"[\s\u3000]+", " ", s)
    return s


def _name_key(it: dict) -> str:
    en = CJK.sub(" ", str(it.get("name_en") or ""))
    en = re.sub(r"\s+", " ", en).strip().lower()
    return en or _norm(it.get("name_zh")) or _norm(it.get("model"))


def _sig(it: dict) -> tuple:
    return (
        _name_key(it), str(it.get("hs_code") or ""), int(it.get("cartons") or 0),
        int(it.get("pieces_per_carton") or 0), int(it.get("pieces") or 0),
        round(float(it.get("amount") or 0), 2), round(float(it.get("gross_weight") or 0), 2),
    )


def _merge_sources(a: dict, b: dict) -> list[dict]:
    out = list(a.get("sources") or [])
    for s in b.get("sources") or []:
        sig = (s.get("file"), s.get("type"), s.get("page"), s.get("sheet"))
        if not any((x.get("file"), x.get("type"), x.get("page"), x.get("sheet")) == sig for x in out):
            out.append(s)
    return out


def _merge_values(keep: dict, other: dict, aggregate: bool) -> dict:
    out = dict(keep)
    num_fields = {"cartons", "pieces", "gross_weight", "net_weight", "cbm", "amount"}
    for k, v in other.items():
        if k in {"id", "sources", "raw"}:
            continue
        if k in num_fields and aggregate:
            out[k] = round(float(out.get(k) or 0) + float(v or 0), 4 if k == "cbm" else 2)
            continue
        if out.get(k) in (None, "", 0, 0.0) and v not in (None, "", 0, 0.0):
            out[k] = v
    if aggregate:
        pieces = int(out.get("pieces") or 0)
        amount = float(out.get("amount") or 0)
        if pieces and amount:
            out["unit_price"] = round(amount / pieces, 4)
    out["sources"] = _merge_sources(keep, other)
    if len(out["sources"]) > 1:
        out["merged_from"] = len(out["sources"])
    return out


def aggregate(documents: list[dict], suppliers: list[dict]) -> dict:
    docs = [d for d in documents if d.get("status") == "parsed" and d.get("items")]
    supplier_by_id = {s["id"]: s for s in suppliers}
    supplier_names = []
    for d in docs:
        s = supplier_by_id.get(d.get("supplier_id"))
        name = (d.get("fields") or {}).get("supplier_name") or (s or {}).get("name") or "供应商"
        if name and name not in supplier_names:
            supplier_names.append(name)

    all_items: list[dict] = []
    for d in docs:
        s = supplier_by_id.get(d.get("supplier_id")) or {}
        for it in d.get("items") or []:
            item = dict(it)
            item["supplier_id"] = d.get("supplier_id")
            item["supplier_name"] = (d.get("fields") or {}).get("supplier_name") or s.get("name")
            src = {"file": d.get("filename"), "type": d.get("type"), "supplier_id": d.get("supplier_id"),
                   "supplier_name": item["supplier_name"], "page": it.get("source_page")}
            item["sources"] = list(it.get("sources") or []) + [src]
            all_items.append(item)

    # 0) fuse a packing list with its matching invoice for the SAME supplier only when
    #    they are different document types and describe the same quantities. Multiple
    #    rows inside one product-master / packing list are distinct lines and stay apart.
    groups: dict[tuple, list[dict]] = {}
    for it in all_items:
        key = (it.get("supplier_id"), _name_key(it), str(it.get("hs_code") or ""))
        groups.setdefault(key, []).append(it)
    fused: list[dict] = []
    qty_fields = {"cartons", "pieces", "pieces_per_carton", "gross_weight", "net_weight", "cbm", "length", "width", "height"}
    price_fields = {"unit_price", "amount"}
    for key, group in groups.items():
        if len(group) == 1:
            fused.append(group[0])
            continue
        packing_items = [x for x in group if (x.get("source_type") == "packing_list") or (x.get("gross_weight") or x.get("cbm")) and not (x.get("amount") or 0)]
        invoice_items = [x for x in group if x not in packing_items and ((x.get("source_type") == "invoice") or (x.get("amount") or 0))]
        other_items = [x for x in group if x not in packing_items and x not in invoice_items]
        used_invoice: set[int] = set()
        for pack in packing_items:
            match = None
            for ii, inv in enumerate(invoice_items):
                if ii in used_invoice:
                    continue
                same_qty = (
                    (not pack.get("cartons") or not inv.get("cartons") or int(pack.get("cartons") or 0) == int(inv.get("cartons") or 0))
                    and (not pack.get("pieces") or not inv.get("pieces") or int(pack.get("pieces") or 0) == int(inv.get("pieces") or 0))
                )
                if same_qty:
                    match = ii
                    break
            if match is not None:
                used_invoice.add(match)
                base = dict(pack)
                other = invoice_items[match]
                for k, v in other.items():
                    if k in {"id", "sources", "raw"}:
                        continue
                    if k in qty_fields or k in price_fields:
                        if base.get(k) in (None, "", 0, 0.0) and v not in (None, "", 0, 0.0):
                            base[k] = v
                    elif base.get(k) in (None, "", 0, 0.0) and v not in (None, "", 0, 0.0):
                        base[k] = v
                base["sources"] = _merge_sources(base, other)
                if not base.get("model") and other.get("model"):
                    base["model"] = other["model"]
                fused.append(base)
            else:
                fused.append(pack)
        for ii, inv in enumerate(invoice_items):
            if ii not in used_invoice:
                fused.append(inv)
        fused.extend(other_items)
    all_items = fused

    # 1) exact duplicate removal across suppliers
    deduped: list[dict] = []
    seen: dict[tuple, int] = {}
    duplicates_removed = 0
    for it in all_items:
        sig = _sig(it)
        if sig in seen:
            idx = seen[sig]
            deduped[idx]["sources"] = _merge_sources(deduped[idx], it)
            deduped[idx]["duplicate_of"] = deduped[idx].get("duplicate_of") or []
            deduped[idx]["duplicate_of"].append(it.get("source_file") or it.get("supplier_name"))
            duplicates_removed += 1
            continue
        seen[sig] = len(deduped)
        deduped.append(it)

    # 2) same product + HS from different suppliers with different quantities => aggregate
    aggregated: list[dict] = []
    groups2: dict[tuple, int] = {}
    aggregated_rows = 0
    for it in deduped:
        key = (_name_key(it), str(it.get("hs_code") or ""))
        if key in groups2 and (it.get("hs_code") or key[0]):
            idx = groups2[key]
            existing = aggregated[idx]
            if existing.get("supplier_id") == it.get("supplier_id"):
                # already fused in phase 0; a second line from the same supplier is a distinct line
                if _sig(existing) == _sig(it):
                    existing["sources"] = _merge_sources(existing, it)
                    duplicates_removed += 1
                    continue
                aggregated.append(it)
                continue
            aggregated[idx] = _merge_values(existing, it, aggregate=True)
            aggregated_rows += 1
            continue
        groups2[key] = len(aggregated)
        aggregated.append(it)

    # 3) enrich, derive, renumber
    for idx, it in enumerate(aggregated, start=1):
        it["id"] = f"it_{idx:03d}"
        it["no"] = idx
        it["currency"] = it.get("currency") or ""
        it["origin"] = it.get("origin") or ""
        it["destination_country"] = it.get("destination_country") or ""
        it["origin_criterion"] = it.get("origin_criterion") or ""
        it["preference_eligible"] = it.get("preference_eligible") or ""
        it.setdefault("supplements", {})
        if not it.get("destination_port"):
            it["destination_port"] = ""
        if not it.get("source_province"):
            joined = (str(it.get("supplier_name") or "") + " " + str(it.get("source_file") or "")).lower()
            if "ningbo" in joined or "宁波" in joined:
                it["source_province"] = "浙江"
            elif "foshan" in joined or "佛山" in joined or "guangzhou" in joined or "广州" in joined:
                it["source_province"] = "广东"
            elif "shenzhen" in joined or "深圳" in joined:
                it["source_province"] = "广东"
        it["unit_price"] = round(float(it.get("unit_price") or 0), 4)
        it["amount"] = round(float(it.get("amount") or 0), 2)
        it["cartons"] = int(it.get("cartons") or 0)
        it["pieces"] = int(it.get("pieces") or 0)
        it["pieces_per_carton"] = int(it.get("pieces_per_carton") or 0)
        it["gross_weight"] = round(float(it.get("gross_weight") or 0), 3)
        it["net_weight"] = round(float(it.get("net_weight") or 0), 3)
        it["cbm"] = round(float(it.get("cbm") or 0), 4)

    totals = {
        "items": len(aggregated),
        "cartons": sum(i["cartons"] for i in aggregated),
        "pieces": sum(i["pieces"] for i in aggregated),
        "amount": round(sum(i["amount"] for i in aggregated), 2),
        "gross_weight": round(sum(i["gross_weight"] for i in aggregated), 3),
        "net_weight": round(sum(i["net_weight"] for i in aggregated), 3),
        "cbm": round(sum(i["cbm"] for i in aggregated), 4),
        "suppliers": len(supplier_names),
        "documents": len(docs),
        "duplicates_removed": duplicates_removed,
        "rows_aggregated": aggregated_rows,
    }

    # document level fields: first non-empty wins, conflicts recorded
    def first(key: str) -> str:
        for d in docs:
            v = (d.get("fields") or {}).get(key)
            if v not in (None, "", 0, 0.0):
                return str(v)
        return ""

    def distinct(key: str) -> list[str]:
        vals = []
        for d in docs:
            v = (d.get("fields") or {}).get(key)
            if v not in (None, "", 0, 0.0):
                s = str(v)
                if s not in vals:
                    vals.append(s)
        return vals

    conflicts = []
    for key, label in (("contract_no", "合同号"), ("invoice_no", "发票号"), ("consignee", "收货人"),
                       ("loading_port", "起运港"), ("destination", "目的地")):
        vals = distinct(key)
        if len(vals) > 1:
            conflicts.append({"field": key, "label": label, "values": vals, "note": f"检测到 {len(vals)} 个不同{label}，模板仅支持一个，已取第一个"})

    date = first("date")

    loading_port = first("loading_port")
    office_map = [("NINGBO", "宁波海关"), ("SHENZHEN", "深圳海关"), ("GUANGZHOU", "广州海关"), ("SHANGHAI", "上海海关"), ("TIANJIN", "天津海关")]
    customs_office = next((v for k, v in office_map if k in loading_port.upper()), "")
    supplier_name = supplier_names[0] if supplier_names else ""
    multi = len({d.get("supplier_id") for d in docs}) > 1
    doc = {
        "scope": "all" if len({d.get("supplier_id") for d in docs}) > 1 else "supplier",
        "supplier_id": docs[0].get("supplier_id") if docs else None,
        "supplier_names": supplier_names,
        "supplier_name": supplier_name,
        "seller_name": supplier_name,
        "seller_name_en": first("supplier_name_en") or supplier_name,
        "seller_name_zh": first("supplier_name_zh"),
        "seller_address": first("address") or first("seller_address"),
        "buyer": first("buyer") or first("consignee"),
        "consignee": first("consignee") or first("buyer"),
        "buyer_address": first("buyer_address") or "",
        "invoice_no": first("invoice_no"),
        "contract_no": first("contract_no"),
        "date": date or first("date"),
        "currency": first("currency") or "",
        "incoterm": first("incoterm") or "",
        "destination": first("destination"),
        "destination_country": first("destination_country") or "",
        "destination_port": first("destination_port") or first("destination") or "",
        "loading_port": loading_port,
        "customs_office": customs_office,
        "vessel": first("vessel"),
        "bl_no": first("bl_no"),
        "container_no": ", ".join(dict.fromkeys([str((d.get("fields") or {}).get("container_no")) for d in docs if (d.get("fields") or {}).get("container_no")])),
        "packing": first("packing") or "",
        "signed_at": first("signed_at") or "",
        "shipping_mark": first("shipping_mark") or "",
        "remarks": first("remarks") or "",
        "transport": first("transport") or "",
        "supervision_mode": first("supervision_mode") or "",
        "tax_mode": first("tax_mode") or "",
        "pre_entry_no": "",
        "customs_no": "",
        "license_no": "",
        "total_amount": totals["amount"],
        "total_cartons": totals["cartons"],
        "total_pieces": totals["pieces"],
        "total_gross": totals["gross_weight"],
        "total_net": totals["net_weight"],
        "total_cbm": totals["cbm"],
    }
    # Do not derive an invoice number from a contract number; leave missing blank.
    if not doc["seller_address"]:
        # parser may expose the address under "address" on any doc
        doc["seller_address"] = next((str((d.get("fields") or {}).get("address")) for d in docs if (d.get("fields") or {}).get("address")), "")
    if not doc["buyer_address"]:
        doc["buyer_address"] = next((str((d.get("fields") or {}).get("buyer_address")) for d in docs if (d.get("fields") or {}).get("buyer_address")), "")

    source_types = sorted({str(d.get("type") or "unknown") for d in docs})
    coverage = {
        "packing_list": any(t in {"packing_list", "combined"} for t in source_types),
        "invoice": any(t in {"invoice", "combined"} for t in source_types),
        "sales_confirmation": "contract" in source_types,
        "customs_declaration": bool(aggregated) and not multi,
        "declaration_elements": bool(aggregated) and not multi,
    }
    doc["source_types"] = source_types
    doc["coverage"] = coverage

    files = []
    for d in docs:
        files.append({
            "id": d.get("file_id"), "filename": d.get("filename"), "supplier_id": d.get("supplier_id"),
            "supplier_name": (d.get("fields") or {}).get("supplier_name") or (supplier_by_id.get(d.get("supplier_id")) or {}).get("name"),
            "type": d.get("type"), "items": len(d.get("items") or []), "pages": (d.get("structure") or {}).get("page_count") or len((d.get("structure") or {}).get("pages") or (d.get("structure") or {}).get("sheets") or []) or 1,
        })
    return {
        "items": aggregated,
        "doc": doc,
        "totals": totals,
        "conflicts": conflicts,
        "documents": files,
        "coverage": coverage,
        "source_types": source_types,
        "supplier_names": supplier_names,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
