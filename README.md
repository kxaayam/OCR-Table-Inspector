
# OCR-Table-Inspector

## Scope

This tool was built **specifically for the University of Toronto OCR
digitization project**, for historical UofT documents (roughly 1900–1980)
scanned and converted to HTML tables by that project's pipeline.

It is **not a general-purpose table checker.** It assumes the exact HTML
conventions that project's scanning output uses:

- Tables are written as HTML `<table>` blocks using `<tr>` rows and
  `<td>`/`<th>` cells.
- Multi-tier headers use `colspan` / `rowspan` attributes.
- Pages are separated in the source document by a line containing only `---`.

If your tables come from a different source or use a different format, the
tool will either produce meaningless output or silently miss problems. It has
only been checked against this one project's output, and nothing else is
supported or claimed.

## What it checks

At present the tool runs **one check**:

**Inconsistent row lengths.** Within a single table, every row should resolve
to the same number of columns. The tool computes each row's column count and
flags any row that does not match the table's most common count. In this
project's scans, the most frequent cause of such a mismatch is a table whose
bottom rows were dropped during scanning ("bottom half cut off"), leaving a
short final row — but the check catches any row that is short (or long)
relative to the rest of its table, wherever it occurs.

Two table formats are handled:

- **Simple tables** (no `colspan`/`rowspan`): a row's column count is its
  literal number of `<td>`/`<th>` cells.
- **Spanned tables** (multi-tier headers using `colspan`/`rowspan`): spans are
  expanded — a `colspan="5"` cell counts as five columns, and a `rowspan`
  cell occupies its column in the rows below — so that a correctly-formed
  header is not mistaken for a broken row.

That is the only check. There is no total/arithmetic verification, no
detection of entirely-missing rows, no text-accuracy checking, and no
cross-table comparison. Those are out of scope for this version.

## Output
 
The tool reports **only tables that have problems.** Tables with no problems
are not mentioned at all. For each flagged table it prints:
 
- **Page** — which page the table is on, counted by `---` dividers (content
  before the first divider is page 1).
- **Name** — the nearest text line immediately above the table (typically its
  printed heading), or `(unnamed)` if there is none.
- **Problem(s) found** — each failing check, numbered, with its own details.
Example:
 
```
Page 1 — "The Province of Ontario"
  (1) Problem found: Inconsistent row lengths
      Rows in this table should have 19 columns.
      - Row 7   | Dundas.....     | Missing 10 columns
      - Row 16  | Haliburton..... | Missing 9 columns
      - Row 26  | Lincoln.....    | Missing 3 columns
```
 
The numbered `(1) Problem found: …` structure is deliberate: it leaves room
for additional checks to be added later, so one table can report several
distinct problems at once.

## Usage

Requires Python 3 (standard library only — no dependencies to install).

Both files must sit in the same folder, since tcheckhe detector imports the page
locator:

- `check1.py`
- `page_locator.py`

Run against one or more files:

```bash
python check1.py document.md
python check1.py file1.md file2.md file3.md
python check1.py scans/*.md
```

Save the report to a file for review:

```bash
python check1.py scans/*.md > report.txt
```

## Known limitations

- **Format-specific.** As above — only this project's HTML output is
  supported.
- **Rows missing a closing `</tr>`.** If a row is truncated so severely that
  it loses its `</tr>` tag, it is not parsed and therefore not counted or
  flagged.
- **Markdown in headings.** The table name is taken verbatim from the line
  above the table with HTML tags removed; Markdown formatting (e.g. `**bold**`)
  is left as-is, so such a heading may show its literal markup.
- **Ambiguous small tables.** "Expected column count" is the most common count
  among a table's rows. For a very small table where no count clearly
  dominates, that reference may not be meaningful. 
