#!/usr/bin/env python3

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from page_locator import divider_positions, page_of_position

TABLE_RE = re.compile(r"<table\b.*?</table>", re.S | re.I)
ROW_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
CELL_RE = re.compile(r"<(t[dh])\b([^>]*)>(.*?)</\1>", re.S | re.I)
COLSPAN_RE = re.compile(r'colspan\s*=\s*["\']?(\d+)["\']?', re.I)
ROWSPAN_RE = re.compile(r'rowspan\s*=\s*["\']?(\d+)["\']?', re.I)


DOT_VALUE_RE = re.compile(r"^\s*\.{1,}\s*\d")

DOT_ONLY_RE = re.compile(r"^\s*\.{1,}\s*$")


@dataclass
class Cell:
    tag: str
    colspan: int
    rowspan: int
    text: str

    def plain(self) -> str:
        text = re.sub(r"<[^>]+>", " ", self.text)
        text = re.sub(r"&nbsp;", " ", text, flags=re.I)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


@dataclass
class Row:
    cells: List[Cell]

    @property
    def literal_count(self) -> int:
        return len(self.cells)

    @property
    def is_header(self) -> bool:
        return any(c.tag == "th" for c in self.cells)

    def label(self) -> str:
        if not self.cells:
            return "(empty row)"
        return self.cells[0].plain() or "(blank first cell)"


@dataclass
class RowIssue:
    row: int
    kind: str
    trigger_llm: bool
    reason: str


@dataclass
class TableResult:
    index: int
    kind: str
    expected: int
    widths: List[int]
    rows: List[Row]
    page: int = 1
    name: str = "(unnamed)"
    flagged: List[int] = field(default_factory=list)
    strict_majority: bool = True

    ignored: List[int] = field(default_factory=list)
    issues: Dict[int, RowIssue] = field(default_factory=dict)


def parse_table(table_html: str) -> List[Row]:
    rows: List[Row] = []

    for row_body in ROW_RE.findall(table_html):
        cells: List[Cell] = []

        for tag, attrs, text in CELL_RE.findall(row_body):
            colspan_match = COLSPAN_RE.search(attrs)
            rowspan_match = ROWSPAN_RE.search(attrs)

            colspan = int(colspan_match.group(1)) if colspan_match else 1
            rowspan = int(rowspan_match.group(1)) if rowspan_match else 1

            cells.append(Cell(
                tag=tag.lower(),
                colspan=max(colspan, 1),
                rowspan=max(rowspan, 1),
                text=text,
            ))

        rows.append(Row(cells=cells))

    return rows


def table_name(doc: str, table_start: int) -> str:
    before = doc[:table_start]

    for raw_line in reversed(before.splitlines()):
        line = re.sub(r"<[^>]+>", " ", raw_line)
        line = re.sub(r"\s+", " ", line).strip()

        if not line:
            continue
        if re.fullmatch(r"-{3,}", line):
            continue

        return line

    return "(unnamed)"


def classify(rows: List[Row]) -> str:
    for row in rows:
        for cell in row.cells:
            if cell.colspan != 1 or cell.rowspan != 1:
                return "spanned"
    return "simple"


def simple_widths(rows: List[Row]) -> List[int]:
    return [row.literal_count for row in rows]


def spanned_widths(rows: List[Row]) -> List[int]:
    carried = Counter()
    widths: List[int] = []

    for i, row in enumerate(rows):
        width = carried[i]

        for cell in row.cells:
            width += cell.colspan

            if cell.rowspan > 1:
                for k in range(1, cell.rowspan):
                    carried[i + k] += cell.colspan

        widths.append(width)

    return widths


def infer_expected_width(rows: List[Row], widths: List[int]) -> int:
    header_widths = [
        width for row, width in zip(rows, widths)
        if row.is_header and width > 0
    ]

    if header_widths:
        return max(header_widths)

    positive_widths = [w for w in widths if w > 0]
    if not positive_widths:
        return 0

    counts = Counter(positive_widths)
    mode, _ = counts.most_common(1)[0]

    max_width = max(positive_widths)

    short_dot_merge_rows = 0
    for row, width in zip(rows, widths):
        if width == max_width - 1 and has_merged_dot_value(row):
            short_dot_merge_rows += 1

    if max_width == mode + 1 and short_dot_merge_rows >= 3:
        return max_width

    return mode


def clean_cell_texts(row: Row) -> List[str]:
    return [cell.plain() for cell in row.cells]


def is_blank_or_dot(text: str) -> bool:
    text = text.strip()
    return text == "" or DOT_ONLY_RE.fullmatch(text) is not None


def contains_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def has_merged_dot_value(row: Row) -> bool:
    for text in clean_cell_texts(row)[1:]:
        if DOT_VALUE_RE.search(text):
            return True
    return False


def count_numeric_cells(row: Row) -> int:
    return sum(1 for text in clean_cell_texts(row)[1:] if contains_digit(text))


def looks_like_sparse_section_row(
    row: Row,
    row_index: int,
    rows: List[Row],
    widths: List[int],
    expected: int,
) -> bool:
    width = widths[row_index]

    if expected <= 0:
        return False

    if width > 2:
        return False

    if not row.cells:
        return True

    texts = clean_cell_texts(row)
    first = texts[0] if texts else ""

    if not first:
        return True

    if has_merged_dot_value(row):
        return False

    
    if any(not is_blank_or_dot(t) for t in texts[1:]):
        return False

    
    if contains_digit(first):
        return False

    
    if len(first) > 80:
        return False

    nearby = []
    for j in (row_index - 2, row_index - 1, row_index + 1, row_index + 2):
        if 0 <= j < len(widths):
            nearby.append(widths[j])

    return expected in nearby


def classify_mismatch(
    row_index: int,
    row: Row,
    rows: List[Row],
    widths: List[int],
    expected: int,
) -> Optional[RowIssue]:
    width = widths[row_index]

    if width == expected:
        return None

    if width == 0:
        return RowIssue(
            row=row_index,
            kind="empty_row",
            trigger_llm=False,
            reason="empty row; not enough evidence of table damage",
        )

    if looks_like_sparse_section_row(row, row_index, rows, widths, expected):
        return RowIssue(
            row=row_index,
            kind="benign_section_row",
            trigger_llm=False,
            reason="short textual row near normal-width rows; likely a section/divider row",
        )

    if width < expected and has_merged_dot_value(row):
        return RowIssue(
            row=row_index,
            kind="merged_placeholder_value",
            trigger_llm=True,
            reason="cell appears to merge placeholder dots with a numeric value",
        )

    if width < expected and count_numeric_cells(row) > 0:
        return RowIssue(
            row=row_index,
            kind="short_data_row",
            trigger_llm=True,
            reason="data row is shorter than expected and still contains numeric values",
        )

    if width > expected:
        return RowIssue(
            row=row_index,
            kind="extra_cells",
            trigger_llm=True,
            reason="row is wider than expected; OCR may have split cells incorrectly",
        )

    return RowIssue(
        row=row_index,
        kind="unclear_mismatch",
        trigger_llm=False,
        reason="width mismatch exists, but not strong enough to spend a local LLM call",
    )


def check_table(index: int, table_html: str, page: int, name: str) -> TableResult:
    rows = parse_table(table_html)
    kind = classify(rows)

    widths = spanned_widths(rows) if kind == "spanned" else simple_widths(rows)
    expected = infer_expected_width(rows, widths)

    counts = Counter(w for w in widths if w > 0)
    top = counts.get(expected, 0)
    strict_majority = top > len(widths) / 2 if widths else False

    flagged: List[int] = []
    ignored: List[int] = []
    issues: Dict[int, RowIssue] = {}

    for i, row in enumerate(rows):
        issue = classify_mismatch(i, row, rows, widths, expected)

        if issue is None:
            continue

        issues[i] = issue

        if issue.trigger_llm:
            flagged.append(i)
        else:
            ignored.append(i)

    return TableResult(
        index=index,
        kind=kind,
        expected=expected,
        widths=widths,
        rows=rows,
        page=page,
        name=name,
        flagged=flagged,
        ignored=ignored,
        issues=issues,
        strict_majority=strict_majority,
    )


def inspect_document(doc: str) -> List[TableResult]:
    dividers = divider_positions(doc)
    results: List[TableResult] = []

    for i, match in enumerate(TABLE_RE.finditer(doc)):
        start = match.start()
        page = page_of_position(start, dividers)
        name = table_name(doc, start)

        results.append(check_table(
            index=i,
            table_html=match.group(0),
            page=page,
            name=name,
        ))

    return results


def report(results: List[TableResult]) -> None:
    for result in results:
        if not result.flagged:
            continue

        print(f'\nPage {result.page} — "{result.name}"')
        print("  (1) Problem found: likely OCR table-width damage")
        print(f"      Expected resolved width: {result.expected}")

        for i in result.flagged:
            issue = result.issues[i]
            diff = result.widths[i] - result.expected

            if diff < 0:
                detail = f"missing {-diff} column(s)"
            else:
                detail = f"extra {diff} column(s)"

            print(
                f"      - Row {i:<3} | {result.rows[i].label()} | "
                f"{detail}; {issue.kind}: {issue.reason}"
            )

        if result.ignored:
            print("      Ignored mismatches:")
            for i in result.ignored:
                issue = result.issues[i]
                print(
                    f"        - Row {i:<3} | {result.rows[i].label()} | "
                    f"{issue.kind}"
                )


def main():
    if len(sys.argv) != 2:
        print("usage: python check.py document.md")
        sys.exit(1)

    path = sys.argv[1]

    with open(path, encoding="utf-8", errors="replace") as fh:
        doc = fh.read()

    report(inspect_document(doc))


if __name__ == "__main__":
    main()
