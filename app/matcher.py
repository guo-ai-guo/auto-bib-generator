"""Match parsed citations against a Zotero library (CSL-JSON).

Design priority: precision over recall. Auto-inclusion only fires when there is
*exactly one* strong candidate, so anything the auto path adds should be
trustworthy. Everything else is pushed to the review queue (AMBIGUOUS) or flagged
(NONE) rather than guessed.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Optional

from .models import (Candidate, CitationType, MatchResult, MatchStatus,
                     ParsedCitation)

FLOOR = 0.45        # below this a candidate is discarded (not shown at all)
CONFIDENT = 0.85    # a candidate at/above this is a "confident match"
MAX_CANDIDATES = 5
_STOP = {"the", "a", "an", "of", "and", "in", "on", "for", "to", "with"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _norm(s)) if t not in _STOP and len(t) > 2}


def _item_surnames(item: dict[str, Any]) -> list[str]:
    out = []
    for a in item.get("author", []):
        fam = a.get("family") or a.get("literal")
        if fam:
            out.append(_norm(fam))
    return out


def _item_year(item: dict[str, Any]) -> Optional[str]:
    issued = item.get("issued") or {}
    parts = issued.get("date-parts") or []
    if parts and parts[0]:
        return str(parts[0][0])
    raw = issued.get("raw")
    if raw:
        m = re.search(r"\d{4}", str(raw))
        if m:
            return m.group(0)
    return None


def _bare_year(y: Optional[str]) -> Optional[str]:
    if not y:
        return None
    m = re.match(r"(\d{4})", y)
    return m.group(1) if m else None


def _name_match(cite_name: str, item_names: list[str]) -> float:
    c = _norm(cite_name)
    best = 0.0
    for n in item_names:
        if c == n:
            return 1.0
        r = SequenceMatcher(None, c, n).ratio()
        best = max(best, r)
    return best if best >= 0.85 else 0.0


def _display(item: dict[str, Any]) -> str:
    surnames = [a.get("family") or a.get("literal") or "" for a in item.get("author", [])]
    if not surnames:
        who = item.get("title", "Untitled")[:40]
    elif len(surnames) == 1:
        who = surnames[0]
    elif len(surnames) == 2:
        who = f"{surnames[0]} & {surnames[1]}"
    else:
        who = f"{surnames[0]} et al."
    year = _item_year(item) or "n.d."
    title = (item.get("title") or "").strip()
    title = (title[:60] + "…") if len(title) > 60 else title
    return f"{who} ({year}) — {title}".strip(" —")


class LibraryIndex:
    """Searchable index over CSL-JSON items, keyed by (surname, year)."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self._by_key: dict[tuple[str, str], list[dict]] = {}
        self._by_surname: dict[str, list[dict]] = {}
        for it in items:
            year = _bare_year(_item_year(it))
            for sn in _item_surnames(it):
                self._by_surname.setdefault(sn, []).append(it)
                if year:
                    self._by_key.setdefault((sn, year), []).append(it)

    def item_key(self, item: dict[str, Any]) -> str:
        return str(item.get("id") or item.get("key") or id(item))

    def candidates_for(self, cite: ParsedCitation) -> list[dict[str, Any]]:
        """Generate a candidate pool via the surname/year index."""
        pool: dict[str, dict] = {}
        cite_year = _bare_year(cite.year)
        for surname in cite.authors:
            sn = _norm(surname)
            keys = [sn]
            # tolerate small surname typos against indexed names
            for known in self._by_surname:
                if known != sn and SequenceMatcher(None, sn, known).ratio() >= 0.9:
                    keys.append(known)
            for k in keys:
                if cite_year and (k, cite_year) in self._by_key:
                    for it in self._by_key[(k, cite_year)]:
                        pool[self.item_key(it)] = it
                for it in self._by_surname.get(k, []):
                    pool[self.item_key(it)] = it
        return list(pool.values())


def _score(cite: ParsedCitation, item: dict[str, Any]) -> float:
    item_names = _item_surnames(item)
    if not cite.authors:
        return 0.0
    author_score = sum(_name_match(a, item_names) for a in cite.authors) / len(cite.authors)

    cite_year = _bare_year(cite.year)
    item_year = _bare_year(_item_year(item))
    if cite_year and item_year:
        year_score = 1.0 if cite_year == item_year else 0.0
    else:
        year_score = 0.5  # unknown on one side -> neutral

    if cite.title and item.get("title"):
        ct, it_ = _tokens(cite.title), _tokens(item["title"])
        union = ct | it_
        title_score = (len(ct & it_) / len(union)) if union else 0.0
        return 0.45 * author_score + 0.25 * year_score + 0.30 * title_score
    return 0.60 * author_score + 0.40 * year_score


def match_citation(cite: ParsedCitation, index: LibraryIndex) -> MatchResult:
    # Citation types that carry no matchable bibliographic signal.
    if cite.ctype is CitationType.NUMBERED or not cite.authors:
        return MatchResult(cite.id, MatchStatus.NONE)

    scored: list[Candidate] = []
    for item in index.candidates_for(cite):
        s = _score(cite, item)
        if s >= FLOOR:
            scored.append(Candidate(index.item_key(item), s, item, _display(item)))
    scored.sort(key=lambda c: c.score, reverse=True)

    if not scored:
        return MatchResult(cite.id, MatchStatus.NONE)

    # The agreed rule: exactly one confident match -> auto-include; zero,
    # multiple, or only weak candidates -> the user confirms in review.
    confident = [c for c in scored if c.score >= CONFIDENT]
    if len(confident) == 1:
        top = confident[0]
        return MatchResult(cite.id, MatchStatus.CONFIDENT, [top], top.item_key)

    return MatchResult(cite.id, MatchStatus.AMBIGUOUS, scored[:MAX_CANDIDATES])


def match_all(citations: list[ParsedCitation],
              items: list[dict[str, Any]]) -> tuple[dict[str, MatchResult], LibraryIndex]:
    index = LibraryIndex(items)
    results = {c.id: match_citation(c, index) for c in citations}
    return results, index
