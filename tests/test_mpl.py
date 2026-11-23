import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import figfit.mpl
from figfit import scale


def test_every_kind_of_text_gets_its_printed_size():
    fig, ax = plt.subplots(figsize=(10, 4))
    line, = ax.plot([0, 1], [0, 1], label="curve")
    ax.set_title("centre")
    ax.set_title("left", loc="left")
    ax.set_xlabel("x")
    note = ax.text(0.5, 0.5, "note")
    ax.legend(title="key")
    shared = fig.legend(handles=[line], loc="upper right")
    letter = fig.text(0.01, 0.95, "a")
    figfit.mpl.set_printed_fonts(fig, 5.0, {"tick": 6, "title": 9})
    printed = lambda text: scale.printed_pt(text.get_fontsize(), 10, 5.0)
    near = lambda text, points: abs(printed(text) - points) < 1e-9
    assert near(ax.get_xticklabels()[0], 6)
    assert near(ax.title, 9) and near(ax._left_title, 9)
    assert near(ax.xaxis.label, 8) and near(note, 8) and near(letter, 8)
    assert near(ax.get_legend().get_texts()[0], 8) and near(ax.get_legend().get_title(), 8)
    assert near(shared.get_texts()[0], 8)


def test_scale_fonts_multiplies_everything():
    fig, ax = plt.subplots()
    ax.set_xlabel("x", fontsize=10)
    figfit.mpl.scale_fonts(fig, 1.5)
    assert ax.xaxis.label.get_fontsize() == 15
