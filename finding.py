#!/usr/bin/env python3

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
