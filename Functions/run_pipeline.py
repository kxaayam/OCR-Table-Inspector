#!/usr/bin/env python3

import re
import sys
from pathlib import Path

import Functions.correct as phase2
import Functions.page_locator as page_locator
import Functions.pipeline_state as pipeline_state
import Functions.stage0_copy as stage0_copy
import Functions.stage1_detect as stage1_detect
import Functions.stage2_locate as stage2_locate

SKILL_PATH = Path(__file__).resolve().parent / "SKILL.md"
WORKING_DIR = Path(__file__).resolve().parent.parent / "working_copies"
WORKING_PDF_DIR = Path(__file__).resolve().parent.parent / "working_pdf"


def _clean_caption(caption: str) -> str:
    """Strip markdown junk (###, **, etc.) from captions for display/report."""
    return re.sub(r"[#*_`]+", "", " ".join(caption.split())).strip()


def run(md_path: str, pdf_path: str, force: bool = False,
        correct: bool = False) -> None:
    md = Path(md_path)
    pdf = Path(pdf_path)
    if not md.is_file():
        sys.exit(f"error: markdown file not found: {md}")
    if not pdf.is_file():
        sys.exit(f"error: PDF file not found: {pdf}")
    if not SKILL_PATH.is_file():
        sys.exit(f"error: SKILL.md not found next to run_pipeline.py")
    if md.stem.endswith(".working") or "_working" in md.stem:
        sys.exit(
            f"error: {md.name} looks like a pipeline working copy, not an "
            f"original document.\nrun the pipeline on the original file; to "
            f"redo tables inside a working copy use Functions.fix_table."
        )

    # --- Stage 0: working copy ----------
    working = WORKING_DIR / stage0_copy.default_output(md).name
    if working.exists() and not force:
        sys.exit(
            f"error: {working} already exists and may hold prior corrections.\n"
            f"pass --force to overwrite it, or redo single tables with:\n"
            f"  python3 -m Functions.fix_table {working} {pdf} --table N --page P"
        )
    stage0_copy.make_working_copy(md, working, force=True)
    print(f"[stage 0] working copy -> {working.name}")

    # --- Stage 1: detect ------
    doc = working.read_text(encoding="utf-8", errors="replace")
    findings = stage1_detect.detect(doc)
    print(f"[stage 1] {len(findings)} problem table(s) found")
    if not findings:
        print("[done] nothing to correct.")
        return

    # --- Stage 2: page from the divider count; render that page ----------
    img_dir = WORKING_PDF_DIR / md.stem
    img_dir.mkdir(parents=True, exist_ok=True)
    state_path = img_dir / "state.json"
    report_path = img_dir / "report.txt"

    n_pages = stage2_locate.pdf_page_count(str(pdf))
    md_pages = len(page_locator.divider_positions(doc)) + 1
    if md_pages != n_pages:
        print(f"[warning] markdown implies {md_pages} pages but the PDF has "
              f"{n_pages} — divider drift is possible; check the images in "
              f"{img_dir}")

    rows = {}   # table_index -> {page, image, status, caption}

    def write_state():
        """Build the state dict and hand it to the shared writer (state.json +
        report.txt), so an interrupted run always leaves an accurate record and
        the format matches the correct/fix_table commands."""
        state = {"document": md.name, "working_copy": str(working),
                 "pdf": str(pdf),
                 "tables": [{"table_index": i, "page": rows[i]["page"],
                             "image": rows[i]["image"],
                             "status": rows[i]["status"],
                             "caption": rows[i]["caption"]}
                            for i in sorted(rows)]}
        pipeline_state.write_state(state, state_path, report_path)

    to_correct = []
    manual = 0
    for f in findings:
        r = stage2_locate.locate_in_pdf(f, str(pdf), image_dir=str(img_dir),
                                        n_pages=n_pages)
        cap = _clean_caption(f.caption)
        if r.status == "located" and r.image_path:
            to_correct.append((f, r.image_path))
            rows[f.table_index] = {"page": r.page,
                                   "image": Path(r.image_path).name,
                                   "status": "pending", "caption": cap}
            print(f'  page {r.page:<3} <- table {f.table_index:>3} "{cap[:55]}"')
        else:
            manual += 1
            rows[f.table_index] = {"page": None, "image": None,
                                   "status": f"manual_review: {r.detail}",
                                   "caption": cap}
            print(f'  MANUAL     <- table {f.table_index:>3} "{cap[:55]}" '
                  f'({r.detail})')
    write_state()
    print(f"[stage 2] {len(to_correct)} located, {manual} need manual review")
    print(f"[stage 2] report -> {report_path}")

    if not to_correct:
        print("[done] no tables could be located; nothing to correct.")
        return

    # --- Checkpoint: stop for review unless --correct was given ----------
    if not correct:
        print()
        print(f"[phase 1 complete] {len(to_correct)} table(s) located, "
              f"{manual} flagged for manual review.")
        print(f"[review] check the page images in {img_dir}")
        print(f"         and {report_path.name} before spending model time.")
        print(f"[next]   corrections are NOT run yet. When the pages look right:")
        print(f"           python3 -m Functions.correct {md} {pdf}")
        print(f"         (resumable: safe to re-run if interrupted)")
        print(f"         other options:")
        print(f"         - one table only: python3 -m Functions.fix_table "
              f"{working} {pdf} --table N --page P")
        print(f"         - skip this review next time: --force --correct")
        return

    # --- Stage 3: delegate to the single correction path ------------------
    phase2.correct(md_path, pdf_path)


def main():
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2 or (flags - {"--force", "--correct"}):
        print("usage: python -m Functions.run_pipeline <document.md> "
              "<source.pdf> [--correct] [--force]")
        sys.exit(1)
    run(args[0], args[1], force="--force" in flags, correct="--correct" in flags)


if __name__ == "__main__":
    main()
