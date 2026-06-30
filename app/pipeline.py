"""Orchestrate the end-to-end flow.

  parse -> extract -> resolve short forms -> match            (run_parse_and_match)
  apply user resolutions                                      (apply_resolutions)
  render bibliography + write output docx with flags          (generate)
"""
from __future__ import annotations

from typing import Any

from .docx_parser import parse_containers
from .docx_writer import Flag, write_output
from .extractor import extract_all
from .matcher import match_all
from .models import (CitationType, Job, JobState, Location, MatchStatus,
                     ParsedCitation)
from .renderer import render_bibliography
from .shortforms import resolve

# Per-job library cache: job_id -> {item_key: csl-json item}
_libraries: dict[str, dict[str, Any]] = {}


def run_parse_and_match(job: Job, items: list[dict[str, Any]]) -> None:
    containers = parse_containers(job.input_path)
    citations = extract_all(containers)
    resolve(citations)
    results, index = match_all(citations, items)

    job.citations = citations
    job.results = results
    _libraries[job.id] = {index.item_key(it): it for it in index.items}
    job.state = JobState.MATCHED


def apply_resolutions(job: Job, resolutions: dict[str, str | None]) -> None:
    """resolutions: citation_id -> chosen item_key (or None to skip)."""
    for cid, key in resolutions.items():
        res = job.results.get(cid)
        if res is None:
            continue
        if key:
            res.chosen_key = key
        else:
            res.chosen_key = None


def _citation_index(job: Job) -> dict[str, ParsedCitation]:
    return {c.id: c for c in job.citations}


def _flag_message(cite: ParsedCitation, res) -> str | None:
    if res.status is MatchStatus.NONE:
        if cite.ctype is CitationType.NUMBERED:
            return (f'Numbered citation "{cite.raw_text}" cannot be matched '
                    f"automatically (no author/year in the marker).")
        return f'No Zotero match found for: "{cite.raw_text}"'
    if res.status is MatchStatus.AMBIGUOUS and not res.chosen_key:
        opts = "; ".join(c.display for c in res.candidates)
        return (f'Ambiguous citation "{cite.raw_text}" — '
                f"{len(res.candidates)} possible matches: {opts}")
    return None


def generate(job: Job) -> dict:
    job.state = JobState.GENERATING
    library = _libraries.get(job.id, {})
    cite_by_id = _citation_index(job)

    # Chosen references -> bibliography.
    chosen_keys: list[str] = []
    seen: set[str] = set()
    for res in job.results.values():
        if res.chosen_key and res.chosen_key not in seen:
            seen.add(res.chosen_key)
            chosen_keys.append(res.chosen_key)

    items = list(library.values())
    entries, engine = render_bibliography(items, chosen_keys, job.style)

    # Flags for unmatched / unresolved citations.
    flags: list[Flag] = []
    for cid, res in job.results.items():
        cite = cite_by_id.get(cid)
        if cite is None:
            continue
        msg = _flag_message(cite, res)
        if msg:
            flags.append(Flag(cite.anchor.location, cite.anchor.container_id,
                              cite.anchor.start, cite.anchor.end, msg))

    stats = write_output(job.input_path, job.output_path,
                         bib_entries=entries, flags=flags, engine=engine)
    job.state = JobState.DONE
    return stats
