#!/usr/bin/env python3


import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from Functions.finding import Finding

DEFAULT_COLLECTION = "uoft-presidentsreports"
URL_TEMPLATE = ("https://content.library.utoronto.ca/{collection}/download/"
                "{doc_id}/page/n{n}.jpg")
DEFAULT_TIMEOUT = 60


@dataclass
class LocateResult:
    finding: Finding
    status: str                     # "located" | "manual_review"
    page: Optional[int] = None
    image_path: Optional[str] = None
    detail: str = ""


def image_name(n: int) -> str:
    """Local filename for scan image n."""
    return f"page_n{n}.jpg"


def page_image_url(doc_id: str, n: int, collection: str = DEFAULT_COLLECTION,
                   template: str = URL_TEMPLATE) -> str:
    return template.format(collection=collection, doc_id=doc_id, n=n)


def fetch_page_image(doc_id: str, n: int, out_path: str,
                     collection: str = DEFAULT_COLLECTION,
                     template: str = URL_TEMPLATE,
                     timeout: int = DEFAULT_TIMEOUT,
                     reuse: bool = True) -> Optional[str]:
    
    if reuse and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path
    url = page_image_url(doc_id, n, collection, template)
    req = urllib.request.Request(
        url, headers={"User-Agent": "ocr-table-inspector"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    if not data:
        return None
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(data)
    return out_path


def locate_page(finding: Finding, doc_id: str, image_dir: str,
                collection: str = DEFAULT_COLLECTION,
                template: str = URL_TEMPLATE,
                timeout: int = DEFAULT_TIMEOUT) -> LocateResult:
    """Fetch the page image for finding.page_guess (assumed to be the correct
    scan index). A missing page (404) or a network error becomes manual_review
    rather than a hard failure."""
    page = finding.page_guess
    if page is None or page < 0:
        return LocateResult(finding, "manual_review",
                            detail=f"no usable page guess ({page})")
    out_path = os.path.join(image_dir, image_name(page))
    try:
        got = fetch_page_image(doc_id, page, out_path, collection, template,
                               timeout)
    except Exception as e:                       # network/HTTP != 404
        return LocateResult(finding, "manual_review",
                            detail=f"fetch failed for n{page}: {e}")
    if got is None:
        return LocateResult(
            finding, "manual_review",
            detail=f"page n{page} not found (404) for {doc_id}")
    return LocateResult(finding, "located", page=page, image_path=got)


def main():
    """Read-only probe: detect tables and show the image URL each would use."""
    argv = sys.argv[1:]
    args = [a for a in argv if not a.startswith("--")]
    doc_id = None
    for i, a in enumerate(argv):
        if a == "--doc-id" and i + 1 < len(argv):
            doc_id = argv[i + 1]
    if len(args) != 1:
        print("usage: python3 -m Functions.stage2_locate document.md "
              "[--doc-id ID]")
        sys.exit(1)

    import Functions.stage1_detect as stage1_detect
    md = Path(args[0])
    doc_id = doc_id or md.stem
    doc = md.read_text(encoding="utf-8", errors="replace")
    findings = stage1_detect.detect(doc)
    if not findings:
        print("No problems found; nothing to locate.")
        return
    for f in findings:
        print(f'[n{f.page_guess}] "{f.caption[:50]}" -> '
              f'{page_image_url(doc_id, f.page_guess)}')


if __name__ == "__main__":
    main()
