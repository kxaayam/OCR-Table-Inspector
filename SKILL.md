# Table Formatting

Convert a printed table in an image or scan into clean, minimal HTML.

The image is authoritative. Preserve visible text, numbers, punctuation, emphasis, and the logical table structure. Do not invent unreadable content or change values to make totals agree.

## Output

By default, return only one fenced `html` code block containing a minimal `<table border="1">`.

Use:

* `<thead>` for header rows
* `<tbody>` for body rows
* `<tr>`, `<th>`, and `<td>`
* `rowspan` and `colspan` only when the source visibly shows a real merged cell

Do not add CSS, classes, captions, alignment attributes, comments, explanations, or notes unless the user explicitly asks.

## Structure

Before writing HTML, determine:

* the logical number of columns
* all header rows and header tiers
* genuine merged cells
* body rows, totals, subtotals, grouping marks, and continuation rows
* whether line breaks are real separate entries or only typographic wrapping

Every row must resolve to the same logical column count after `rowspan` and `colspan` are considered.

## Headers

Preserve the printed header hierarchy.

If a header spans multiple subcolumns, use `colspan`.
If a header spans the full header height, use `rowspan`.
Do not omit upper-tier or lower-tier header labels.

## Body rows

Use `rowspan` and `colspan` only for genuine merged cells.

Do not use `colspan` merely because text visually extends across empty space. Put the text in its logical column and use ordinary empty cells for the rest.

If one printed cell contains several distinct logical entries, split them into separate HTML rows. Put shared labels only where they appear, unless the source clearly shows a merged cell.

If a line break is caused only by narrow column width, merge the wrapped text into one cell.

## Braces and grouping marks

If a printed brace clearly shows that one value or label applies to several rows, represent that meaning with `rowspan`. Do not output the brace character itself.

Resolve overlapping groupings column by column.

## Values

Place each value:

* beside the entry it belongs to
* under the correct header
* on the consolidated row if the label was only typographically wrapped

Do not shift values up or down to make rows look fuller.

## Totals and subtotals

Represent totals and subtotals as ordinary body rows. Put captions and values in their printed columns. Preserve visible bold or italic emphasis. Do not use `<hr>` or `<u>` to imitate printed rules.

## Dots

Leader dots after row labels should be preserved by default and normalized to five periods, attached only to the label, for example `Anthropology.....`.

Placeholder dots such as `..` should be preserved only where visibly printed as missing-value markers. Do not insert placeholder dots into headers or cells omitted because of `rowspan`/`colspan`.

If the user asks to remove dots, remove leader dots and use empty cells for placeholder dots.

## Unreadable content

If a cell cannot be read confidently, do not guess. Use an empty cell.

## HTML escaping

Escape HTML-sensitive characters:

* `&` as `&amp;`
* `<` as `&lt;`
* `>` as `&gt;`

## Final check

Before returning, silently verify that:

* all rows resolve to the same logical column count
* headers, body entries, totals, and subtotals are included
* values are under the correct headers
* wrapped text has not been split into false rows
* separate entries have not been incorrectly merged
* printed numbers and punctuation have not been altered
