#!/usr/bin/env python3

import sys
from pathlib import Path

import stage0_copy
import stage1_detect
import stage2_locate
import stage3_correct

SKILL_PATH = Path(__file__).resolve().parent / "SKILL.md"


def run(md_path: str, pdf_path: str) -> None:
    md = Path(md_path)
    pdf = Path(pdf_path)
    if not md.is_file():
        sys.exit(f"error: markdown file not found: {md}")
    if not pdf.is_file():
        sys.exit(f"error: PDF file not found: {pdf}")
    if not SKILL_PATH.is_file():
        sys.exit(f"error: SKILL.md not found next to run_pipeline.py")

    # --- Stage 0: working copy ----------
    working = stage0_copy.default_output(md)
    stage0_copy.make_working_copy(md, working, force=True)
    print(f"[stage 0] working copy -> {working.name}")

    # --- Stage 1: detect ------
    doc = working.read_text(encoding="utf-8", errors="replace")
    findings = stage1_detect.detect(doc)
    print(f"[stage 1] {len(findings)} problem table(s) found")
    if not findings:
        print("[done] nothing to correct.")
        return

    # --- Stage 2: locate (read the PDF once, reuse across findings) ------
    img_dir = md.with_name(md.stem + "_pages")
    img_dir.mkdir(exist_ok=True)
    page_texts = stage2_locate.extract_page_texts(str(pdf))
    stats = stage2_locate.document_stats(page_texts)
    print(f"[stage 2] read {len(page_texts)} PDF pages; locating each table...")

    to_correct = []         
    manual = 0
    for f in findings:
        r = stage2_locate.locate_in_pdf(
            f, str(pdf), image_dir=str(img_dir),
            stats=stats, page_texts=page_texts)
        if r.status == "located" and r.image_path:
            to_correct.append((f, r.image_path))
            print(f'  page {r.page:<3} <- "{f.caption[:55]}"')
        else:
            manual += 1
            print(f'  MANUAL     <- "{f.caption[:55]}" ({r.detail})')
    print(f"[stage 2] {len(to_correct)} located, {manual} need manual review")

    if not to_correct:
        print("[done] no tables could be located; nothing to correct.")
        return

    # --- Stage 3: correct with gemma4 + SKILL, write into the copy -------
    skill_text = SKILL_PATH.read_text(encoding="utf-8")
    print(f"[stage 3] correcting {len(to_correct)} table(s) with gemma4 "
          f"(one model call each -- this is slow)...")

    corrections = []      
    for f, image_path in to_correct:
        try:
            corrected = stage3_correct.correct_table(f, image_path, skill_text)
        except Exception as e: 
            corrected = None
            print(f'  ERROR      <- "{f.caption[:55]}" ({e})')
            continue
        if corrected:
            corrections.append((f, corrected))
            print(f'  corrected  <- "{f.caption[:55]}"')
        else:
            print(f'  no table   <- "{f.caption[:55]}" (model gave no usable table)')

    applied, skipped = stage3_correct.apply_corrections(str(working), corrections)
    print(f"[stage 3] wrote {len(applied)} correction(s) into {working.name}")

    # --- final check: what (if anything) is still broken -----------------
    remaining = stage1_detect.detect(
        working.read_text(encoding="utf-8", errors="replace"))
    print(f"[done] {len(remaining)} table(s) still flagged after correction; "
          f"result is in {working.name}")


def main():
    if len(sys.argv) != 3:
        print("usage: python run_pipeline.py <document.md> <source.pdf>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
