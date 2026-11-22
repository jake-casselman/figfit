import pytest

import figfont
from figfont import cli
from figfont.measure import Result


def test_the_reference_for_all_papers_is_in_order():
    ref = figfont.reference()
    low, high = ref["paper_medians_p25_p75"]
    wide_low, wide_high = ref["paper_medians_p10_p90"]
    assert ref["papers"] >= 1000
    assert wide_low <= low <= ref["median_pt"] <= high <= wide_high
    assert 4 < ref["median_pt"] < 10


def test_every_journal_and_field_has_the_same_numbers():
    assert len(figfont.journals()) >= 20 and len(figfont.fields()) >= 3
    for name in figfont.journals():
        entry = figfont.reference(name)
        assert entry["papers"] >= 10 and entry["field"] in figfont.fields()
        assert entry["paper_medians_p25_p75"][0] <= entry["median_pt"] <= entry["paper_medians_p25_p75"][1]
    for name in figfont.fields():
        assert figfont.reference(field=name)["papers"] >= 10
    assert sum(figfont.reference(field=name)["papers"] for name in figfont.fields()) <= figfont.reference()["papers"]


def test_a_journal_without_an_entry_falls_back_to_all_papers():
    assert figfont.reference("Journal of Things Nobody Measured") == figfont.reference()


def test_an_unknown_field_is_an_error():
    with pytest.raises(KeyError):
        figfont.reference(field="Alchemy")


def test_verdict_words():
    low, high = figfont.reference()["paper_medians_p25_p75"]
    middle = (low + high) / 2
    assert figfont.verdict(Result("f", "text", [middle] * 10))["verdict"] == "ok"
    assert figfont.verdict(Result("f", "text", [low - 1] * 10))["verdict"] == "small"
    assert figfont.verdict(Result("f", "text", [high + 1] * 10))["verdict"] == "large"
    assert figfont.verdict(Result("f", "text", []))["verdict"] == "no text found"
    # a tenth of the text under the floor is "small", whatever the median
    assert figfont.verdict(Result("f", "text", [middle] * 8 + [4.0] * 2), smallest_ok=6.0)["verdict"] == "small"


def test_verdict_against_a_journal_and_a_field():
    journal, field = figfont.journals()[0], figfont.fields()[0]
    result = Result("f", "text", [7.0] * 10)
    assert figfont.verdict(result, journal)["reference_median_pt"] == figfont.reference(journal)["median_pt"]
    assert figfont.verdict(result, field=field)["reference_median_pt"] == figfont.reference(field=field)["median_pt"]


def test_the_command_line_takes_a_field(capsys):
    field = figfont.fields()[0]
    assert cli.main(["paper", "docs/examples/paper.pdf", "--field", field]) == 0
    out = capsys.readouterr().out
    assert f"median {figfont.reference(field=field)['median_pt']} pt" in out and "paper.pdf" in out
