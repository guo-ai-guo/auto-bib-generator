"""Shared test fixtures: a small CSL-JSON library and helpers."""
from __future__ import annotations

from app.docx_parser import Container
from app.models import Anchor, CitationType, Location, ParsedCitation


def library() -> list[dict]:
    return [
        {"id": "smith2020", "type": "article-journal",
         "title": "Deep learning for cats",
         "author": [{"family": "Smith", "given": "John"}],
         "issued": {"date-parts": [[2020]]},
         "container-title": "Journal of Feline AI"},
        {"id": "smithjones2019", "type": "book",
         "title": "A history of dogs",
         "author": [{"family": "Smith", "given": "Jane"},
                    {"family": "Jones", "given": "Bob"}],
         "issued": {"date-parts": [[2019]]},
         "publisher": "Academic Press"},
        {"id": "smith2020b", "type": "article-journal",
         "title": "Reinforcement learning for dogs",
         "author": [{"family": "Smith", "given": "John"}],
         "issued": {"date-parts": [[2020]]},
         "container-title": "Journal of Canine AI"},
        {"id": "doe2018", "type": "chapter",
         "title": "Vision transformers",
         "author": [{"family": "Doe", "given": "Alice"}],
         "issued": {"date-parts": [[2018]]}},
    ]


def body(text: str, idx: int = 0) -> Container:
    return Container(Location.BODY, idx, text)


def footnote(text: str, nid: int = 1) -> Container:
    return Container(Location.FOOTNOTE, nid, text)
