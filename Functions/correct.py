#!/usr/bin/env python3


import sys
from pathlib import Path

import Functions.check as check
import Functions.pipeline_state as pipeline_state
import Functions.stage2_locate as stage2_locate
import Functions.stage3_correct as stage3_correct

WORKING_DIR = Path(__file__).resolve().parent.parent / "working_copies"
WORKING_PDF_DIR = Path(__file__).resolve().parent.parent / "working_pdf"


def _needs_correcting(status: str) -> bool:
    return status != "corrected" and not str(status).startswith("manual_review")


def correct(md_path: str, doc_id: str = None) -> None:
    md = Path(md_path)
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
                 f"  python3 -m Functions.run_pipeline {md}")

    state = pipeline_state.read_state(state_path)
    doc_id = doc_id or state.get("doc_id") or md.stem
    collection = state.get("collection", stage2_locate.DEFAULT_COLLECTION)
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

    # --- Pass 1: make sure every pending table has its image + a request ------
    text = working.read_text(encoding="utf-8", errors="replace")
    matches = list(check.TABLE_RE.finditer(text))
    for t in sorted(todo, key=lambda x: x["table_index"]):
        idx, page = t["table_index"], t["page"]
        image_name = t.get("image") or (
            stage2_locate.image_name(page) if page is not None else "-")
        # A missing full-page image can be re-fetched. A selected crop cannot:
        # regenerating it requires detector/OCR provenance, so leave it missing.
        is_page_image = Path(image_name).name == stage2_locate.image_name(page)
        if page is not None and is_page_image and not (img_dir / image_name).exists():
            try:
                stage2_locate.fetch_page_image(
                    doc_id, page, str(img_dir / image_name), collection)
            except Exception as e:
                print(f"  [warning] could not fetch {image_name} for table "
                      f"{idx}: {e}")
        if 0 <= idx < len(matches):
            m = matches[idx]
            caption = t.get("caption") or check.table_name(text, m.start())
            stage3_correct.write_request(str(img_dir), idx, page, image_name,
                                         caption, m.group(0))

    # --- Pass 2: apply whatever responses Claude has produced -----------------
    applied = 0
    awaiting = []
    for t in sorted(todo, key=lambda x: x["table_index"]):
        idx, page = t["table_index"], t["page"]
        corrected = stage3_correct.read_corrected(str(img_dir), idx)
        if not corrected:
            awaiting.append((idx, page))
            continue
        status = stage3_correct.apply_corrected_table(
            str(working), idx, corrected, page)
        t["status"] = status
        pipeline_state.write_state(state, state_path, report_path)
        if status == "corrected":
            applied += 1
            print(f'  applied    <- table {idx:>3} (n{page})')
        else:
            awaiting.append((idx, page))
            print(f'  {status:<28} <- table {idx:>3} (n{page})')

    if applied:
        print(f"[correct] spliced {applied} corrected table(s) into "
              f"{working.name}")

    if awaiting:
        print()
        print(f"[waiting on Claude] {len(awaiting)} table(s) still need "
              f"correcting. For each one:")
        print(f"  1. open its page image in {img_dir}")
        print(f"  2. read the OCR table in {stage3_correct.requests_dir(str(img_dir))}")
        print(f"  3. save the corrected <table> to "
              f"{stage3_correct.responses_dir(str(img_dir))}:")
        for idx, page in awaiting:
            print(f'       table {idx:>3}  ->  responses/table_{idx}.html')
        print(f"  then re-run this command to splice them in (resumable).")
    else:
        remaining = sum(1 for t in tables if _needs_correcting(t["status"]))
        if remaining == 0:
            print(f"[done] all located tables corrected; result in "
                  f"{working.name}")


def main():
    argv = sys.argv[1:]
    doc_id = None
    positional = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--doc-id" and i + 1 < len(argv):
            doc_id = argv[i + 1]; i += 2
        elif a.startswith("--"):
            positional = []; break            # unknown flag -> show usage
        else:
            positional.append(a); i += 1

    if len(positional) != 1:
        print("usage: python -m Functions.correct <document.md> [--doc-id ID]")
        sys.exit(1)
    correct(positional[0], doc_id=doc_id)


if __name__ == "__main__":
    main()
