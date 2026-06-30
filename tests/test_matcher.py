from app.extractor import extract_from_container
from app.matcher import match_all
from app.models import MatchStatus
from tests.fixtures import body, library


def _match(text):
    cites = extract_from_container(body(text))
    results, _ = match_all(cites, library())
    return cites, results


def test_confident_single_match():
    cites, results = _match("(Doe, 2018)")
    r = results[cites[0].id]
    assert r.status is MatchStatus.CONFIDENT
    assert r.chosen_key == "doe2018"


def test_ambiguous_same_author_year():
    # Two Smith 2020 items in the library -> must go to review, not auto.
    cites, results = _match("(Smith, 2020)")
    r = results[cites[0].id]
    assert r.status is MatchStatus.AMBIGUOUS
    assert {c.item_key for c in r.candidates} >= {"smith2020", "smith2020b"}
    assert r.chosen_key is None


def test_title_disambiguates_to_confident():
    # Footnote-style with a title should pin down one of the two Smith 2020s.
    from tests.fixtures import footnote
    cites = extract_from_container(
        footnote('Smith, John. "Reinforcement learning for dogs." Journal, 2020.'))
    results, _ = match_all(cites, library())
    statuses = {results[c.id].status for c in cites}
    assert MatchStatus.CONFIDENT in statuses


def test_no_match():
    cites, results = _match("(Nonexistent, 1999)")
    assert results[cites[0].id].status is MatchStatus.NONE


def test_numbered_is_none():
    cites, results = _match("Prior work [3] showed this.")
    numbered = [c for c in cites if c.raw_text == "[3]"][0]
    assert results[numbered.id].status is MatchStatus.NONE
