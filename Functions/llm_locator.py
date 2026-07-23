#!/usr/bin/env python3


import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import Functions.check as check
import Functions.stage2_locate as stage2_locate
from Functions.finding import Finding

DEFAULT_WINDOW = 8           # fetch guess +/- this many scan indices

MAX_HEADER_ITEMS = 24
MAX_ROW_LABELS = 8


@dataclass
class RelocateResult:
    finding: Finding
    guess: int
    candidates: List[int]
    selected: Optional[int]
    status: str                      # "located" | "manual_review" | "awaiting"
    image_path: Optional[str] = None
    detail: str = ""
    request_path: Optional[str] = None



def _locate_requests_dir(image_dir: str) -> str:
    return os.path.join(image_dir, "locate_requests")


def _locate_responses_dir(image_dir: str) -> str:
    return os.path.join(image_dir, "locate_responses")


def _locate_request_path(image_dir: str, table_index: int) -> str:
    return os.path.join(_locate_requests_dir(image_dir),
                        f"table_{table_index}.txt")


def _locate_response_path(image_dir: str, table_index: int) -> str:
    return os.path.join(_locate_responses_dir(image_dir),
                        f"table_{table_index}.txt")


# --- fingerprint -------------------------------------------------------------

def _clean(text: str) -> str:
    return re.sub(r"[#*_`]+", "", " ".join((text or "").split())).strip()


def _dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def build_fingerprint(finding: Finding) -> Dict[str, Any]:
    """Pull caption, header text, and distinctive row labels out of the flagged
    table so there is something concrete to match against the page images."""
    caption = _clean(finding.caption)

    headers: List[str] = []
    labels: List[str] = []
    try:
        rows = check.parse_table(finding.table_html)
    except Exception:
        rows = []
    for row in rows:
        if row.is_header:
            headers.extend(c.plain() for c in row.cells if c.plain())
        else:
            lbl = row.label()
            if lbl not in ("(empty row)", "(blank first cell)"):
                labels.append(lbl)

    # flagged rows are the damaged ones; their labels are still useful anchors
    for fr in finding.details.get("flagged_rows", []):
        lbl = (fr.get("label") or "").strip()
        if lbl and lbl not in ("(empty row)", "(blank first cell)"):
            labels.append(lbl)

    return {
        "caption": caption,
        "headers": _dedupe(headers)[:MAX_HEADER_ITEMS],
        "row_labels": _dedupe(labels)[:MAX_ROW_LABELS],
    }


def _fingerprint_text(fp: Dict[str, Any], candidates: List[int],
                      table_index: int) -> str:
    lines = [
        f"Locate the page holding table {table_index}.",
        f"Candidate scan indices (images in _candidates/cand_n<p>.jpg): "
        + ", ".join(str(p) for p in candidates),
        "",
        "Target table fingerprint:",
        f"  caption: {fp['caption'] or '(none)'}",
    ]
    if fp["headers"]:
        lines.append("  column headers: " + " | ".join(fp["headers"]))
    if fp["row_labels"]:
        lines.append("  row labels: " + " | ".join(fp["row_labels"]))
    lines += [
        "",
        f"Open the candidate images, decide which page contains this table, and",
        f"write that single scan index (or 'none') to "
        f"locate_responses/table_{table_index}.txt.",
    ]
    return "\n".join(lines)


def _candidate_window(guess: int, window: int) -> List[int]:
    # n is 0-based; the upper bound is unknown, so overshoot and let 404s drop.
    lo = max(0, guess - window)
    return list(range(lo, guess + window + 1))


def _fetch_candidates(doc_id: str, candidates: List[int], cand_dir: str,
                      collection: str) -> List[int]:
    """Fetch each candidate scan image; return the indices that actually
    exist (404s are skipped)."""
    os.makedirs(cand_dir, exist_ok=True)
    got: List[int] = []
    for p in candidates:
        out = os.path.join(cand_dir, f"cand_n{p}.jpg")
        try:
            path = stage2_locate.fetch_page_image(doc_id, p, out, collection)
        except Exception:
            path = None
        if path:
            got.append(p)
    return got


def read_choice(image_dir: str, table_index: int) -> Optional[int]:
    """Parse Claude's chosen scan index from the response file, or None if
    absent / 'none' / unparseable."""
    p = Path(_locate_response_path(image_dir, table_index))
    if not p.is_file():
        return None
    m = re.search(r"-?\d+", p.read_text(encoding="utf-8", errors="replace"))
    return int(m.group(0)) if m else None


# --- public entry points -----------------------------------------------------

def emit_candidates(finding: Finding, doc_id: str, image_dir: str,
                    window: int = DEFAULT_WINDOW,
                    collection: str = stage2_locate.DEFAULT_COLLECTION
                    ) -> RelocateResult:
    """Fetch the candidate window and write the locate request for Claude."""
    guess = finding.page_guess
    wanted = _candidate_window(guess, window)
    cand_dir = os.path.join(image_dir, "_candidates")
    candidates = _fetch_candidates(doc_id, wanted, cand_dir, collection)
    if not candidates:
        return RelocateResult(
            finding, guess, [], None, "manual_review",
            detail=f"no candidate images fetched around n{guess}")

    fp = build_fingerprint(finding)
    os.makedirs(_locate_requests_dir(image_dir), exist_ok=True)
    os.makedirs(_locate_responses_dir(image_dir), exist_ok=True)
    req_path = _locate_request_path(image_dir, finding.table_index)
    Path(req_path).write_text(
        _fingerprint_text(fp, candidates, finding.table_index) + "\n",
        encoding="utf-8")

    return RelocateResult(
        finding, guess, candidates, None, "awaiting",
        detail=f"candidates {candidates[0]}..{candidates[-1]} fetched; "
               f"awaiting page choice",
        request_path=req_path)


def record_choice(finding: Finding, doc_id: str, image_dir: str,
                  window: int = DEFAULT_WINDOW,
                  collection: str = stage2_locate.DEFAULT_COLLECTION
                  ) -> RelocateResult:
    """Read Claude's chosen scan index and, if it exists, fetch it as
    page_n<N>.jpg. Otherwise fall back to manual review."""
    guess = finding.page_guess
    selected = read_choice(image_dir, finding.table_index)
    if selected is None:
        return RelocateResult(
            finding, guess, [], None, "awaiting",
            detail="no page choice recorded yet")

    out_path = os.path.join(image_dir, stage2_locate.image_name(selected))
    try:
        got = stage2_locate.fetch_page_image(doc_id, selected, out_path,
                                             collection)
    except Exception as e:
        return RelocateResult(
            finding, guess, [], selected, "manual_review",
            detail=f"fetch failed for n{selected}: {e}")
    if got is None:
        return RelocateResult(
            finding, guess, [], selected, "manual_review",
            detail=f"chosen page n{selected} not found (404)")
    moved = " (== divider guess)" if selected == guess else \
        f" (relocated from divider guess {guess})"
    return RelocateResult(
        finding, guess, [], selected, "located",
        image_path=got, detail=f"page n{selected}{moved}")


def main():
    import argparse
    import Functions.stage1_detect as stage1_detect

    ap = argparse.ArgumentParser(
        description="Claude-assisted page locator (read-only probe).")
    ap.add_argument("md")
    ap.add_argument("--doc-id", default=None)
    ap.add_argument("--collection", default=stage2_locate.DEFAULT_COLLECTION)
    ap.add_argument("--table", type=int, help="only this table index")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    ap.add_argument("--image-dir", default=None)
    args = ap.parse_args()

    md = Path(args.md)
    doc_id = args.doc_id or md.stem
    doc = md.read_text(encoding="utf-8", errors="replace")
    findings = stage1_detect.detect(doc)
    if args.table is not None:
        findings = [f for f in findings if f.table_index == args.table]
    image_dir = args.image_dir or os.path.join(".", "_llm_locator_out")
    os.makedirs(image_dir, exist_ok=True)

    for f in findings:
        # If a choice is already recorded, act on it; otherwise emit candidates.
        if read_choice(image_dir, f.table_index) is not None:
            r = record_choice(f, doc_id, image_dir, window=args.window,
                              collection=args.collection)
        else:
            r = emit_candidates(f, doc_id, image_dir, window=args.window,
                                collection=args.collection)
        print(f'\ntable {f.table_index} "{_clean(f.caption)[:50]}"')
        print(f'  guess=n{r.guess} '
              f'candidates={r.candidates[0] if r.candidates else "-"}..'
              f'{r.candidates[-1] if r.candidates else "-"} '
              f'selected={r.selected} status={r.status}')
        print(f'  detail: {r.detail}')
        if r.request_path:
            print(f'  request: {r.request_path}')


if __name__ == "__main__":
    main()
