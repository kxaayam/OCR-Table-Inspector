#!/usr/bin/env python3
"""

  check_name   - which detector flagged it (for the report / debugging).
  table_index  - 0-based position of the table within the document. Lets two
                 different checks that flag the SAME table be recognised as
                 such later (de-duplication).
  start, end   - character offsets of the table block in the document, from
                 '<table' to just past '</table>'. Stage 5 needs these to
                 replace exactly the right span.
  table_html   - the raw table block, verbatim. Used both as the correction
                 target and as raw material for the Stage 2 fingerprint.
  page_guess   - the ROUGH page number from page_locator ('---' counting).
                 A starting hint for Stage 2, not a trusted answer.
  caption      - the nearest title/name preceding the table. The primary
                 fingerprint Stage 2 will search the PDF for.
  summary      - one-line human-readable description of what is wrong.
  details      - structured, check-specific extras (free-form dict), e.g. the
                 expected column count and which rows were off.
                 
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Finding:
    check_name: str
    table_index: int
    start: int
    end: int
    table_html: str
    page_guess: int
    caption: str
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
