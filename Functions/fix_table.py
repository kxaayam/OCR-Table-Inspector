#!/usr/bin/env python3

import sys
from pathlib import Path

import Functions.check as check
import Functions.pipeline_state as pipeline_state
import Functions.stage2_locate as stage2_locate
import Functions.stage3_correct as stage3_correct

WORKING_PDF_DIR = Path(__file__).resolve().parent.parent / "working_pdf"


def _doc_folder_name(working_stem: str) -> str:
    """Map a working-copy stem back to the run's working_pdf folder name."""
    if working_stem.endswith(".working"):
        return working_stem[: -len(".working")]
    if "_working" in working_stem:
        return working_stem.replace("_working", "_original")
    return working_stem


def _sync_state(img_dir: Path, table_index: int, page: int,
                image_name: str) -> None:
    """Mark this table corrected in state.json / report.txt, if they exist."""
    state_path = img_dir / "state.json"
    report_path = img_dir / "report.txt"
    if not state_path.is_file():
        return
    state = pipeline_state.read_state(state_path)
    for t in state["tables"]:
        if t["table_index"] == table_index:
            t["status"] = "corrected"
            t["page"] = page
            t["image"] = image_name
            break
    pipeline_state.write_state(state, state_path, report_path)
    print(f"[fix] updated {state_path.name}")


def fix_table(working_path: str, table_index: int, page: int,
              doc_id: str = None,
              collection: str = stage2_locate.DEFAULT_COLLECTION) -> None:
    working = Path(working_path)
    if not working.is_file():
        sys.exit(f"error: working copy not found: {working}")
    folder = _doc_folder_name(working.stem)
    doc_id = doc_id or folder

    text = working.read_text(encoding="utf-8", errors="replace")
    matches = list(check.TABLE_RE.finditer(text))
    if not 0 <= table_index < len(matches):
        sys.exit(f"error: table {table_index} out of range "
                 f"(0..{len(matches) - 1})")

    img_dir = WORKING_PDF_DIR / folder
    img_dir.mkdir(parents=True, exist_ok=True)

    # The user picked this page, so fetch it fresh (no reuse).
    image_name = stage2_locate.image_name(page)
    try:
        got = stage2_locate.fetch_page_image(
            doc_id, page, str(img_dir / image_name), collection, reuse=False)
    except Exception as e:
        sys.exit(f"error: fetching n{page} for {doc_id} failed: {e}")
    if got is None:
        sys.exit(f"error: page n{page} not found (404) for {doc_id}")

    m = matches[table_index]
    caption = check.table_name(text, m.start())
    stage3_correct.write_request(str(img_dir), table_index, page, image_name,
                                 caption, m.group(0))

    corrected = stage3_correct.read_corrected(str(img_dir), table_index)
    if not corrected:
        resp = stage3_correct.response_path(str(img_dir), table_index)
        print(f"[fix] request ready for table {table_index} (n{page}).")
        print(f"      open {img_dir / image_name}, correct the table per "
              f"SKILL.md,")
        print(f"      save the <table> to {resp}, then re-run this command.")
        return

    status = stage3_correct.apply_corrected_table(
        str(working), table_index, corrected, page)
    if status != "corrected":
        sys.exit(f"{status}; working copy unchanged")
    print(f"[fix] table {table_index} rewritten from n{page} "
          f"in {working.name}")
    _sync_state(img_dir, table_index, page, image_name)


def main():
    argv = sys.argv[1:]
    table_index = page = None
    doc_id = None
    collection = stage2_locate.DEFAULT_COLLECTION
    positional = []
    i = 0
    try:
        while i < len(argv):
            if argv[i] == "--table" and i + 1 < len(argv):
                table_index = int(argv[i + 1]); i += 2
            elif argv[i] == "--page" and i + 1 < len(argv):
                page = int(argv[i + 1]); i += 2
            elif argv[i] == "--doc-id" and i + 1 < len(argv):
                doc_id = argv[i + 1]; i += 2
            elif argv[i] == "--collection" and i + 1 < len(argv):
                collection = argv[i + 1]; i += 2
            else:
                positional.append(argv[i]); i += 1
    except ValueError:
        table_index = page = None
    if len(positional) != 1 or table_index is None or page is None:
        print("usage: python -m Functions.fix_table <working.md> "
              "--table N --page P [--doc-id ID] [--collection NAME]")
        sys.exit(1)
    fix_table(positional[0], table_index, page, doc_id=doc_id,
              collection=collection)


if __name__ == "__main__":
    main()
