# -*- coding: utf-8 -*-
"""Per-supplier source-file backups (automatic on upload)."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from ..config import DATA_DIR

BACKUP_ROOT = DATA_DIR / "supplier_backups"


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name)[:120] or "file"


def backup_upload(supplier_id: str, source: Path, filename: str, digest: str, size: int) -> str:
    folder = BACKUP_ROOT / supplier_id / "files"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = folder / f"{stamp}_{_safe(filename)}"
    n = 1
    while target.exists():
        target = folder / f"{stamp}_{n}_{_safe(filename)}"
        n += 1
    shutil.copy2(source, target)
    manifest_path = BACKUP_ROOT / supplier_id / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        manifest = {"supplier_id": supplier_id, "files": []}
    manifest.setdefault("files", []).append({
        "filename": filename,
        "backup_path": str(target),
        "relative_path": str(target.relative_to(BACKUP_ROOT / supplier_id)),
        "sha256": digest,
        "size": size,
        "backed_up_at": datetime.now().isoformat(timespec="seconds"),
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(target)
