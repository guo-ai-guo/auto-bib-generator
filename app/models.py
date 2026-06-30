"""Domain models shared across the pipeline.

These are plain dataclasses (with `to_dict` helpers) so they can be passed to
the parser/matcher internally and serialized to JSON for the API without
coupling the core logic to Pydantic.
"""
from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


class CitationType(str, enum.Enum):
    AUTHOR_DATE = "author_date"      # (Smith 2020), (Smith, 2020, p. 14)
    NUMBERED = "numbered"            # [1], superscript ¹
    FOOTNOTE_FULL = "footnote_full"  # full bibliographic citation in a note
    SHORT_FORM = "short_form"        # ibid., supra note 12, id.
    UNKNOWN = "unknown"


class MatchStatus(str, enum.Enum):
    CONFIDENT = "confident"   # exactly one strong candidate -> auto-include
    AMBIGUOUS = "ambiguous"   # multiple plausible candidates -> user picks
    NONE = "none"             # no candidate above the floor -> flag


class Location(str, enum.Enum):
    BODY = "body"
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"


@dataclass
class Anchor:
    """Where a citation lives in the document, precise enough to attach a
    Word comment back to the same run range later."""
    location: Location
    # For body text: index into the document's paragraph list.
    # For notes: the note's numeric id (w:id in footnotes.xml / endnotes.xml).
    container_id: int
    # Character offsets within the *concatenated text* of the container.
    start: int
    end: int

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["location"] = self.location.value
        return d


@dataclass
class ParsedCitation:
    """A raw citation span pulled out of the document."""
    id: str
    raw_text: str
    ctype: CitationType
    anchor: Anchor
    # Structured fields parsed from raw_text (best effort).
    authors: list[str] = field(default_factory=list)  # surnames
    year: Optional[str] = None
    title: Optional[str] = None
    pages: Optional[str] = None
    # If this was a short form (ibid./supra), the id of the citation it
    # resolves to once short-form resolution has run.
    resolved_from: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ctype"] = self.ctype.value
        d["anchor"] = self.anchor.to_dict()
        return d


@dataclass
class Candidate:
    """A Zotero item proposed as a match, with a score in [0, 1]."""
    item_key: str
    score: float
    csl: dict[str, Any]              # the CSL-JSON item
    display: str                     # short human-readable label for the UI

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_key": self.item_key,
            "score": round(self.score, 3),
            "display": self.display,
        }


@dataclass
class MatchResult:
    citation_id: str
    status: MatchStatus
    candidates: list[Candidate] = field(default_factory=list)
    # Item key chosen for inclusion: auto-set for CONFIDENT, set by the user
    # for AMBIGUOUS via the resolutions endpoint. None means "skip / flag".
    chosen_key: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "status": self.status.value,
            "candidates": [c.to_dict() for c in self.candidates],
            "chosen_key": self.chosen_key,
        }


class JobState(str, enum.Enum):
    PARSING = "parsing"
    MATCHED = "matched"        # parsing+matching done, awaiting resolutions
    GENERATING = "generating"
    DONE = "done"
    ERROR = "error"


@dataclass
class Job:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: JobState = JobState.PARSING
    error: Optional[str] = None
    style: str = "apa"
    collection: Optional[str] = None
    input_path: Optional[str] = None
    output_path: Optional[str] = None
    citations: list[ParsedCitation] = field(default_factory=list)
    results: dict[str, MatchResult] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        buckets = {"confident": 0, "ambiguous": 0, "none": 0}
        for r in self.results.values():
            buckets[r.status.value] += 1
        return buckets

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state.value,
            "error": self.error,
            "style": self.style,
            "collection": self.collection,
            "summary": self.summary(),
            "citations": [c.to_dict() for c in self.citations],
            "results": {k: v.to_dict() for k, v in self.results.items()},
        }
