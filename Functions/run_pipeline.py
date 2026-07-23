#!/usr/bin/env python3

import os
import re
import sys
from pathlib import Path

import Functions.pipeline_state as pipeline_state
import Functions.stage0_copy as stage0_copy
import Functions.stage1_detect as stage1_detect
import Functions.stage2_locate as stage2_locate
import Functions.stage3_correct as stage3_correct
import Functions.llm_locator as llm_locator

WORKING_DIR = Path(__file__).resolve().parent.parent / "working_copies"
WORKING_PDF_DIR = Path(__file__).resolve().parent.parent / "working_pdf"


DEFAULT_COLLECTION = stage2_locate.DEFAULT_COLLECTION
URL_TEMPLATE = stage2_locate.URL_TEMPLATE


def _clean_caption(caption: str) -> str:
    """Strip markdown junk (###, **, etc.) from captions for display/report."""
    return re.sub(r"[#*_`]+", "", " ".join(caption.split())).strip()


def run(md_path: str, doc_id: str = None,
        collection: str = DEFAULT_COLLECTION,
        url_template: str = URL_TEMPLATE, force: bool = False,
        vision: bool = False,
        vision_window: int = llm_locator.DEFAULT_WINDOW) -> None:
    md = Path(md_path)
    if not md.is_file():
        sys.exit(f"error: markdown file not found: {md}")
    if md.stem.endswith(".working") or "_working" in md.stem:
        sys.exit(
            f"error: {md.name} looks like a pipeline working copy, not an "
            f"original document.\nrun the pipeline on the original file; to "
            f"redo tables inside a working copy use Functions.fix_table."
        )
    doc_id = doc_id or md.stem

    # --- Stage 0: working copy ----------
    working = WORKING_DIR / stage0_copy.default_output(md).name
    if working.exists() and not force:
        sys.exit(
            f"error: {working} already exists and may hold prior corrections.\n"
            f"pass --force to overwrite it, or redo single tables with:\n"
            f"  python3 -m Functions.fix_table {working} --table N --page P"
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

    # --- Stage 2: fetch each table's page image from the library ----------
    img_dir = WORKING_PDF_DIR / md.stem
    img_dir.mkdir(parents=True, exist_ok=True)
    state_path = img_dir / "state.json"
    report_path = img_dir / "report.txt"
    print(f"[stage 2] document '{doc_id}' via {collection}; fetching images...")

    rows = {}   # table_index -> state row

    def write_state():
        state = {"document": md.name, "working_copy": str(working),
                 "doc_id": doc_id, "collection": collection,
                 "vision_enabled": vision,
                 "tables": [rows[i] for i in sorted(rows)]}
        pipeline_state.write_state(state, state_path, report_path)

    to_correct = []
    manual = 0
    auto_locator = None
    vision_init_error = None
    if vision:
        try:
            from Functions.vision_locator import AutomaticVisionLocator
            auto_locator = AutomaticVisionLocator()
        except Exception as exc:
            vision_init_error = str(exc)
            print(f"  [vision unavailable] {exc}; using locator fallback")

    def fallback(f):
        """Use an existing recorded LLM choice, otherwise emit its request."""
        if llm_locator.read_choice(str(img_dir), f.table_index) is not None:
            return llm_locator.record_choice(
                f, doc_id, str(img_dir), window=vision_window,
                collection=collection)
        return llm_locator.emit_candidates(
            f, doc_id, str(img_dir), window=vision_window,
            collection=collection)

    for f in findings:
        cap = _clean_caption(f.caption)
        provenance = "page_guess"
        diagnostics = None
        full_page = None
        if vision and auto_locator is not None:
            try:
                r = auto_locator.locate(
                    f, doc_id, str(img_dir), window=vision_window,
                    collection=collection, template=url_template, debug=True)
            except Exception as exc:
                r = None
                vision_init_error = str(exc)
            if r is not None and r.status == "located":
                provenance = "automatic_vision"
                diagnostics = r.diagnostics_path
                full_page = r.full_page_path
            else:
                r = fallback(f)
                provenance = "llm_locator_fallback"
        elif vision:
            r = fallback(f)
            provenance = "llm_locator_fallback"
        else:
            r = stage2_locate.locate_page(
                f, doc_id, str(img_dir), collection=collection,
                template=url_template)

        if r.status == "located" and r.image_path:
            relative_image = os.path.relpath(r.image_path, img_dir)
            to_correct.append((f, r.image_path))
            rows[f.table_index] = {
                "table_index": f.table_index, "page": r.page,
                "image": relative_image, "status": "pending", "caption": cap,
                "locator": provenance,
                "full_page_image": (
                    os.path.relpath(full_page, img_dir) if full_page else
                    stage2_locate.image_name(r.page)),
                "matching_diagnostics": (
                    os.path.relpath(diagnostics, img_dir)
                    if diagnostics else None),
            }
            stage3_correct.write_request(
                str(img_dir), f.table_index, r.page,
                relative_image, cap, f.table_html)
            print(f'  n{r.page:<4} <- table {f.table_index:>3} "{cap[:55]}"')
        else:
            manual += 1
            detail = getattr(r, "detail", "") or vision_init_error or "unresolved"
            rows[f.table_index] = {
                "table_index": f.table_index, "page": None, "image": None,
                "status": f"manual_review: {detail}", "caption": cap,
                "locator": provenance, "full_page_image": None,
                "matching_diagnostics": None,
            }
            print(f'  MANUAL     <- table {f.table_index:>3} "{cap[:55]}" '
                  f'({r.detail})')
    write_state()
    print(f"[stage 2] {len(to_correct)} located, {manual} need manual review")
    print(f"[stage 2] report -> {report_path}")

    if not to_correct:
        print("[done] no tables could be located; nothing to correct.")
        return

    # --- Handoff to Claude for Stage 3 ------------------------------------
    print()
    print(f"[phase 1 complete] {len(to_correct)} table(s) located, "
          f"{manual} flagged for manual review.")
    print(f"[review] check the fetched page images in {img_dir}")
    print(f"         and {report_path.name} before correcting.")
    print(f"[stage 3] correction is done by Claude, not a model server:")
    print(f"          for each located table, open its page_nN.jpg image, read")
    print(f"          the matching requests/table_<idx>.html, and save the")
    print(f"          corrected <table> to responses/table_<idx>.html.")
    print(f"[apply]   then splice the corrections into the working copy with:")
    print(f"            python3 -m Functions.correct {md}")
    print(f"          (resumable: safe to re-run as you finish more tables)")
    print(f"          one table only: python3 -m Functions.fix_table "
          f"{working} --table N --page P")


def main():
    argv = sys.argv[1:]
    doc_id = collection = url_template = None
    force = vision = False
    vision_window = llm_locator.DEFAULT_WINDOW
    positional = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--doc-id" and i + 1 < len(argv):
            doc_id = argv[i + 1]; i += 2
        elif a == "--collection" and i + 1 < len(argv):
            collection = argv[i + 1]; i += 2
        elif a == "--url-template" and i + 1 < len(argv):
            url_template = argv[i + 1]; i += 2
        elif a == "--force":
            force = True; i += 1
        elif a == "--vision":
            vision = True; i += 1
        elif a == "--vision-window" and i + 1 < len(argv):
            vision_window = int(argv[i + 1]); i += 2
        elif a.startswith("--"):
            positional = []; break            # unknown flag -> show usage
        else:
            positional.append(a); i += 1

    if len(positional) != 1:
        print("usage: python -m Functions.run_pipeline <document.md> "
              "[--doc-id ID] [--collection NAME] [--url-template TPL] "
              "[--vision] [--vision-window N] [--force]")
        sys.exit(1)

    run(positional[0], doc_id=doc_id,
        collection=collection or DEFAULT_COLLECTION,
        url_template=url_template or URL_TEMPLATE, force=force,
        vision=vision, vision_window=vision_window)


if __name__ == "__main__":
    main()
