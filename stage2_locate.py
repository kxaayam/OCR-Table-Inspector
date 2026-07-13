#!/usr/bin/env python3

import math
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import check
from finding import Finding


DISTINCT_MAX_FRAC = 0.2    
                          
MAX_SEARCH_RADIUS = 3    

_PLACEHOLDER_LABELS = {"(empty row)", "(blank first cell)"}
_UNNAMED = "(unnamed)"



def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_numeric(norm: str) -> bool:
    return norm != "" and all(tok.isdigit() for tok in norm.split())


def _terms(norm_text: str) -> set:
    toks = norm_text.split()
    terms = set(toks)
    terms.update(f"{a} {b}" for a, b in zip(toks, toks[1:]))
    return terms



def build_probes(finding: Finding) -> Tuple[Optional[str], List[str]]:
    caption: Optional[str] = None
    if finding.caption and finding.caption != _UNNAMED:
        caption = normalize(finding.caption) or None

    labels: List[str] = []
    for row in check.parse_table(finding.table_html):
        raw = row.label()
        if raw in _PLACEHOLDER_LABELS:
            continue
        norm = normalize(raw)
        if not norm or _is_numeric(norm):
            continue
        labels.append(norm)
    return caption, labels


def fingerprint_terms(caption_norm: Optional[str], label_norms: List[str]) -> set:
    fp: set = set()
    if caption_norm:
        fp |= _terms(caption_norm)
    for lab in label_norms:
        fp |= _terms(lab)
    return fp



def document_stats(page_texts: List[str]) -> Tuple[List[set], Counter, int]:
    page_terms = [_terms(normalize(t)) for t in page_texts]
    df: Counter = Counter()
    for terms in page_terms:
        for term in terms:
            df[term] += 1
    return page_terms, df, len(page_texts)


def _idf(term: str, df: Counter, n: int) -> float:
    d = df.get(term, 0)
    return math.log(n / d) if d > 0 else 0.0


def _is_distinctive(term: str, df: Counter, n: int) -> bool:
    d = df.get(term, 0)
    return 0 < d <= max(1, int(DISTINCT_MAX_FRAC * n))


def _page_score(page_term_set: set, fp_terms: set, df: Counter, n: int) -> float:
    return sum(_idf(t, df, n) for t in fp_terms if t in page_term_set)


def _has_distinctive(page_term_set: set, fp_terms: set, df: Counter, n: int) -> bool:
    return any(t in page_term_set and _is_distinctive(t, df, n) for t in fp_terms)




def search_order(center: int, n_pages: int, max_radius: int) -> List[int]:
    order: List[int] = []
    if 0 <= center < n_pages:
        order.append(center)
    for r in range(1, max_radius + 1):
        for idx in (center + r, center - r):
            if 0 <= idx < n_pages:
                order.append(idx)
    return order



@dataclass
class LocateResult:
    finding: Finding
    status: str                    
    page: Optional[int] = None    
    resolved_by: str = ""      
    image_path: Optional[str] = None
    detail: str = ""


def locate(finding: Finding, page_texts: List[str],
           max_radius: int = MAX_SEARCH_RADIUS,
           stats: Optional[Tuple[List[set], Counter, int]] = None) -> LocateResult:
    n = len(page_texts)
    if n == 0:
        return LocateResult(finding, "manual_review",
                            detail="PDF has no pages / no text extracted")

    caption_norm, label_norms = build_probes(finding)
    fp_terms = fingerprint_terms(caption_norm, label_norms)
    if not fp_terms:
        return LocateResult(finding, "manual_review",
                            detail="no usable caption or row labels to search for")

    if stats is None:
        stats = document_stats(page_texts)
    page_terms, df, _ = stats

    center = max(0, min(finding.page_guess - 1, n - 1)) 


    best_idx: Optional[int] = None
    best_score = 0.0
    for idx in search_order(center, n, max_radius):
        if not _has_distinctive(page_terms[idx], fp_terms, df, n):
            continue
        score = _page_score(page_terms[idx], fp_terms, df, n)
        if best_idx is None or score > best_score:
            best_idx, best_score = idx, score

    if best_idx is None:
        return LocateResult(
            finding, "manual_review",
            detail=(f"no page within {max_radius} of guessed page {center + 1} "
                    f"contains a distinctive term from this table"))

    if best_idx == center:
        return LocateResult(finding, "located", page=best_idx + 1,
                            resolved_by="position",
                            detail=f"confirmed at guessed page (score {best_score:.1f})")
    return LocateResult(
        finding, "located", page=best_idx + 1, resolved_by="content_search",
        detail=(f"divider guess was page {center + 1}; best match on page "
                f"{best_idx + 1} (score {best_score:.1f})"))




def extract_page_texts(pdf_path: str) -> List[str]:
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    try:
        return [doc[i].get_text() for i in range(doc.page_count)]
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
                  max_radius: int = MAX_SEARCH_RADIUS,
                  stats: Optional[Tuple[List[set], Counter, int]] = None,
                  page_texts: Optional[List[str]] = None) -> LocateResult:
    if page_texts is None:
        page_texts = extract_page_texts(pdf_path)
    result = locate(finding, page_texts, max_radius=max_radius, stats=stats)
    if result.status == "located" and result.page is not None:
        out_path = os.path.join(image_dir or ".", f"page_{result.page}.png")
        result.image_path = render_page(pdf_path, result.page - 1, out_path)
    return result


def main():
    if len(sys.argv) != 3:
        print("usage: python stage2_locate.py document.md source.pdf")
        sys.exit(1)
    md_path, pdf_path = sys.argv[1], sys.argv[2]

    import stage1_detect
    with open(md_path, encoding="utf-8", errors="replace") as fh:
        doc = fh.read()

    findings = stage1_detect.detect(doc)
    if not findings:
        print("No problems found; nothing to locate.")
        return

    page_texts = extract_page_texts(pdf_path)
    stats = document_stats(page_texts)
    for f in findings:
        r = locate_in_pdf(f, pdf_path, page_texts=page_texts, stats=stats)
        where = f"page {r.page}" if r.page else "MANUAL REVIEW"
        print(f'[{where}] "{f.caption}" — {r.detail}')


if __name__ == "__main__":
    main()
