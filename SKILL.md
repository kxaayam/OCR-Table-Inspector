---
name: table-formatting
description: "Produce clean, photo-faithful HTML tables built from plain tr and td elements, in either of two modes: CREATE a table from scratch given only an image or scan of a printed table, or UPDATE a rough HTML transcription (OCR output with data-bbox attributes, br-packed cells, misaligned values) to conform to its source image. Applies to tables of any size, shape, or subject, including ledgers, registries, reports, lists, and schedules. Use this skill whenever the user supplies a table image and asks to transcribe, build, conform, clean, fix, decompose, \"remove data boxes\", or restructure the table; whenever data-bbox attributes appear in supplied markup; or whenever multi-line table cells should be split into one row per entry."
---

# Table Formatting

Guidelines for producing clean, minimal HTML tables that conform to a source image. Tables may have any number of rows and columns and any subject matter. The goal is a simple, uniform grid of plain `<tr>` and `<td>` elements whose content and alignment match the print.

There are two modes. Pick the one that matches the input:

- **Create table** — the only input is an image or scan, with no HTML. Transcribe the table directly into clean HTML. See "Create table" below.
- **Update table** — both an image and a rough HTML transcription are supplied. Conform the existing markup to the image. See "Update table" below.

Both modes share the Core operations and Stylization guidelines; only the starting point differs.

## Inputs

1. An image of the printed table. The image is authoritative.
2. An HTML transcription, typically machine-generated, containing artifacts such as `data-bbox` attributes, `<br/>`-packed multi-line cells, ruling rows, semantic wrappers, and misplaced values.

 Report textual corrections (spelling, missing emphasis, wrong values) and any content visible in the image but absent from the markup. Append such missing content when it clearly belongs to the table, and flag the addition so it can be removed if unwanted.

## Core operations

### 1. Remove data boxes and attribute clutter

Strip every `data-bbox` attribute and any other positional, stylistic, or machine-generated attribute (`class`, `style`, `id`, `data-*`). These are transcription artifacts, never content.

### 2. Keep structural wrappers; use consistent cells

Keep the table's structural wrappers: `<thead>` around the header block, `<tbody>` around the body rows, and `<th>` for header cells. Use plain `<tr>` and `<td>` for body rows. Keep a minimal table element such as `<table border="1">` unless the user specifies otherwise.

Use `colspan` and `rowspan` wherever the print shows a single cell covering several columns or rows: multi-tier headers, grouped column bands, braced value spans (Core operation 6), and any label or figure the print physically merges across the grid. Reproduce the printed cell structure faithfully rather than flattening it. For body text that merely runs across the page width without being a true merged cell, the first cell of the row may instead carry the text with empty cells filling the remainder; reserve span attributes for cells the print genuinely merges.

### 3. Decompose multi-line cells

Break `<br/>`-packed cells apart so that each printed line of content becomes its own row, with one logical entry per row. Every row should contain the same number of `<td>` cells as the table has columns, padded with empty `<td></td>` cells. Headings, sub-headers, subtotals, and totals each occupy their own standalone row. When one column carries more lines than its neighbor (e.g., a long list of contributors beside a single fund name), continuation rows leave the exhausted columns empty.

### 4. Merge typographic wraps

A line break in the print that exists only because text exceeded the printed column width is a typographic artifact, not a separate entry. Do NOT split such text across rows. Merge the wrapped continuation into a single cell and place any associated value on the consolidated row. Test: if the second printed line is an indented continuation of a name or phrase rather than a new entry, merge it. Examples: "Ontario Federation of Home and School / Associations Inc."; "American Society of Heating, Refrigerating / &amp; Air-Conditioning Engineers".

### 6. Braces: group spans with rowspan

Old printed tables use a curly brace ( { or } ) to show that one value is shared across several adjacent rows, or that a block of rows is grouped under one label. Reproduce the meaning, not the glyph: do not emit brace characters. Instead, give the shared cell a `rowspan` equal to the number of rows it covers, and let the unshared cells in those rows stay as ordinary `<td>` cells.

Read the brace by its opening and closing:

- Where a brace **opens** (the rows fan out from a single shared value into several distinct ones), the shared column collapses to one `rowspan` cell and the differing columns expand to one cell per row.
- Where a brace **closes** (several distinct rows converge onto a single shared value), that column collapses to one `rowspan` cell covering those rows. A faint or lightly printed brace at the very start of a group still counts; treat it the same as a clear one.
- A column may be braced over one span while a neighbouring column is braced over a different span in the same block. Resolve each column independently: nest or stagger the `rowspan` values so each shared value covers exactly the rows the brace touches. For example, in a five-row group one column may span all five rows, another may split into a 2-row span plus a 3-row span, and a third may carry a separate value on every row.
- When a row's leading columns are absorbed by a `rowspan` from above, that row emits fewer `<td>` cells; its explicit cells begin at the first non-spanned column. This is correct and expected.


### 7. Align values to the image

Each value belongs on the row of the entry it is printed beside, in the column where it is printed. When a value sits beside the second line of a wrapped name, it belongs to that single merged entry. Subtotal and total rows carry only their value cells, with other cells empty. Captions for totals are placed in whichever column the print shows them.


### 8. Stylization guidelines

- Inline emphasis mirrors the print and nothing else: `<b>` only where the print is bold, `<i>` only where italic, `<u>` only where the text itself is genuinely underlined.
- A subtotal or total row is its own ordinary row, with each total in its column and the other cells empty. Mirror the print's emphasis on that row (for example, bold figures if the print is bold). Do not represent a printed rule with `<hr/>` elements, ruling-only rows, or `<u>`.
- Preserve printed currency symbols, spacing conventions, and punctuation as shown.
- Escape ampersands as `&amp;`.
- Do not add CSS, alignment attributes, or any decoration absent from the user's instructions.

### 9. Dots: leaders and placeholders

Old printed tables use two kinds of dots, both typographic. Always render them by default so the output matches the print; follow any contrary user instruction (such as a request to drop them) where given:

- **Leader dots** trail a row label to guide the eye toward its values ("Anthropology............"). The printed count varies line to line only because it fills to a fixed column edge; it carries no information. Default: append a uniform short run of five dots to the label cell (`Anthropology.....`) rather than reproducing the variable printed counts. Never let a leader run merge a label with the next column.
- **Placeholder dots** (commonly `..`) fill a cell that has no value, marking the absence of a figure. Default: place the literal `..` in every otherwise-empty data cell. Header cells and total cells are not placeholders; do not add dots to them.

These two are independent: an instruction about one (e.g., to drop leaders) does not change the handling of the other. Apply each according to its own default unless told otherwise.

## Create table

Input is an image only. Build the HTML directly from it.

1. Identify the grid: count the columns and read every column header, including rotated or stacked headers. Read multi-word headers in full (e.g., "M.Sc. (Dent.)", "Grad. Stud.").
2. Build the header from the image's tier structure, inside `<thead>` and using `<th>` cells. A single printed header line becomes one row of `<th>` cells, one per column. Where the print stacks headers in tiers — a band label printed above the sub-columns it covers — emit one `<tr>` per tier: give each band-label cell a `colspan` equal to the number of sub-columns beneath it, give each sub-column cell its own cell on the lower tier, and give any cell that occupies the full header height (such as a leading "Courses" column or a trailing "Totals" column) a `rowspan` equal to the number of tiers. Read and include every label from every tier; omit none.
3. Read the body row by row. For each printed row, record the label and the value sitting under each column. Treat a blank or placeholder-dot cell as no value.
4. Emit one `<tr>` per printed row with exactly the column count of `<td>` cells, padding absent values with empty cells. Apply the dots, wrap-merging, stylization, and alignment rules from Core operations.
5. For a totals or summary row, place each printed total in its column on its own ordinary row, mirroring the print's emphasis (for example, bold) but without `<u>` or a rule row; place its caption in the column where it is printed.
6. Verify before delivering: every row resolves to the same total column count once `colspan` and `rowspan` are accounted for (simulate the grid where spans are present), headers are complete across all tiers, and every transcribed figure matches the image. For numeric tables, cross-foot the body against any printed totals row; if a column sum disagrees with the printed total, report the discrepancy and name the rows whose faint or ambiguous digits most likely explain it. Do not silently alter either the body or the printed totals to force agreement.
8. Deliver as an .html file. Report the row count and any verification findings.

## Update table

Inputs are an image and a rough HTML transcription. Conform the markup to the image.

1. Read the image line by line; map each printed line to its column values.
2. Strip `data-bbox` and other machine-generated attribute clutter from the supplied HTML. Keep the structural wrappers `<thead>`, `<tbody>`, and `<th>`, and keep `colspan`/`rowspan` where the print genuinely merges cells.
3. Merge typographic wraps into single logical entries.
4. Emit one row per logical entry, heading, subtotal, and total, in printed order, with a uniform cell count, correcting any values the transcription placed in the wrong row or column.
5. Verify: no `data-bbox` or other clutter remains, no unintended `<br/>` or ruling rows, cell counts are uniform, and every value matches the image in both content and placement.
7. Deliver as an .html file. Report the row count, corrections made against the supplied markup, and any content appended from the image.

## Adaptation

These are defaults, not absolutes. Follow the user's explicit instructions where they differ: they may want headers preserved, `colspan` retained, rule rows kept, or a different decomposition granularity. Earlier instructions in a conversation (e.g., "no horizontal-rule rows") persist for later tables in the same conversation unless countermanded.

## Worked example: update table

Supplied fragment (four-column ledger; the same operations apply to any column count):

```html
<tr>
<td data-bbox="351 681 411 917"><i>School of Library Science</i><br/>Anne Hume Bursary</td>
<td data-bbox="366 241 466 511">Zonta Club of Windsor<br/>Ontario Federation of Home and School<br/>Associations Inc.</td>
<td></td>
<td data-bbox="366 46 466 101">$ 150.00<br/>250.00</td>
</tr>
<tr><td></td><td></td><td><hr/></td><td></td></tr>
```

Correct output:

```html
<tr>
<td><i>School of Library Science</i></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr>
<td>Anne Hume Bursary</td>
<td>Zonta Club of Windsor</td>
<td></td>
<td>$ 150.00</td>
</tr>
<tr>
<td>Ontario Home and School Federation Bursary Fund</td>
<td>Ontario Federation of Home and School Associations Inc.</td>
<td></td>
<td>250.00</td>
</tr>
<tr>
<td></td>
<td></td>
<td></td>
<td>$ 400.00</td>
</tr>
```

Note the merged wrapped name, the standalone italic header row, the value on the consolidated row, the subtotal on its own row (no rule row, no `<u>`), and the uniform cell structure.

## Worked example: create table from image

A wide enrolment matrix: a "Department" label column, many narrow degree-count columns with stacked headers, and a final "Totals" row that rules beneath each figure. In the print, each department name trails leader dots to its row of counts, and every empty count cell is filled with `..`.

Default rendering (leaders normalized to five dots on each label, `..` in empty data cells, headers and totals left clean):

```html
<thead>
<tr>
<th>Department</th>
<th>Ph.D.</th>
<th>M.A.</th>
<th>M.S.</th>
<th>Grad. Stud.</th>
</tr>
</thead>
<tbody>
<tr>
<td>Botany.....</td>
<td>15</td>
<td>1</td>
<td>..</td>
<td>1</td>
</tr>
<tr>
<td>Totals</td>
<td>133</td>
<td>138</td>
<td>5</td>
<td>97</td>
</tr>
</tbody>
```

If the user instead asks to drop the dots, the label loses its leaders and empty cells become truly empty:

```html
<tr>
<td>Botany</td>
<td>15</td>
<td>1</td>
<td></td>
<td>1</td>
</tr>
```

Each row carries the full column count whether or not the cells hold figures; the totals sit on their own row without `<u>` or a rule row; and the body should be cross-footed against the totals row, reporting any column that fails to reconcile rather than adjusting digits to match.

## Worked example: multi-tier header

An enrolment matrix bands its columns under four year-group labels, each printed above four sub-columns (U C, V C, T C, M C), with a "Courses" label column on the left and a "Totals" column on the right that each rise the full header height. The header occupies two printed tiers and resolves to eighteen columns.

```html
<thead>
<tr>
<th rowspan="2">Courses</th>
<th colspan="4">First Year</th>
<th colspan="4">Second Year</th>
<th colspan="4">Third Year</th>
<th colspan="4">Fourth Year</th>
<th rowspan="2">Totals</th>
</tr>
<tr>
<th>U C</th><th>V C</th><th>T C</th><th>M C</th>
<th>U C</th><th>V C</th><th>T C</th><th>M C</th>
<th>U C</th><th>V C</th><th>T C</th><th>M C</th>
<th>U C</th><th>V C</th><th>T C</th><th>M C</th>
</tr>
</thead>
```

The first tier carries "Courses" and "Totals" with `rowspan="2"` plus four band labels with `colspan="4"`; the second tier carries the sixteen sub-column labels. Counting the two `rowspan` cells carried down plus the sixteen sub-column cells, the second tier resolves to eighteen slots, matching the first. Body rows below each emit eighteen `<td>` cells.

## Worked example: braces handled with rowspan

A group of five course rows (Div. I, II, III, Special Radio, IV) sits under a left brace that shares one block of early-column values, while inner braces in later columns share values across smaller sub-spans. No brace glyphs appear in the output; the spans carry the meaning.

```html
<tr>
<td>Div. I.....</td>
<td rowspan="5">28</td><td rowspan="5">15</td>
<td rowspan="2">6</td><td rowspan="2">5</td>
<td>1</td><td>..</td>
<td rowspan="5">108</td>
</tr>
<tr>
<td>Div. II.....</td>
<td>1</td><td>1</td>
</tr>
<tr>
<td>Div. III.....</td>
<td rowspan="3">2</td><td rowspan="3">3</td>
<td>2</td><td>2</td>
</tr>
<tr>
<td>Special Radio.....</td>
<td>1</td><td>1</td>
</tr>
<tr>
<td>Div. IV.....</td>
<td>1</td><td>..</td>
</tr>
```

The first two columns span all five rows (one shared value). The next pair splits into a 2-row span (Div. I–II) and a 3-row span (Div. III, Special Radio, IV). The final pair carries a distinct value on every row. The Totals column spans all five. Rows two through five emit fewer `<td>` cells because the spans above occupy their leading columns; every row still resolves to the same total width, which should be verified by simulating the grid.