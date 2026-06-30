"""Resolve short-form citations (ibid., id., supra note N, op. cit.).

Short forms only make sense in sequence, so we walk the note citations in
footnote/endnote order and carry forward the most recent "full" citation. A
resolved short form inherits the structured fields (authors/year/title) of its
target so the matcher can treat it like the real thing, and records
`resolved_from` so the UI can explain the link.

This is intentionally conservative: legal (Bluebook) conventions get arbitrarily
hairy, so anything we cannot resolve with confidence is left unresolved and will
surface in the review queue rather than being mis-attributed.
"""
from __future__ import annotations

import re
from typing import Optional

from .models import CitationType, Location, ParsedCitation

_SUPRA_NOTE = re.compile(r"supra\s+notes?\.?\s*(\d+)", re.IGNORECASE)
_IBID = re.compile(r"\b(ibid|id)\b", re.IGNORECASE)


def _is_full(c: ParsedCitation) -> bool:
    return c.ctype in (CitationType.FOOTNOTE_FULL, CitationType.AUTHOR_DATE) \
        and bool(c.authors)


def _copy_fields(short: ParsedCitation, target: ParsedCitation) -> None:
    short.resolved_from = target.id
    short.authors = list(target.authors)
    short.year = target.year
    short.title = target.title


def resolve(citations: list[ParsedCitation]) -> list[ParsedCitation]:
    """Mutate SHORT_FORM citations in `citations` in place; return the list."""
    # Only note citations participate in short-form chains.
    note_cites = [c for c in citations
                  if c.anchor.location in (Location.FOOTNOTE, Location.ENDNOTE)]
    note_cites.sort(key=lambda c: (c.anchor.container_id, c.anchor.start))

    # Index full citations by the note id they live in (for "supra note N").
    full_by_note: dict[int, ParsedCitation] = {}
    for c in note_cites:
        if _is_full(c):
            full_by_note.setdefault(c.anchor.container_id, c)

    last_full: Optional[ParsedCitation] = None
    for c in note_cites:
        if c.ctype is CitationType.SHORT_FORM:
            sm = _SUPRA_NOTE.search(c.raw_text)
            if sm:
                target = full_by_note.get(int(sm.group(1)))
                if target:
                    _copy_fields(c, target)
            elif _IBID.search(c.raw_text) and last_full is not None:
                _copy_fields(c, last_full)
            # op. cit. / loc. cit. / bare supra -> fall back to last_full.
            elif last_full is not None:
                _copy_fields(c, last_full)
        elif _is_full(c):
            last_full = c
    return citations
