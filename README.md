# OCR Table Correction Pipeline (Under construction 🚧 🧱 ) 
*Developed by Zoe Yu, EngSci 2T9, University of Toronto 


This repository contains a pipeline for detecting and correcting problematic HTML tables in OCR-generated Markdown files.
It identifies suspicious tables, links each to its scanned page image from the U of T Library, and hands only high-risk cases to Claude — running in your Claude Code session — for correction. This reduces unnecessary manual review of historical archive documents.

The pipeline does not call any model server, and there is no PDF input. Python does the deterministic work (detect, locate, fetch page images, splice results back safely); Claude is the vision step that reads each page image and rewrites the table.

## Workflow

```text
OCR Markdown file
      ↓
Stage 0: create working copy
      ↓
Stage 1: detect suspicious tables
      ↓
Stage 2: fetch table's page image from the U of T Library
      ↓
Stage 3: Claude corrects each table from its page image + SKILL.md
      ↓
Corrected working Markdown file
```

## Repository Structure

```text
Functions/               Python package holding the pipeline code
  run_pipeline.py        Run the full pipeline
  stage0_copy.py         Create a working copy of the input Markdown file
  stage1_detect.py       Run table-detection checks
  check.py               Detect uneven/high-risk table structures
  finding.py             Shared Finding object used across stages
  stage2_locate.py       Fetch each table's page image from the library
  page_locator.py        Estimate page numbers using Markdown page dividers
  llm_locator.py         Optional Claude-assisted page locator (confirms the guess)
  stage3_correct.py      Correction handoff: write requests, splice responses back
  correct.py             Resumable batch-correction driver
  fix_table.py           Re-correct a single table on a chosen page
  pipeline_state.py      Read/write state.json + report.txt
  SKILL.md               Table correction instructions Claude follows
working_copies/          Edited copies of input Markdown (originals untouched)
working_pdf/             Fetched page images + state.json / report.txt per run
requirements.txt         Python dependencies (none — standard library only)
requirements-vision.txt  Optional automatic localization dependencies
```

## Setup

Requires only **Python 3 and an internet connection**. There are no third-party
dependencies (page images are fetched over HTTP with the standard library), no
PDF input, and no model server or API key — the correction step is performed by
Claude in your Claude Code session.

Page images come from the U of T Library, e.g.:

```text
https://content.library.utoronto.ca/uoft-presidentsreports/download/<doc_id>/page/n<N>.jpg
```

The `<doc_id>` defaults to the markdown filename stem (e.g.
`presidentsreport1958univ.md` → `presidentsreport1958univ`). Both the
`presidentsreport…` and `uoftreportgov…` document types are served by the same
`uoft-presidentsreports` collection.

## Usage

Run the full pipeline from the repository root (so the `Functions` package is
importable):

```bash
python3 -m Functions.run_pipeline <document.md> [--doc-id ID] [--force]
```

Automatic table-crop localization is optional because its model stack is
large. On Windows, create a dedicated CPU environment and validate all three
model loaders with:

```powershell
.\scripts\setup_vision.ps1
.\.venv-vision\Scripts\python.exe scripts\smoke_vision.py
```

Models are downloaded from their official registries on first use and then
reused from the normal Hugging Face/Paddle caches. Run automatic localization
with `--vision`; change the nearby scan window with `--vision-window N`.

Example:

```bash
python3 -m Functions.run_pipeline presidentsreport1958univ.md
```

This runs Stages 0–2: it makes a working copy, detects the suspect tables,
fetches each table's page image from the library, and writes one correction
*request* per table under `working_pdf/<document>/requests/`. It then stops so
you can review the fetched pages. Pass `--force` to overwrite an existing
working copy. The document id defaults to the markdown stem; override it with
`--doc-id` (and the collection or URL with `--collection` / `--url-template`).

Stage 3 is done by Claude: for each located table, open its `page_nN.jpg`
image, read the matching `requests/table_<idx>.html`, and save the corrected
`<table>` to `responses/table_<idx>.html`. Then splice the corrections into the
working copy with:

```bash
python3 -m Functions.correct <document.md>
```

This is resumable — correct a few tables, run it, correct more, run it again.
To redo a single table on a specific page:

```bash
python3 -m Functions.fix_table <working.md> --table N --page P
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

### Stage 2: Fetch the Table's Page Image

When a suspicious table is found, Stage 2 fetches the corresponding scanned page image from the U of T Library.

The scan index `n` comes from the Markdown page dividers (`---`): the number of dividers before the table gives the page, which is assumed to match the library's scan index directly. The image is downloaded to `working_pdf/<document>/page_nN.jpg` (cached and reused on later runs).

If the page image cannot be fetched (e.g. HTTP 404 or a network error), the table is left for manual review.


### Stage 3: Correct with Claude

Once the page image is fetched, the pipeline prepares everything Claude needs:

- the fetched page image (`page_nN.jpg`)
- the rough OCR table HTML (`requests/table_<idx>.html`)
- `SKILL.md`

Claude reads the page image and rewrites the table, saving only the corrected
`<table>...</table>` markup to `responses/table_<idx>.html`. Running
`python3 -m Functions.correct` then splices each corrected table into the
working Markdown file, verifying the original table is still exactly where it
was recorded before replacing it.

## SKILL.md
`SKILL.md` contains the table-formatting instructions Claude follows.

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
