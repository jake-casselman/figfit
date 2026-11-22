import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pymupdf
import pytest

from figfont import paper_figures
from figfont.papers import _groups


def _plot(path, fontsize=8, as_image=False):
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1, 2], [0, 1, 0])
    ax.set_xlabel("Year", fontsize=fontsize)
    ax.set_ylabel("Demand", fontsize=fontsize)
    ax.tick_params(labelsize=fontsize - 1)
    fig.savefig(path, dpi=200 if as_image else None)
    plt.close(fig)


def _paper(tmp_path, figure, caption="Fig. 1 What the figure shows, in the paper's caption font."):
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=500)
    page.insert_textbox(pymupdf.Rect(56, 30, 344, 120), "Body text of the paper. " * 12, fontname="tiro", fontsize=10)
    box = pymupdf.Rect(56, 130, 344, 346)
    if str(figure).endswith(".png"):
        page.insert_image(box, filename=str(figure))
    else:
        page.show_pdf_page(box, pymupdf.open(figure), 0)
    if caption:
        page.insert_textbox(pymupdf.Rect(56, 352, 344, 380), caption, fontname="tibo", fontsize=9)
    doc.save(tmp_path / "paper.pdf")
    return tmp_path / "paper.pdf"


def test_a_figure_with_stored_text_gives_its_sizes_as_printed(tmp_path):
    _plot(tmp_path / "figure.pdf")
    found = paper_figures(_paper(tmp_path, tmp_path / "figure.pdf"))
    assert found["pages"] == 1 and len(found["figures"]) == 1 and not found["no_text"]
    figure = found["figures"][0]
    assert figure["page"] == 1 and not figure["image"]
    # drawn 4 in wide and placed 4 in wide, so the sizes are the ones it was drawn with
    assert sorted(set(round(s, 1) for s in figure["sizes"])) == [7.0, 8.0]
    assert 3.0 < figure["width_in"] < 4.2    # the box is found on a 3 pt grid
    assert found["body_pt"] == 10.0 and found["caption_pt"] == 9.0
    assert round(found["page_width_in"], 2) == round(400 / 72, 2)


def test_the_caption_is_never_figure_text(tmp_path):
    _plot(tmp_path / "figure.pdf")
    sizes = paper_figures(_paper(tmp_path, tmp_path / "figure.pdf"))["figures"][0]["sizes"]
    assert 9.0 not in [round(s, 1) for s in sizes]


def test_a_figure_saved_as_an_image_is_listed_without_text(tmp_path):
    _plot(tmp_path / "figure.png", as_image=True)
    found = paper_figures(_paper(tmp_path, tmp_path / "figure.png"))
    assert not found["figures"]
    assert len(found["no_text"]) == 1 and found["no_text"][0]["image"]


def test_a_page_without_a_caption_has_no_figures(tmp_path):
    _plot(tmp_path / "figure.pdf")
    found = paper_figures(_paper(tmp_path, tmp_path / "figure.pdf", caption=""))
    assert not found["figures"] and not found["no_text"]


def test_a_book_is_refused(tmp_path):
    doc = pymupdf.open()
    for _ in range(5):
        doc.new_page()
    doc.save(tmp_path / "long.pdf")
    with pytest.raises(ValueError):
        paper_figures(tmp_path / "long.pdf", max_pages=4)


def test_touching_cells_form_one_group():
    grid = np.array([[1, 1, 0, 0],
                     [0, 0, 1, 0],     # touches the first group at a corner
                     [0, 0, 0, 0],
                     [1, 0, 0, 1]], bool)
    labels = _groups(grid)
    assert labels[0, 0] == labels[0, 1] == labels[1, 2] != 0
    assert len({labels[0, 0], labels[3, 0], labels[3, 3]}) == 3
    assert labels[2].sum() == 0
