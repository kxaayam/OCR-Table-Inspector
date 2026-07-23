#!/usr/bin/env python3


import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

from Functions.finding import Finding

_TABLE_RE = re.compile(r"<table\b.*?</table>", re.S | re.I)


# --- agent handoff paths -----------------------------------------------------

def requests_dir(image_dir: str) -> str:
    return os.path.join(image_dir, "requests")


def responses_dir(image_dir: str) -> str:
    return os.path.join(image_dir, "responses")


def request_path(image_dir: str, table_index: int) -> str:
    return os.path.join(requests_dir(image_dir), f"table_{table_index}.html")


def response_path(image_dir: str, table_index: int) -> str:
    return os.path.join(responses_dir(image_dir), f"table_{table_index}.html")


def write_request(image_dir: str, table_index: int, page, image_name: str,
                  caption: str, ocr_table_html: str) -> str:
    """Write the correction request Claude will act on: the raw OCR table, with
    a header naming the page image and where to save the corrected table."""
    os.makedirs(requests_dir(image_dir), exist_ok=True)
    os.makedirs(responses_dir(image_dir), exist_ok=True)
    out = request_path(image_dir, table_index)
    header = (
        f"<!-- table {table_index} | page {page} | image: {image_name}\n"
        f"     caption: {caption}\n"
        f"     Open the referenced image, then rewrite the table below so it matches\n"
        f"     the printed page, following SKILL.md. Save ONLY the corrected\n"
        f"     <table>...</table> to responses/table_{table_index}.html -->\n"
    )
    Path(out).write_text(header + ocr_table_html + "\n", encoding="utf-8")
    return out


def read_corrected(image_dir: str, table_index: int) -> Optional[str]:
    """Return Claude's corrected <table> for this index, or None if there is no
    response file yet (or it holds no usable table)."""
    p = Path(response_path(image_dir, table_index))
    if not p.is_file():
        return None
    return extract_table_html(p.read_text(encoding="utf-8", errors="replace"))


def extract_table_html(text: str) -> Optional[str]:
    m = _TABLE_RE.search(text or "")
    return m.group(0) if m else None


# --- safe write-back ---------------------------------------------------------

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


def apply_corrected_table(working_path: str, table_index: int,
                          corrected_html: str, page=None) -> str:
    """Splice Claude's corrected <table> into the working copy in place of the
    Nth table. The Nth table is re-located on each call, so this is safe to run
    repeatedly and in any order; apply_corrections still verifies the original
    text is exactly where we found it before replacing."""
    import Functions.check as check
    text = Path(working_path).read_text(encoding="utf-8", errors="replace")
    tables = list(_TABLE_RE.finditer(text))
    if not 0 <= table_index < len(tables):
        return f"error: table {table_index} out of range (0..{len(tables) - 1})"
    corrected = extract_table_html(corrected_html)
    if not corrected:
        return "error: response holds no <table>...</table>"
    m = tables[table_index]
    finding = Finding(check_name="correct", table_index=table_index,
                      start=m.start(), end=m.end(), table_html=m.group(0),
                      page_guess=page or 0,
                      caption=check.table_name(text, m.start()),
                      summary="", details={})
    try:
        apply_corrections(str(working_path), [(finding, corrected)])
    except ValueError as e:
        return f"error: {e}"
    return "corrected"
