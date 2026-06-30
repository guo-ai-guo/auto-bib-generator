from app.extractor import extract_from_container, parse_surnames
from app.models import CitationType
from tests.fixtures import body, footnote


def _types(cites):
    return [c.ctype for c in cites]


def test_parenthetical_single():
    cites = extract_from_container(body("As shown (Smith, 2020), cats learn."))
    assert len(cites) == 1
    c = cites[0]
    assert c.ctype is CitationType.AUTHOR_DATE
    assert c.authors == ["Smith"]
    assert c.year == "2020"


def test_parenthetical_two_authors_and_pages():
    cites = extract_from_container(body("(Smith & Jones, 2019, p. 14)"))
    assert len(cites) == 1
    c = cites[0]
    assert c.authors == ["Smith", "Jones"]
    assert c.year == "2019"
    assert c.pages == "14"


def test_multi_citation_group_splits():
    cites = extract_from_container(body("(Smith 2020; Doe 2018)"))
    years = sorted(c.year for c in cites)
    assert years == ["2018", "2020"]


def test_narrative():
    cites = extract_from_container(body("Smith et al. (2018) argue that..."))
    assert len(cites) == 1
    assert cites[0].authors == ["Smith"]
    assert cites[0].year == "2018"


def test_numbered_detected():
    cites = extract_from_container(body("Prior work [12] showed this."))
    assert any(c.ctype is CitationType.NUMBERED for c in cites)


def test_footnote_full_citation():
    note = footnote("Smith, John. Deep learning for cats. Journal of Feline AI, 2020.")
    cites = extract_from_container(note)
    assert any(c.ctype is CitationType.FOOTNOTE_FULL for c in cites)
    full = [c for c in cites if c.ctype is CitationType.FOOTNOTE_FULL][0]
    assert "Smith" in full.authors
    assert full.year == "2020"


def test_short_form_detected():
    cites = extract_from_container(footnote("Ibid., p. 22."))
    assert any(c.ctype is CitationType.SHORT_FORM for c in cites)


def test_parse_surnames():
    assert parse_surnames("Smith & Jones") == ["Smith", "Jones"]
    assert parse_surnames("Smith et al.") == ["Smith"]
    assert parse_surnames("van der Berg and Smith") == ["Berg", "Smith"]
