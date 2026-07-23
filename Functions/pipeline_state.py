#!/usr/bin/env python3

import json
from pathlib import Path


def write_state(state: dict, state_path, report_path) -> None:
    Path(state_path).write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    lines = [
        f'document: {state["document"]}',
        f'working copy: {state["working_copy"]}',
        f'doc id: {state.get("doc_id", "")}',
        f'collection: {state.get("collection", "")}',
        "note: table N = Nth <table> block in the document (0-based),",
        f'      redo one with: python3 -m Functions.fix_table '
        f'{state["working_copy"]} --table N --page P',
        "",
    ]
    for t in state["tables"]:
        page = str(t["page"]) if t["page"] is not None else "-"
        img = t["image"] or "-"
        lines.append(f'table {t["table_index"]:>3} | page {page:>4} | '
                     f'{img:<14} | {t["status"]:<28} | {t["caption"]}')
    Path(report_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_state(state_path) -> dict:
    return json.loads(Path(state_path).read_text(encoding="utf-8"))
