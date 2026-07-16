#!/usr/bin/env python3

import re
from typing import List


DIVIDER_RE = re.compile(r"^\s*---\s*$", re.MULTILINE)


def divider_positions(doc: str) -> List[int]:
    return [m.start() for m in DIVIDER_RE.finditer(doc)]


def page_of_position(pos: int, dividers: List[int]) -> int:
    count = 0
    for d in dividers:
        if d < pos:
            count += 1
        else:
            break
    return count + 1