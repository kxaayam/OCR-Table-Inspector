#!/usr/bin/env python3

import os
import sys
from dataclasses import dataclass
from typing import Optional

from Functions.finding import Finding


@dataclass
class LocateResult:
    finding: Finding
    status: str                     # "located" | "manual_review"
    page: Optional[int] = None
    image_path: Optional[str] = None
    detail: str = ""


def pdf_page_count(pdf_path: str) -> int:
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    try:
        return doc.page_count
    finally:
        doc.close()


def render_page(pdf_path: str, page_index0: int, out_path: str,
                dpi: int = 200) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    try:
        doc[page_index0].get_pixmap(dpi=dpi).save(out_path)
    finally:
        doc.close()
    return out_path


def locate_in_pdf(finding: Finding, pdf_path: str,
                  image_dir: Optional[str] = None,
                  n_pages: Optional[int] = None) -> LocateResult:
    """The divider guess IS the page. Render it. If the guess falls outside
    the PDF, flag for manual review -- never clamp, never relocate."""
    if n_pages is None:
        n_pages = pdf_page_count(pdf_path)
    page = finding.page_guess
    if not 1 <= page <= n_pages:
        return LocateResult(
            finding, "manual_review",
            detail=f"divider guess {page} is outside the PDF (1..{n_pages})")
    out_path = os.path.join(image_dir or ".", f"page_{page}.png")
    return LocateResult(finding, "located", page=page,
                        image_path=render_page(pdf_path, page - 1, out_path))


def main():
    if len(sys.argv) != 3:
        print("usage: python3 -m Functions.stage2_locate document.md source.pdf")
        sys.exit(1)
    md_path, pdf_path = sys.argv[1], sys.argv[2]

    import Functions.stage1_detect as stage1_detect
    with open(md_path, encoding="utf-8", errors="replace") as fh:
        doc = fh.read()

    findings = stage1_detect.detect(doc)
    if not findings:
        print("No problems found; nothing to locate.")
        return

    n = pdf_page_count(pdf_path)
    for f in findings:
        if 1 <= f.page_guess <= n:
            print(f'[page {f.page_guess}] "{f.caption}"')
        else:
            print(f'[MANUAL REVIEW] "{f.caption}" — guess {f.page_guess} '
                  f'outside PDF (1..{n})')


if __name__ == "__main__":
    main()
