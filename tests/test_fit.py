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


def _legend_figure():
    from matplotlib.patches import Patch
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.pcolormesh(np.random.rand(20, 20))  # the panel is full: no empty corner
    ax.legend(handles=[Patch(color=c, label=f"{k}  (N {k * 3})") for k, c in enumerate("rgbk")],
              loc="lower left", title="Zone", frameon=False)
    return fig, ax


def test_legend_on_a_full_panel_goes_under_it():
    fig, ax = _legend_figure()
    assert figfont.fit(fig, quiet=True) == 0
    legend = ax.get_legend()
    fig.canvas.draw()
    assert legend.get_window_extent().y1 < ax.get_window_extent().y0
    assert legend._ncols == 4 and legend.get_title().get_text() == "Zone"


def test_legend_on_data_moves_to_an_empty_corner():
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(range(6), [9, 8, 7, 2, 1, 1], width=1.0, label="bars")
    legend = ax.legend(loc="upper left", frameon=False)
    figfont.fit(fig, quiet=True)
    fig.canvas.draw()
    box, panel = ax.get_legend().get_window_extent(), ax.get_window_extent()
    assert box.x0 > panel.x0 + panel.width / 4 and box.y1 <= panel.y1  # off the tall bars, still inside


def test_label_keeps_clear_of_its_numbers_and_long_label_rewraps():
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.set_ylabel("People\n(thousands per unit eHDD)", fontsize=20, labelpad=0)
    ax.tick_params(labelsize=20)
    letter = fig.text(0.02, 0.9, "e", fontsize=20, fontweight="bold")
    letter._panel = {"axis": ax, "kind": "letter", "dx": -0.1, "dy": 0.02}
    figfont.fit(fig, quiet=True)
    fig.canvas.draw()
    assert ax.yaxis.label.get_text() == "People (thousands\nper unit eHDD)"
    gap = min(t.get_window_extent().x0 for t in ax.get_yticklabels()) - ax.yaxis.label.get_window_extent().x1
    assert gap >= 0.29 * 20 * fig.dpi / 72


def _legend_boxes(fig, ax):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    return ax.get_legend().get_window_extent(renderer), renderer


def test_legend_under_a_panel_stays_between_stacked_panels():
    fig, (upper, lower) = plt.subplots(2, 1, figsize=(6, 6), sharex=True, gridspec_kw={"hspace": 0.2})
    upper.pcolormesh(np.random.rand(12, 12))
    upper.plot([0, 12], [0, 12], label="A long curve label for the test")
    upper.plot([0, 12], [12, 0], label="Another long label for the test")
    upper.legend(loc="upper left")
    lower.plot([0, 12], [0, 1])
    lower.set_title("Lower panel title")
    assert figfont.fit(fig, quiet=True) == 0
    box, renderer = _legend_boxes(fig, upper)
    assert box.y1 <= upper.get_window_extent(renderer).y0
    assert box.y0 >= lower.title.get_window_extent(renderer).y1


def test_legend_may_lie_on_bands_and_grid():
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.axvspan(0, 5, color="red", alpha=0.12)
    ax.axvspan(5, 10, color="green", alpha=0.12)
    ax.grid(True)
    ax.plot([0, 10], [0, 0.2], label="curve")
    ax.set_ylim(0, 1)
    legend = ax.legend(loc="upper left")
    figfont.fit(fig, quiet=True)
    assert ax.get_legend() is legend and legend._loc == 2


def test_legend_text_touching_data_moves_off_it():
    fig, ax = plt.subplots(figsize=(6, 4))
    x = np.linspace(-40, 20, 200)
    ax.fill_between(x, -10 * np.exp(-((x + 5) / 6.0) ** 2), 0.5, color="0.8", label="5th to 95th percentile")
    ax.plot(x, 0 * x, label="median")
    ax.set_ylim(-11, 2)
    ax.legend(loc="lower right", frameon=False)
    from figfont import textfit
    assert figfont.fit(fig, quiet=True) == 0
    pixels = textfit._drawn(fig)
    renderer = fig.canvas.get_renderer()
    grounds = [np.round(np.array(c[:3]) * 255) for c in (fig.get_facecolor(), ax.get_facecolor())]
    for text in ax.get_legend().get_texts():
        assert textfit._covered(pixels, text.get_window_extent(renderer), grounds) <= textfit.TOUCH


def test_frameless_legend_moves_off_a_reference_line():
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot([0, 10], [0, 0.2], label="A curve with a long label")
    ax.axvline(8.5, linestyle=":")
    ax.set_ylim(0, 1)
    ax.legend(loc="upper right", frameon=False)
    from figfont import textfit
    assert figfont.fit(fig, quiet=True) == 0
    pixels = textfit._drawn(fig)
    renderer = fig.canvas.get_renderer()
    grounds = [np.round(np.array(c[:3]) * 255) for c in (fig.get_facecolor(), ax.get_facecolor())]
    for text in ax.get_legend().get_texts():
        assert textfit._covered(pixels, text.get_window_extent(renderer), grounds) <= textfit.TOUCH
