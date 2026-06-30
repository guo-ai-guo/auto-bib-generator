from app.extractor import extract_all
from app.shortforms import resolve
from tests.fixtures import footnote


def test_ibid_resolves_to_previous_full():
    containers = [
        footnote("Smith, John. Deep learning for cats. Journal, 2020.", 1),
        footnote("Ibid., p. 30.", 2),
    ]
    cites = resolve(extract_all(containers))
    ibid = [c for c in cites if "Ibid" in c.raw_text][0]
    assert ibid.resolved_from is not None
    assert ibid.authors == ["Smith"]
    assert ibid.year == "2020"


def test_supra_note_resolves_to_that_note():
    containers = [
        footnote("Doe, Alice. Vision transformers. Press, 2018.", 5),
        footnote("Smith, John. Cats. Journal, 2020.", 8),
        footnote("Doe, supra note 5, at 12.", 9),
    ]
    cites = resolve(extract_all(containers))
    supra = [c for c in cites if "supra" in c.raw_text.lower()][0]
    assert supra.resolved_from is not None
    assert supra.year == "2018"
    assert supra.authors == ["Doe"]
