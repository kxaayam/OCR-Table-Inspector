# OCR Table Correction Pipeline (Under construction 🚧 🧱 ) 

This repository contains a pipeline for detecting and correcting problematic HTML tables in OCR-generated Markdown files.

It identifies suspicious tables, links them to the corresponding PDF page, and sends only high-risk cases to a local vision LLM for correction. This reduces unnecessary manual review of historical archive documents.

## Workflow

```text
OCR Markdown file
      ↓
Stage 0: create working copy
      ↓
Stage 1: detect suspicious tables
      ↓
Stage 2: locate table page in source PDF
      ↓
Stage 3: correct table using local vision LLM + SKILL.md
      ↓
Corrected working Markdown file
```

## Repository Structure

```text
run_pipeline.py      Run the full pipeline
stage0_copy.py       Create a working copy of the input Markdown file
stage1_detect.py     Run table-detection checks
check.py             Detect uneven/high-risk table structures
finding.py           Shared Finding object used across stages
stage2_locate.py     Locate suspicious tables in the source PDF
page_locator.py      Estimate page numbers using Markdown page dividers
stage3_correct.py    Send located tables to the local vision LLM
SKILL.md             Table correction instructions for the LLM
```

## Usage

Run the full pipeline with:

```bash
python3 run_pipeline.py <document.md> <source.pdf>
```

Example:

```bash
python3 run_pipeline.py report_original.md report.pdf
```

## Stage

### Stage 0: Create Working Copy

The original OCR Markdown file is never edited directly. The pipeline will first creates a working copy, and all later changes are applied to that copy. 

### Stage 1: Detect Suspicious Tables

Stage 1 scans the Markdown file for HTML <table> blocks and checks for structural issues. Its main check flags uneven row widths while distinguishing harmless section rows from likely OCR errors.

**Low-risk examples:**
```text
First Year
Second Year
Faculty of Arts
Totals
```

**High-risk exmaples:**
```text
..112
.. 56
. 19
```

### Stage 2: Locate Table in PDF

When a suspicious table is found, Stage 2 tries to locate the corresponding page in the source PDF.

It uses:
- the approximate page position from Markdown page dividers '---' 
- nearby captions or headings
- distinctive row labels from the table

If the page cannot be located confidently, the table is left for manual review.


### Stage 3: Correct with Local Vision LLM

Once the page is located, Stage 3 sends the following to the local vision LLM:

- the rendered page image
- the rough OCR table HTML
- `SKILL.md`

The model is asked to return only the corrected `<table>...</table>` markup. The corrected table is then written into the working Markdown file.

## SKILL.md
`SKILL.md` contains the table-formatting instructions used by the LLM.

It gives rules for:
- cleaning OCR-generated HTML
- preserving table structure
- handling headers and body rows
- separating leader dots from placeholder dots
- correcting merged or shifted table cells
- producing clean HTML table output

## Next Steps
Planned next steps:
- test on more real OCR archive files
- add post-correction validation
- improve logging and summary reports
- collect more examples of OCR table failures
- add additional checks for other high-risk table errors
