#!/usr/bin/env python3

import base64
import json
import re
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

from finding import Finding

DEFAULT_MODEL = "gemma4:12b-it-q8_0"
DEFAULT_HOST = "http://localhost:11434"

_TABLE_RE = re.compile(r"<table\b.*?</table>", re.S | re.I)


def _build_messages(finding: Finding, image_b64: str, skill_text: str):
    system = (
        skill_text
        + "\n\n---\n\n"
        "TASK: You are correcting an OCR table transcription. You are given an "
        "image of a printed page and a rough HTML transcription of ONE table "
        "from that page; some rows have the wrong number of columns. Using the "
        "IMAGE as the authoritative source and following the formatting "
        "guidelines above (Update table mode), output the corrected HTML for "
        "that one table only. Output ONLY the corrected <table>...</table> "
        "markup -- no explanation, no code fences."
    )
    user = ("Rough HTML transcription to correct (it is one table on the page "
            "shown in the image):\n\n" + finding.table_html)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user, "images": [image_b64]},
    ]


def correct_table(finding: Finding, image_path: str, skill_text: str,
                  model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
                  timeout: int = 600) -> Optional[str]:
    image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    payload = {
        "model": model,
        "messages": _build_messages(finding, image_b64, skill_text),
        "stream": False,
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
                      ) -> Tuple[List[Finding], List[Finding]]:
    path = Path(working_path)
    text = path.read_text(encoding="utf-8")
    applied: List[Finding] = []
    skipped: List[Finding] = []
    for finding, corrected in sorted(corrections, key=lambda c: c[0].start,
                                     reverse=True):
        if text[finding.start:finding.end] == finding.table_html:
            text = text[:finding.start] + corrected + text[finding.end:]
            applied.append(finding)
        else:
            skipped.append(finding)
    path.write_text(text, encoding="utf-8")
    return applied, skipped
