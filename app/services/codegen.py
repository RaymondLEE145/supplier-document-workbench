# -*- coding: utf-8 -*-
"""Generate the executable Python fill script and run it."""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import template_engine

ALLOWED_IMPORTS = {"json", "sys", "os", "re", "copy", "pathlib", "openpyxl", "pandas", "datetime", "typing"}


def _engine_source() -> str:
    src = Path(template_engine.__file__).read_text(encoding="utf-8")
    marker = 'if __name__ == "__main__":'
    if marker in src:
        src = src.split(marker)[0]
    src = src.replace("from __future__ import annotations\n", "")
    return src.rstrip()


def generate_script(payload: dict, template_path: str | Path, output_path: str | Path, script_path: str | Path,
                    engine: str = "structural", llm_note: str = "") -> dict:
    template_path = str(Path(template_path).resolve())
    output_path = str(Path(output_path).resolve())
    script_path = Path(script_path)
    payload_json = json.dumps(payload, ensure_ascii=False, indent=1)
    header = f'''# -*- coding: utf-8 -*-
"""
AUTO-GENERATED export script — Supplier Document Workbench
engine: {engine}
{llm_note}
This script reads the user's original Excel template, applies the standardized
supplier-document payload, rebuilds the five sheets while preserving styles and
merged cells, rewrites SUM / cross-sheet formulas, and saves the output workbook.

Usage:
    python generated_fill.py [template.xlsx] [output.xlsx]
The payload is embedded below, so the script is runnable on its own.
"""
'''
    body = _engine_source()
    footer = f'''

# ---------------------------------------------------------------------------
# generated payload (standard intermediate model + document header fields)
# ---------------------------------------------------------------------------
PAYLOAD = json.loads({payload_json!r})
DEFAULT_TEMPLATE = r"""{template_path}"""
DEFAULT_OUTPUT = r"""{output_path}"""


if __name__ == "__main__":
    tpl = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEMPLATE
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT
    report = fill_workbook(tpl, PAYLOAD, out)
    report["engine"] = {engine!r}
    print(json.dumps(report, ensure_ascii=False))
'''
    code = header + body + footer
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(code, encoding="utf-8")
    return {"path": str(script_path), "bytes": script_path.stat().st_size, "engine": engine,
            "payload": payload, "template": template_path, "output": output_path}


def validate_python(code: str) -> tuple[bool, str]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                root = name.split(".")[0]
                if root and root not in ALLOWED_IMPORTS:
                    return False, f"不允许的导入: {name}"
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in {"eval", "exec", "compile", "__import__"}:
                return False, f"不允许的调用: {fn.id}"
    return True, "ok"


def run_script(script_path: str | Path, template_path: str | Path, output_path: str | Path, timeout: int = 120) -> dict:
    cmd = [sys.executable, str(script_path), str(template_path), str(output_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-4000:],
        "cmd": cmd,
    }


# ---------------------------------------------------------------------------
# optional LLM code generation
# ---------------------------------------------------------------------------
def build_llm_prompt(payload: dict, template_inspection: dict) -> str:
    skeleton = json.dumps({
        "template": template_inspection,
        "payload_preview": {
            "doc": payload.get("doc"),
            "items": payload.get("items", [])[:4],
            "count": len(payload.get("items", [])),
        },
        "requirements": [
            "输出一个可独立运行的 Python 脚本（仅使用 openpyxl / pandas / json / copy / re）",
            "读取用户原始 xlsx 模板，不能新建空白工作簿替代",
            "必须保留 5 个 Sheet、表头样式、合并单元格，处理循环插入行",
            "必须重写 SUM 合计公式与跨 Sheet 公式（销货确认书 → 报关单），保持相对引用",
            "装箱清单列：NO/图片/英文品名/中文品名/HS/材质/箱数/每箱件数/L/M/H/CBM/毛重/包装类型",
            "发票列：NO/英文品名/中文品名/HS/材质/外箱数量/每箱件数/计价件数/单价/金额",
            "报关单：合同号、贸易国、运抵国、指运港、件数、毛净重、成交方式、商品项（10位HS/数量/单价/总价/币制）",
            "不得编造数据；缺失字段留空",
            "脚本入口：python script.py template.xlsx output.xlsx",
        ],
    }, ensure_ascii=False, indent=1)
    return (
        "你是顶级 Excel 模板工程师。请基于以下模板结构与标准化单证数据，生成一段可执行 Python 脚本。"
        "只返回代码块，不要解释。\n\n" + skeleton
    )


def try_llm_script(prompt: str, settings: dict, script_path: Path) -> tuple[bool, str, str]:
    """Call an OpenAI-compatible endpoint if the user configured one. Returns (ok, code, note)."""
    llm = (settings or {}).get("llm") or {}
    if not llm.get("enabled") or not llm.get("api_key"):
        return False, "", "LLM 未配置，使用确定性结构代码生成器"
    base = (llm.get("base_url") or "https://api.deepseek.com/v1").rstrip("/")
    model = llm.get("model") or "deepseek-chat"
    import urllib.request
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps({
            "model": model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": "You are an expert Python/openpyxl template engineer. Return only a fenced Python code block."},
                {"role": "user", "content": prompt},
            ],
        }).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {llm['api_key']}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        text = data["choices"][0]["message"]["content"]
        m = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
        code = m.group(1).strip() if m else text.strip()
        ok, note = validate_python(code)
        if not ok:
            return False, "", f"LLM 脚本校验失败：{note}"
        script_path.write_text(code, encoding="utf-8")
        return True, code, "LLM 生成脚本通过 AST 校验"
    except Exception as exc:
        return False, "", f"LLM 调用失败：{type(exc).__name__}: {exc}"
