"""Find and parse citation spans inside a text container.

Best-effort, conservative heuristics. The guiding principle from the design:
when in doubt, emit the citation and let the matcher/reviewer decide rather than
silently dropping or guessing. We never rewrite the document here.

Handles:
  - author-date parenthetical:  (Smith 2020), (Smith, 2020, p. 14),
                                (Smith & Jones 2019; Doe et al., 2018)
  - author-date narrative:      Smith (2020), Smith et al. (2018)
  - numbered:                   [1], [1, 2], [1-3]   (detected, not matchable)
  - footnote full citations:    a note that reads as a full reference
  - short forms:                ibid., id., supra note 12, op. cit.
"""
from __future__ import annotations

import re
import uuid

from .docx_parser import Container
from .models import Anchor, CitationType, Location, ParsedCitation

YEAR = r"(?:1[6-9]\d{2}|20\d{2})[a-z]?"

# A parenthetical group that contains at least one year.
_PAREN = re.compile(r"\(([^()]*\b" + YEAR + r"\b[^()]*)\)")
# One author-year unit inside a parenthetical group (split on ';' first).
_UNIT = re.compile(
    r"(?P<authors>.*?)[,;\s]+(?P<year>" + YEAR + r")"
    r"(?:[,\s]*(?:pp?\.?|paras?\.?)\s*(?P<pages>[\d–\-,\s]+))?",
    re.DOTALL,
)
# Narrative: Surname [et al. / and Surname / & Surname] (YEAR ...)
_NARRATIVE = re.compile(
    r"(?P<authors>[A-Z][A-Za-z'’\-]+"
    r"(?:\s*(?:,|and|&|et al\.?)\s*[A-Z]?[A-Za-z'’\-]*)*?)"
    r"\s+\((?P<year>" + YEAR + r")"
    r"(?:[,\s]*(?:pp?\.?)\s*(?P<pages>[\d–\-,\s]+))?\)"
)
_NUMBERED = re.compile(r"\[(\d+(?:\s*[,–\-]\s*\d+)*)\]")
_SHORT = re.compile(
    r"\b(ibid\.?|id\.?|op\.?\s*cit\.?|loc\.?\s*cit\.?"
    r"|supra(?:\s+notes?\.?\s*\d+)?)\b",
    re.IGNORECASE,
)
_QUOTED = re.compile(r"[\"“]([^\"”]{3,})[\"”]")


def _new_id() -> str:
    return "c_" + uuid.uuid4().hex[:10]


def parse_surnames(authors: str) -> list[str]:
    """Pull surname tokens out of an author string fragment."""
    s = re.sub(r"\bet al\.?", " ", authors, flags=re.IGNORECASE)
    s = re.sub(r"\b(and)\b", "&", s, flags=re.IGNORECASE)
    names: list[str] = []
    for part in re.split(r"[&,]", s):
        part = part.strip()
        if not part:
            continue
        tok = part.split()[-1]
        if tok and tok[0].isupper() and len(tok) > 1:
            names.append(tok)
    return names


def _mk(raw: str, ctype: CitationType, container: Container,
        start: int, end: int, *, authors=None, year=None,
        title=None, pages=None) -> ParsedCitation:
    return ParsedCitation(
        id=_new_id(),
        raw_text=raw,
        ctype=ctype,
        anchor=Anchor(container.location, container.container_id, start, end),
        authors=authors or [],
        year=year,
        title=title,
        pages=(pages.strip() if pages else None),
    )


def _extract_author_date(container: Container) -> list[ParsedCitation]:
    out: list[ParsedCitation] = []
    text = container.text

    for m in _PAREN.finditer(text):
        group = m.group(1)
        base = m.start(1)
        # Split multi-citation groups on ';' keeping offsets.
        offset = 0
        for chunk in group.split(";"):
            unit = _UNIT.search(chunk)
            if unit:
                surnames = parse_surnames(unit.group("authors"))
                if surnames:
                    cstart = base + offset + (unit.start())
                    cend = base + offset + (unit.end())
                    out.append(_mk(chunk.strip(), CitationType.AUTHOR_DATE,
                                   container, cstart, cend,
                                   authors=surnames, year=unit.group("year"),
                                   pages=unit.group("pages")))
            offset += len(chunk) + 1

    for m in _NARRATIVE.finditer(text):
        surnames = parse_surnames(m.group("authors"))
        if surnames:
            out.append(_mk(m.group(0), CitationType.AUTHOR_DATE, container,
                           m.start(), m.end(), authors=surnames,
                           year=m.group("year"), pages=m.group("pages")))
    return out


def _looks_like_full_citation(text: str) -> bool:
    has_year = re.search(YEAR, text) is not None
    long_enough = len(text) > 30
    has_sep = ("," in text) or ("." in text)
    return has_year and long_enough and has_sep


def _extract_footnote(container: Container) -> list[ParsedCitation]:
    out: list[ParsedCitation] = []
    text = container.text

    # Short forms (ibid./supra/...) — resolved later by shortforms.py.
    for m in _SHORT.finditer(text):
        out.append(_mk(m.group(0), CitationType.SHORT_FORM, container,
                       m.start(), m.end()))

    # Embedded author-date parentheticals within a note.
    out.extend(_extract_author_date(container))

    # Whole-note full citation (only if it isn't merely a short form).
    if _looks_like_full_citation(text) and not _SHORT.match(text.strip()):
        ym = re.search(YEAR, text)
        year = ym.group(0) if ym else None
        # Author guess: text before the first comma.
        head = text.split(",", 1)[0]
        surnames = parse_surnames(head)
        qt = _QUOTED.search(text)
        title = qt.group(1) if qt else None
        # Avoid duplicating an embedded parenthetical we already captured.
        already = any(c.anchor.start == 0 and c.anchor.end == len(text)
                      for c in out)
        if surnames and not already:
            out.append(_mk(text.strip(), CitationType.FOOTNOTE_FULL, container,
                           0, len(text), authors=surnames, year=year,
                           title=title))
    return out


def extract_from_container(container: Container) -> list[ParsedCitation]:
    if container.location is Location.BODY:
        cites = _extract_author_date(container)
        # Numbered citations: detected but not matchable without a ref list.
        for m in _NUMBERED.finditer(container.text):
            cites.append(_mk(m.group(0), CitationType.NUMBERED, container,
                             m.start(), m.end()))
        return cites
    return _extract_footnote(container)


def extract_all(containers: list[Container]) -> list[ParsedCitation]:
    out: list[ParsedCitation] = []
    for c in containers:
        out.extend(extract_from_container(c))
    return out
