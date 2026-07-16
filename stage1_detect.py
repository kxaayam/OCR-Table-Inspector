#!/usr/bin/env python3


import sys
from typing import Callable, List

import Functions.check as check
from Functions.finding import Finding


# --- adapters: one per check -------------------------------------------------

def check1_adapter(doc: str) -> List[Finding]:
    """Wrap check.py (row-width damage detector) into common Findings."""
    matches = list(check.TABLE_RE.finditer(doc))
    findings: List[Finding] = []

    for r in check.inspect_document(doc):
        if not r.flagged:                    
            continue
        m = matches[r.index]

        flagged_rows = []
        for i in r.flagged:
            delta = r.widths[i] - r.expected  
            flagged_rows.append(
                {"row": i, "label": r.rows[i].label(), "delta": delta}
            )

        findings.append(Finding(
            check_name="check",
            table_index=r.index,
            start=m.start(),
            end=m.end(),
            table_html=m.group(0),
            page_guess=r.page,
            caption=r.name,
            summary=(f"{len(r.flagged)} row(s) with the wrong column count "
                     f"(table expects {r.expected})"),
            details={
                "expected_columns": r.expected,
                "kind": r.kind,
                "flagged_rows": flagged_rows,
            },
        ))
    return findings




CHECKS: List[Callable[[str], List[Finding]]] = [
    check1_adapter,
    # check2_adapter,   # <- future checks plug in here
]



def detect(doc: str) -> List[Finding]:
    """Run every registered check and return one merged, ordered list."""
    findings: List[Finding] = []
    for check_fn in CHECKS:
        findings.extend(check_fn(doc))
    # Stable, human-friendly order: by rough page, then by position in the file.
    findings.sort(key=lambda f: (f.page_guess, f.start))
    return findings


def report(findings: List[Finding]) -> None:
    if not findings:
        print("No problems found.")
        return
    print(f"{len(findings)} finding(s):\n")
    for f in findings:
        print(f'[{f.check_name}] page ~{f.page_guess} — "{f.caption}"')
        print(f"    {f.summary}")
        for r in f.details.get("flagged_rows", []):
            d = r["delta"]
            where = f"missing {-d} col" if d < 0 else f"extra {d} col"
            print(f'      row {r["row"]:<3} {r["label"]}  ({where})')
        print()


def main():
    if len(sys.argv) != 2:
        print("usage: python3 -m Functions.stage1_detect document.md")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8", errors="replace") as fh:
        doc = fh.read()
    report(detect(doc))


if __name__ == "__main__":
    main()
