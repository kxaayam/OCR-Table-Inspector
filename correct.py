#!/usr/bin/env python3

import sys
from pathlib import Path

import Functions.pipeline_state as pipeline_state
import Functions.stage3_correct as stage3_correct

SKILL_PATH = Path(__file__).resolve().parent / "SKILL.md"
WORKING_DIR = Path(__file__).resolve().parent.parent / "working_copies"
WORKING_PDF_DIR = Path(__file__).resolve().parent.parent / "working_pdf"


def _needs_correcting(status: str) -> bool:
    return status != "corrected" and not str(status).startswith("manual_review")


def correct(md_path: str, pdf_path: str) -> None:
    md = Path(md_path)
    pdf = Path(pdf_path)
    if not pdf.is_file():
        sys.exit(f"error: PDF file not found: {pdf}")
    if not SKILL_PATH.is_file():
        sys.exit("error: SKILL.md not found next to correct.py")
    if md.stem.endswith(".working") or "_working" in md.stem:
        sys.exit(
            f"error: {md.name} looks like a pipeline working copy, not an "
            f"original document.\npass the same original file you gave the "
            f"locate step; to redo single tables use Functions.fix_table."
        )

    img_dir = WORKING_PDF_DIR / md.stem
    state_path = img_dir / "state.json"
    report_path = img_dir / "report.txt"
    if not state_path.is_file():
        sys.exit(f"error: no locate state at {state_path}\n"
                 f"run the locate step first:\n"
                 f"  python3 -m Functions.run_pipeline {md} {pdf}")

    state = pipeline_state.read_state(state_path)
    if Path(state["pdf"]).name != pdf.name:
        sys.exit(
            f"error: this document was located against "
            f"{Path(state['pdf']).name}, but you passed {pdf.name}.\n"
            f"page numbers in the state belong to that PDF — use the same "
            f"file, or re-run the locate step against the new one."
        )
    state["pdf"] = str(pdf)                       # this invocation's pdf path
    working = WORKING_DIR / Path(state["working_copy"]).name
    if not working.is_file():
        sys.exit(f"error: working copy {working} is missing; re-run locate.")

    tables = state["tables"]
    done = [t for t in tables if t["status"] == "corrected"]
    manual = [t for t in tables if str(t["status"]).startswith("manual_review")]
    todo = [t for t in tables if _needs_correcting(t["status"])]
    print(f"[correct] {len(todo)} to do, {len(done)} already corrected, "
          f"{len(manual)} manual-review (skipped)")
    if not todo:
        print("[done] nothing left to correct.")
        return

    skill_text = SKILL_PATH.read_text(encoding="utf-8")
    print(f"[correct] {len(todo)} table(s) with the local model (one call "
          f"each -- slow); safe to re-run if interrupted")

    n_ok = 0
    for t in sorted(todo, key=lambda x: x["table_index"]):
        idx, page = t["table_index"], t["page"]
        status = stage3_correct.correct_table_by_index(
            str(working), str(pdf), idx, page, skill_text, str(img_dir))
        t["status"] = status
        pipeline_state.write_state(state, state_path, report_path)
        if status == "corrected":
            n_ok += 1
            print(f'  corrected  <- table {idx:>3} (page {page})')
        else:
            print(f'  {status:<28} <- table {idx:>3} (page {page})')

    remaining = sum(1 for t in tables if _needs_correcting(t["status"]))
    print(f"[done] corrected {n_ok} this run; {remaining} still need attention; "
          f"result in {working.name}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print("usage: python -m Functions.correct <document.md> <source.pdf>")
        sys.exit(1)
    correct(args[0], args[1])


if __name__ == "__main__":
    main()
