#!/usr/bin/env python3

import base64
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

from Functions.finding import Finding

DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:12b-it-q8_0")
DEFAULT_HOST = "http://localhost:11434"

_TABLE_RE = re.compile(r"<table\b.*?</table>", re.S | re.I)


def _build_messages(finding: Finding, image_b64: str, skill_text: str):
    system = skill_text
    user = re.sub(r"[#*_`]+", "", " ".join(finding.caption.split())).strip()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user, "images": [image_b64]},
    ]


def correct_table(finding: Finding, image_path: str, skill_text: str,
                  model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
                  timeout: int = 1800) -> Optional[str]:
    image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    payload = {
        "model": model,
        "messages": _build_messages(finding, image_b64, skill_text),
        "stream": False,
        "think": False,
    }
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return extract_table_html(data.get("message", {}).get("content", ""))


def extract_table_html(text: str) -> Optional[str]:
    m = _TABLE_RE.search(text or "")
    return m.group(0) if m else None


def apply_corrections(working_path: str,
                      corrections: List[Tuple[Finding, str]]
                      ) -> List[Finding]:
    path = Path(working_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    applied: List[Finding] = []
    for finding, corrected in sorted(corrections, key=lambda c: c[0].start,
                                     reverse=True):
        if text[finding.start:finding.end] != finding.table_html:
            raise ValueError(
                f"correction target not found at recorded position "
                f"{finding.start}:{finding.end} (table_index {finding.table_index})"
            )
        text = text[:finding.start] + corrected + text[finding.end:]
        applied.append(finding)
    path.write_text(text, encoding="utf-8")
    return applied


def correct_table_by_index(working_path: str, pdf_path: str, table_index: int,
                           page, skill_text: str, image_dir: str,
                           reuse_image: bool = True) -> str:
    import Functions.stage2_locate as stage2_locate
    import Functions.check as check
    working = Path(working_path)
    text = working.read_text(encoding="utf-8", errors="replace")
    tables = list(_TABLE_RE.finditer(text))
    if not 0 <= table_index < len(tables):
        return f"error: table {table_index} out of range (0..{len(tables) - 1})"
    n_pages = stage2_locate.pdf_page_count(pdf_path)
    if page is None or not 1 <= page <= n_pages:
        return f"error: page {page} outside PDF (1..{n_pages})"

    m = tables[table_index]
    img_path = os.path.join(image_dir, f"page_{page}.png")
    if not (reuse_image and os.path.exists(img_path)):
        stage2_locate.render_page(pdf_path, page - 1, img_path)

    finding = Finding(check_name="correct", table_index=table_index,
                      start=m.start(), end=m.end(), table_html=m.group(0),
                      page_guess=page, caption=check.table_name(text, m.start()),
                      summary="", details={})
    try:
        corrected = correct_table(finding, img_path, skill_text)
    except Exception as e:                  
        return f"error: {e}"
    if not corrected:
        return "no usable table from model"
    try:
        apply_corrections(str(working), [(finding, corrected)])
    except ValueError as e:
        return f"error: {e}"
    return "corrected"
