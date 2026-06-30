"""Render a bibliography from CSL-JSON items in a chosen CSL style.

Preferred path: citeproc-py + a real .csl style file (full APA/Chicago/MLA
fidelity). Style files are discovered from, in order:
  1. the bundled ./styles directory (drop .csl files there), then
  2. the `citeproc-py-styles` package, if installed.

If citeproc or a style file is unavailable, we degrade gracefully to a built-in
author-date formatter so the tool still produces *something* offline. The API
reports which engine was used so the UI can warn about reduced fidelity.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

STYLES_DIR = Path(__file__).resolve().parent.parent / "styles"
_FALLBACK_STYLES = ["apa", "chicago-author-date", "mla", "harvard1", "ieee"]


# ----------------------------------------------------------------------------
# Style discovery
# ----------------------------------------------------------------------------
def _bundled_style_path(style: str) -> Optional[Path]:
    p = STYLES_DIR / f"{style}.csl"
    return p if p.exists() else None


def _package_style_path(style: str) -> Optional[str]:
    try:
        from citeproc_styles import get_style_filepath
        return get_style_filepath(style)
    except Exception:
        return None


def list_styles() -> list[str]:
    found = set(_FALLBACK_STYLES)
    if STYLES_DIR.exists():
        found.update(p.stem for p in STYLES_DIR.glob("*.csl"))
    return sorted(found)


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------
def _render_citeproc(items: list[dict[str, Any]], keys: list[str],
                     style_path: str) -> Optional[list[str]]:
    try:
        from citeproc import (CitationStylesStyle, CitationStylesBibliography,
                              Citation, CitationItem, formatter)
        from citeproc.source.json import CiteProcJSON
    except Exception:
        return None

    try:
        bib_source = CiteProcJSON(items)
        style = CitationStylesStyle(style_path, validate=False)
        bib = CitationStylesBibliography(style, bib_source, formatter.plain)
        for key in keys:
            bib.register(Citation([CitationItem(key)]))
        bib.sort()
        return ["".join(entry) if isinstance(entry, (list, tuple)) else str(entry)
                for entry in bib.bibliography()]
    except Exception:
        return None


def _fmt_authors(item: dict[str, Any]) -> str:
    names = []
    for a in item.get("author", []):
        fam = a.get("family") or a.get("literal") or ""
        given = a.get("given", "")
        initials = " ".join(f"{p[0]}." for p in given.split()) if given else ""
        names.append(f"{fam}, {initials}".strip().rstrip(","))
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " & " + names[-1]


def _fallback_entry(item: dict[str, Any]) -> str:
    from .matcher import _item_year  # reuse year extraction
    authors = _fmt_authors(item)
    year = _item_year(item) or "n.d."
    title = (item.get("title") or "").strip()
    container = (item.get("container-title") or item.get("publisher") or "").strip()
    pieces = []
    if authors:
        pieces.append(f"{authors}")
    pieces.append(f"({year}).")
    if title:
        pieces.append(f"{title}.")
    if container:
        pieces.append(f"{container}.")
    return " ".join(pieces)


def render_bibliography(items: list[dict[str, Any]], keys: list[str],
                        style: str) -> tuple[list[str], str]:
    """Return (entries, engine) where engine is 'citeproc' or 'fallback'."""
    if not keys:
        return [], "fallback"

    style_path = _bundled_style_path(style)
    style_path = str(style_path) if style_path else _package_style_path(style)

    if style_path:
        entries = _render_citeproc(items, keys, style_path)
        if entries is not None:
            return entries, "citeproc"

    # Fallback: author-date, sorted by author then year.
    by_key = {str(it.get("id") or it.get("key")): it for it in items}
    chosen = [by_key[k] for k in keys if k in by_key]
    chosen.sort(key=lambda it: _fallback_entry(it).lower())
    return [_fallback_entry(it) for it in chosen], "fallback"
