#!/usr/bin/env python3
"""Stage 2 helper: LLM-assisted page locator.

The divider count (finding.page_guess) is only a STARTING GUESS. This module
renders that page plus a window of neighbours, builds a small fingerprint from
the flagged table, and asks the local vision model which candidate page really
holds the table. The guess is used automatically only when the model answers
with high confidence; anything less falls back to manual review.

Reuses stage2_locate.render_page / pdf_page_count for all rendering. Does not
touch the markdown, the dividers, or the detector.
"""

import base64
import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import Functions.check as check
import Functions.stage2_locate as stage2_locate
from Functions.finding import Finding

DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:12b-it-q8_0")
DEFAULT_HOST = "http://localhost:11434"

DEFAULT_WINDOW = 8          # render guess +/- this many pages
DEFAULT_CANDIDATE_DPI = 100  # low dpi so a full window fits the model context
DEFAULT_TIMEOUT = 1800

MAX_HEADER_ITEMS = 24
MAX_ROW_LABELS = 8

SYSTEM_PROMPT = (
    "You identify which scanned page of a printed document contains one "
    "specific table. You are shown several page images in ascending page "
    "order, together with a fingerprint of the target table: its caption, its "
    "column headers, and a few of its row labels. At most one page is the "
    "target. Compare the fingerprint against the text visible on each page "
    "image and decide which page it is.\n"
    "Report confidence honestly:\n"
    "- high: the caption or the column headers plainly match exactly one page;\n"
    "- medium: a page is a likely match but you are not certain;\n"
    "- low: no page clearly matches, or several look similar.\n"
    "Return the actual PDF page number (one of the numbers you were given), or "
    "null if nothing clearly matches."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "page": {"type": ["integer", "null"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["page", "confidence"],
}


@dataclass
class RelocateResult:
    finding: Finding
    guess: int
    candidates: List[int]
    selected: Optional[int]
    confidence: str
    status: str                      # "located" | "manual_review"
    image_path: Optional[str] = None
    detail: str = ""
    timing: Dict[str, Any] = field(default_factory=dict)
    raw: str = ""


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
    table so the model has something concrete to match against."""
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


def _fingerprint_text(fp: Dict[str, Any], candidates: List[int]) -> str:
    first, last = candidates[0], candidates[-1]
    lines = [
        f"You are shown {len(candidates)} page images in ascending order.",
        f"Image 1 = PDF page {first}, and each following image is the next "
        f"page, up to image {len(candidates)} = PDF page {last}.",
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
        "Which PDF page contains this table? Answer with the page number "
        "(one of the numbers above) or null, plus your confidence.",
    ]
    return "\n".join(lines)


# --- model call --------------------------------------------------------------

def _render_candidates(pdf_path: str, candidates: List[int], cand_dir: str,
                       dpi: int) -> List[str]:
    os.makedirs(cand_dir, exist_ok=True)
    paths = []
    for p in candidates:
        out = os.path.join(cand_dir, f"cand_{p}.png")
        if not os.path.exists(out):
            stage2_locate.render_page(pdf_path, p - 1, out, dpi=dpi)
        paths.append(out)
    return paths


def _ask_model(fp_text: str, image_paths: List[str], model: str, host: str,
               timeout: int) -> Dict[str, Any]:
    images = [base64.b64encode(Path(p).read_bytes()).decode()
              for p in image_paths]
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": fp_text, "images": images},
        ],
        "stream": False,
        "think": False,
        "format": RESPONSE_SCHEMA,
        "options": {"temperature": 0, "num_predict": 64},
    }
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    wall = time.time() - t0
    data["_wallclock_s"] = wall
    return data


def _extract_timing(data: Dict[str, Any]) -> Dict[str, Any]:
    def sec(key):
        v = data.get(key)
        return round(v / 1e9, 2) if isinstance(v, (int, float)) else None
    return {
        "wallclock_s": round(data.get("_wallclock_s", 0), 2),
        "total_duration_s": sec("total_duration"),
        "load_duration_s": sec("load_duration"),
        "prompt_eval_count": data.get("prompt_eval_count"),
        "eval_count": data.get("eval_count"),
        "eval_duration_s": sec("eval_duration"),
    }


# --- public entry point ------------------------------------------------------

def relocate(finding: Finding, pdf_path: str, image_dir: str,
             window: int = DEFAULT_WINDOW,
             candidate_dpi: int = DEFAULT_CANDIDATE_DPI,
             model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
             timeout: int = DEFAULT_TIMEOUT,
             n_pages: Optional[int] = None) -> RelocateResult:
    """Confirm (or correct) finding.page_guess with the vision model.

    Auto-selects the model's page only on high confidence; otherwise returns a
    manual_review result. Renders the chosen page at full dpi as page_N.png so
    the existing correction workflow can reuse it.
    """
    if n_pages is None:
        n_pages = stage2_locate.pdf_page_count(pdf_path)
    guess = finding.page_guess

    lo = max(1, guess - window)
    hi = min(n_pages, guess + window)
    candidates = list(range(lo, hi + 1))
    if not candidates:
        return RelocateResult(
            finding, guess, [], None, "low", "manual_review",
            detail=f"divider guess {guess} has no candidate pages in 1..{n_pages}")

    fp = build_fingerprint(finding)
    fp_text = _fingerprint_text(fp, candidates)
    cand_dir = os.path.join(image_dir, "_candidates")
    cand_paths = _render_candidates(pdf_path, candidates, cand_dir,
                                    candidate_dpi)

    try:
        data = _ask_model(fp_text, cand_paths, model, host, timeout)
    except Exception as e:
        return RelocateResult(
            finding, guess, candidates, None, "low", "manual_review",
            detail=f"model call failed: {e}")

    timing = _extract_timing(data)
    content = data.get("message", {}).get("content", "") or ""
    try:
        parsed = json.loads(content)
        selected = parsed.get("page")
        confidence = parsed.get("confidence", "low")
        if selected is not None:
            selected = int(selected)
    except Exception as e:
        return RelocateResult(
            finding, guess, candidates, None, "low", "manual_review",
            detail=f"could not parse model response: {e}", timing=timing,
            raw=content)

    if confidence not in ("high", "medium", "low"):
        confidence = "low"

    # auto-use the page ONLY on high confidence and only if it is a page we
    # actually showed the model
    if confidence == "high" and selected in candidates:
        img_path = os.path.join(image_dir, f"page_{selected}.png")
        if not os.path.exists(img_path):
            stage2_locate.render_page(pdf_path, selected - 1, img_path)
        moved = " (== divider guess)" if selected == guess else \
            f" (relocated from divider guess {guess})"
        return RelocateResult(
            finding, guess, candidates, selected, confidence, "located",
            image_path=img_path,
            detail=f"model chose page {selected}{moved}", timing=timing,
            raw=content)

    reason = "no clear match" if selected is None else \
        (f"page {selected} outside candidate window"
         if selected not in candidates else f"confidence {confidence}")
    return RelocateResult(
        finding, guess, candidates, selected, confidence, "manual_review",
        detail=f"not auto-used: {reason}; divider guess was {guess}",
        timing=timing, raw=content)


def main():
    import argparse
    import Functions.stage1_detect as stage1_detect

    ap = argparse.ArgumentParser(
        description="LLM-assisted page locator (read-only probe).")
    ap.add_argument("md")
    ap.add_argument("pdf")
    ap.add_argument("--table", type=int, help="only this table index")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    ap.add_argument("--image-dir", default=None)
    args = ap.parse_args()

    doc = Path(args.md).read_text(encoding="utf-8", errors="replace")
    findings = stage1_detect.detect(doc)
    if args.table is not None:
        findings = [f for f in findings if f.table_index == args.table]
    image_dir = args.image_dir or os.path.join(".", "_llm_locator_out")
    os.makedirs(image_dir, exist_ok=True)

    n_pages = stage2_locate.pdf_page_count(args.pdf)
    for f in findings:
        r = relocate(f, args.pdf, image_dir, window=args.window, n_pages=n_pages)
        print(f'\ntable {f.table_index} "{_clean(f.caption)[:50]}"')
        print(f'  guess={r.guess} candidates={r.candidates[0]}..'
              f'{r.candidates[-1]} selected={r.selected} '
              f'confidence={r.confidence} status={r.status}')
        print(f'  detail: {r.detail}')
        print(f'  timing: {r.timing}')


if __name__ == "__main__":
    main()
