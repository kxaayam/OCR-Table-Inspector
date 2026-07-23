"""Deterministic OCR/content matching for automatic table localization."""

from collections import Counter
from dataclasses import dataclass
from html import unescape
import re
import unicodedata
from typing import Dict, Iterable, List, Optional, Sequence

TAG_RE = re.compile(r"<[^>]*>", re.S)
TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)
NUMBER_RE = re.compile(
    r"(?<![\w])[-+−]?(?:\d{1,3}(?:[,\s]\d{3})+|\d+)(?:\.\d+)?%?(?![\w])")


def visible_text(html: str) -> str:
    return unescape(TAG_RE.sub(" ", html or ""))


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", unescape(text or ""))
    return " ".join(text.casefold().replace("−", "-").split())


def lexical_tokens(text: str) -> List[str]:
    return TOKEN_RE.findall(normalize_text(text))


def numeric_tokens(text: str) -> List[str]:
    out = []
    for match in NUMBER_RE.finditer(normalize_text(text)):
        token = re.sub(r"[,\s]", "", match.group(0))
        out.append(token)
    return out


def multiset_f1(target: Iterable[str], observed: Iterable[str]) -> Optional[float]:
    target_counts, observed_counts = Counter(target), Counter(observed)
    if not target_counts or not observed_counts:
        return None
    overlap = sum((target_counts & observed_counts).values())
    precision = overlap / sum(observed_counts.values())
    recall = overlap / sum(target_counts.values())
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (
        precision + recall)


@dataclass(frozen=True)
class CandidateText:
    candidate_id: str
    text: str


def _unique_winner(scores: Dict[str, Optional[float]]) -> Optional[str]:
    usable = {key: value for key, value in scores.items() if value is not None}
    if not usable:
        return None
    best = max(usable.values())
    winners = [key for key, value in usable.items() if value == best]
    return winners[0] if len(winners) == 1 else None


def rank_candidates(table_html: str,
                    candidates: Sequence[CandidateText]) -> dict:
    target = normalize_text(visible_text(table_html))
    target_lexical = lexical_tokens(target)
    target_numeric = numeric_tokens(target)
    lexical, numeric = {}, {}
    for candidate in candidates:
        normalized = normalize_text(candidate.text)
        lexical[candidate.candidate_id] = multiset_f1(
            target_lexical, lexical_tokens(normalized))
        numeric[candidate.candidate_id] = multiset_f1(
            target_numeric, numeric_tokens(normalized))
    lexical_winner = _unique_winner(lexical)
    numeric_winner = (
        _unique_winner(numeric) if target_numeric else None
    )
    accepted = (
        lexical_winner is not None
        and lexical_winner == numeric_winner
    )
    return {
        "lexical_scores": lexical,
        "numeric_scores": numeric,
        "lexical_winner": lexical_winner,
        "numeric_winner": numeric_winner,
        "agreement": accepted,
        "status": "accepted" if accepted else "unresolved",
        "selected": lexical_winner if accepted else None,
        "target_has_numeric_evidence": bool(target_numeric),
    }
