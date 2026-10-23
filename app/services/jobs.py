# -*- coding: utf-8 -*-
"""Tiny in-process job manager used by upload / compliance / export."""
from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime
from typing import Any, Callable

from ..config import new_id, now_iso

_LOCK = threading.RLock()
JOBS: dict[str, dict] = {}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create(kind: str, meta: dict | None = None) -> dict:
    job_id = new_id("job_")
    job = {
        "id": job_id,
        "kind": kind,
        "status": "queued",
        "progress": 0,
        "phase": "排队中",
        "message": "任务已创建",
        "logs": [],
        "error": None,
        "result": None,
        "meta": meta or {},
        "created_at": _now(),
        "updated_at": _now(),
        "started_ts": time.time(),
    }
    with _LOCK:
        JOBS[job_id] = job
    return dict(job)


def get(job_id: str) -> dict | None:
    with _LOCK:
        job = JOBS.get(job_id)
        return dict(job) if job else None


def update(job_id: str, **kwargs) -> dict | None:
    with _LOCK:
        job = JOBS.get(job_id)
        if not job:
            return None
        job.update(kwargs)
        job["updated_at"] = _now()
        if kwargs.get("progress") is not None:
            job["progress"] = max(0, min(100, int(kwargs["progress"])))
        return dict(job)


def log(job_id: str, message: str, progress: float | None = None, phase: str | None = None) -> None:
    with _LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job["logs"].append({"at": _now(), "message": message})
        job["logs"] = job["logs"][-80:]
        job["message"] = message
        if progress is not None:
            job["progress"] = max(0, min(100, int(progress)))
        if phase:
            job["phase"] = phase
        job["updated_at"] = _now()


def fail(job_id: str, error: str) -> None:
    update(job_id, status="failed", error=error, message=error, phase="失败", progress=100)


def finish(job_id: str, result: Any = None, message: str = "完成") -> None:
    with _LOCK:
        job = JOBS.get(job_id)
        if job and job.get("status") == "failed":
            return
    update(job_id, status="done", progress=100, message=message, phase="完成", result=result)


def run(job_id: str, fn: Callable[[dict], Any], kind: str = "") -> None:
    """Run fn(job) in a daemon thread; never leave the job hanging."""
    def runner():
        update(job_id, status="running", phase="处理中", message="开始处理", progress=2)
        try:
            result = fn(job_id)
            finish(job_id, result=result, message="处理完成")
        except Exception as exc:
            fail(job_id, f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=6)}")
    threading.Thread(target=runner, name=f"job-{kind or job_id}", daemon=True).start()


def public(job: dict | None) -> dict | None:
    if not job:
        return None
    out = dict(job)
    out.pop("started_ts", None)
    return out
