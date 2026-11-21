import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import figfont


def test_fit_clears_collisions():
    fig = plt.figure(figsize=(8, 6))
    grid = fig.add_gridspec(2, 2, hspace=0.25, wspace=0.2)
    for k in range(4):
        ax = fig.add_subplot(grid[k // 2, k % 2])
        bar = fig.colorbar(ax.imshow(np.random.rand(4, 4)), ax=ax)
        bar.set_label("Colour bar label (units)")
        ax.set_ylabel("Hourly eHDD (W m$^{-2}$)")
        box = ax.get_position()
        letter = fig.text(box.x0 - 0.02, box.y1 + 0.01, "abcd"[k], fontweight="bold")
        letter._panel = {"axis": ax, "kind": "letter", "dx": -0.02, "dy": 0.01}
    for text in fig.findobj(matplotlib.text.Text):
        text.set_fontsize(text.get_fontsize() * 1.3)
    assert figfont.overlaps(fig)
    assert figfont.fit(fig, quiet=True) == 0


def test_tilts_crowded_two_line_ticks():
    fig, ax = plt.subplots(figsize=(3, 3))
    ax.set_xticks([1, 2, 3, 4], ["1\n(90)", "2\n(1,214)", "3\n(776)", "4\n(256)"], fontsize=16)
    assert figfont.fit(fig, quiet=True) == 0
    assert ax.get_xticklabels()[1].get_text() == "2 (1,214)"


def test_suggest_size_shrinks_small_panels():
    big, ax = plt.subplots(figsize=(6, 4))
    ax.set_xlabel("label", fontsize=8)
    small, axes = plt.subplots(1, 4, figsize=(5, 1.5))
    for a in axes:
        a.set_xlabel("label", fontsize=8)
    assert figfont.suggest_size(big) == 8.0
    assert figfont.suggest_size(small) == 6.0
