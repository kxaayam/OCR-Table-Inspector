#!/usr/bin/env python3

import sys
from pathlib import Path

import Functions.pipeline_state as pipeline_state
import Functions.stage3_correct as stage3_correct

SKILL_PATH = Path(__file__).resolve().parent / "SKILL.md"
WORKING_PDF_DIR = Path(__file__).resolve().parent.parent / "working_pdf"


def _doc_folder_name(working_stem: str) -> str:
    """Map a working-copy stem back to the run's working_pdf folder name."""
    if working_stem.endswith(".working"):
        return working_stem[: -len(".working")]
    if "_working" in working_stem:
        return working_stem.replace("_working", "_original")
    return working_stem


def fix_table(working_path: str, pdf_path: str, table_index: int,
              page: int) -> None:
    working = Path(working_path)
    pdf = Path(pdf_path)
    if not working.is_file():
        sys.exit(f"error: working copy not found: {working}")
    if not pdf.is_file():
        sys.exit(f"error: PDF not found: {pdf}")
    if not SKILL_PATH.is_file():
        sys.exit("error: SKILL.md not found next to fix_table.py")

    img_dir = WORKING_PDF_DIR / _doc_folder_name(working.stem)
    img_dir.mkdir(parents=True, exist_ok=True)
    skill_text = SKILL_PATH.read_text(encoding="utf-8")

    print(f"[fix] correcting table {table_index} from page {page} "
          f"(local model, slow)...")
    # reuse_image=False: the user picked this page, so render it fresh.
    status = stage3_correct.correct_table_by_index(
        str(working), str(pdf), table_index, page, skill_text, str(img_dir),
        reuse_image=False)
    if status != "corrected":
        sys.exit(f"{status}; working copy unchanged")
    print(f"[fix] table {table_index} rewritten from page {page} "
          f"in {working.name}")

    # keep state.json / report.txt in sync if this document has them
    state_path = img_dir / "state.json"
    report_path = img_dir / "report.txt"
    if state_path.is_file():
        state = pipeline_state.read_state(state_path)
        for t in state["tables"]:
            if t["table_index"] == table_index:
                t["status"] = "corrected"
                t["page"] = page
                t["image"] = f"page_{page}.png"
                break
        pipeline_state.write_state(state, state_path, report_path)
        print(f"[fix] updated {state_path.name}")


def main():
    argv = sys.argv[1:]
    table_index = page = None
    positional = []
    i = 0
    try:
        while i < len(argv):
            if argv[i] == "--table" and i + 1 < len(argv):
                table_index = int(argv[i + 1]); i += 2
            elif argv[i] == "--page" and i + 1 < len(argv):
                page = int(argv[i + 1]); i += 2
            else:
                positional.append(argv[i]); i += 1
    except ValueError:
        table_index = page = None
    if len(positional) != 2 or table_index is None or page is None:
        print("usage: python -m Functions.fix_table <working.md> <source.pdf> "
              "--table N --page P")
        sys.exit(1)
    fix_table(positional[0], positional[1], table_index, page)


if __name__ == "__main__":
    main()
