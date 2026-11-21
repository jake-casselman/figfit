from figfont import measure


def test_upright_lines_are_kept_and_text_on_its_side_is_not():
    assert measure._upright(120, 20, "Month of the year")   # one line of text
    assert measure._upright(30, 20, "20")                   # a short number
    assert not measure._upright(20, 120, "Hour of day")     # written up the page
    assert not measure._upright(90, 60, "Detached")         # tilted 30 degrees


def _word(angle):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (240, 240), "white")
    ImageDraw.Draw(image).text((60, 100), "Semi", font=ImageFont.load_default(size=48), fill="black")
    image = image.rotate(angle, fillcolor="white")
    grey = image.convert("L").point(lambda v: 255 if v < 128 else 0)
    return image, grey.getbbox()


def test_short_tilted_word_is_not_level():
    image, box = _word(0)
    assert measure._level(image, box)
    image, box = _word(30)
    assert measure._upright(box[2] - box[0], box[3] - box[1], "Semi")  # the length test alone lets it through
    assert not measure._level(image, box)


def test_boxes_that_share_most_of_the_smaller_one():
    assert measure._shared((0, 0, 10, 10), (2, 2, 6, 6)) == 1.0
    assert measure._shared((0, 0, 10, 10), (10, 0, 20, 10)) == 0.0


def test_figure_text_in_a_paper_is_counted_and_body_text_is_not(tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pymupdf
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xlabel("Year", fontsize=8)
    ax.set_ylabel("Demand", fontsize=8)   # at the left edge of the figure
    ax.set_title("a", loc="left", fontsize=8, pad=0)
    ax.tick_params(labelsize=7)
    fig.subplots_adjust(top=0.96)          # the title reaches the top edge
    fig.savefig(tmp_path / "figure.pdf")
    plt.close(fig)
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=500)
    page.insert_textbox(pymupdf.Rect(56, 30, 344, 120), "Body text of the paper. " * 12, fontname="tiro", fontsize=10)
    page.show_pdf_page(pymupdf.Rect(56, 130, 344, 346), pymupdf.open(tmp_path / "figure.pdf"), 0)
    page.insert_textbox(pymupdf.Rect(56, 352, 344, 380), "Fig. 1 A caption.", fontname="tibo", fontsize=9)
    doc.save(tmp_path / "paper.pdf")
    result = measure.pdf_figure_text(str(tmp_path / "paper.pdf"))
    assert result.n == 7                   # four tick numbers, two axis labels and the panel letter
    assert sorted(set(result.sizes)) == [7.0, 8.0]
