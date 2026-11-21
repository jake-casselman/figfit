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
        ax.set_ylabel("Hourly demand (W m$^{-2}$)")
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
    ax.set_ylabel("People\n(thousands per unit demand)", fontsize=20, labelpad=0)
    ax.tick_params(labelsize=20)
    letter = fig.text(0.02, 0.9, "e", fontsize=20, fontweight="bold")
    letter._panel = {"axis": ax, "kind": "letter", "dx": -0.1, "dy": 0.02}
    figfont.fit(fig, quiet=True)
    fig.canvas.draw()
    assert ax.yaxis.label.get_text() == "People (thousands\nper unit demand)"
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


BOX = dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="darkgray", alpha=0.9)


def _land(ax):
    """A big filled shape on the right (a continent) and specks on the left (islands)."""
    ax.set_xlim(0, 100)
    ax.set_ylim(-50, 50)
    ax.fill([60, 100, 100, 70, 55], [-50, -50, 50, 50, 10], color="tan", edgecolor="black")
    ax.plot([12, 20, 26, 33], [14, 12, 16, 11], "k.", markersize=2)


def _on_drawing(fig, ax, note):
    from figfont import textfit
    fig.canvas.draw()  # a box has no size before the first draw
    pixels = textfit._drawn(fig, list(ax.texts))
    box = note.get_bbox_patch().get_window_extent(fig.canvas.get_renderer())
    grounds = [np.round(np.array(c[:3]) * 255) for c in (fig.get_facecolor(), ax.get_facecolor())]
    return textfit._covered(pixels, box, grounds)


def test_boxed_note_moves_off_the_edge_of_a_shape_and_its_partner_follows():
    fig, ax = plt.subplots(figsize=(8, 4))
    _land(ax)
    north = ax.text(50, 8, "NDJFM", ha="left", va="bottom", bbox=BOX)
    south = ax.text(50, -8, "MJJAS", ha="left", va="top", bbox=BOX)
    assert _on_drawing(fig, ax, north) > 0.02
    assert figfont.fit(fig, quiet=True) == 0
    assert _on_drawing(fig, ax, north) == 0 and _on_drawing(fig, ax, south) == 0
    assert north.get_position()[0] < 50 and north.get_position()[0] == south.get_position()[0]
    assert abs(north.get_position()[1] - 8) < 1e-6 and abs(south.get_position()[1] + 8) < 1e-6
    assert 50 - north.get_position()[0] < 8  # a nudge, not a new place


def test_boxed_note_on_specks_or_clear_of_everything_stays():
    fig, ax = plt.subplots(figsize=(8, 4))
    _land(ax)
    on_specks = ax.text(10, 8, "NDJFM", ha="left", va="bottom", bbox=BOX)
    clear = ax.text(10, -8, "MJJAS", ha="left", va="top", bbox=BOX)
    figfont.fit(fig, quiet=True)
    assert on_specks.get_position() == (10, 8) and clear.get_position() == (10, -8)


def test_boxed_note_written_on_the_data_stays():
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.imshow(np.random.rand(20, 30), extent=(0, 30, 0, 20), aspect="auto")
    note = ax.text(5, 15, "P95 U = 2.34", bbox=BOX)
    figfont.fit(fig, quiet=True)
    assert note.get_position() == (5, 15)


def test_boxed_note_with_no_clear_place_stays_and_is_reported(capsys):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_xlim(0, 100)
    ax.set_ylim(-50, 50)
    for x in range(0, 101, 4):
        ax.plot([x, x + 30], [-50, 50], color="black")  # lines everywhere
    note = ax.text(50, 0, "NDJFM", bbox=BOX)
    figfont.fit(fig, "lines")
    assert note.get_position() == (50, 0)
    assert "TEXT ON DATA lines: 'NDJFM'" in capsys.readouterr().out


def test_shapes_are_found_the_same_without_scipy(monkeypatch):
    import builtins
    from figfont import textfit
    ink = np.zeros((40, 60), bool)
    ink[5:8, 5:8] = True          # a speck
    ink[20:22, 10:50] = True      # a long line
    ink[30:34, 55:60] = True      # small, but runs off the edge
    ink[10, 30] = ink[11, 31] = True  # two pixels joined at a corner
    with_scipy = textfit._things(ink, 12)
    real = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", lambda name, *a, **k: (_ for _ in ()).throw(ImportError(name))
                        if name.startswith("scipy") else real(name, *a, **k))
    without = textfit._things(ink, 12)
    assert (with_scipy == without).all()
    assert without[20, 30] and without[31, 57] and not without[6, 6] and not without[10, 30]


def test_label_running_off_the_figure_goes_onto_two_lines():
    fig, ax = plt.subplots(figsize=(4, 2.6), layout="constrained")
    ax.set_ylabel("Heating degree days per year (degree days)", fontsize=14)
    assert "\n" not in ax.yaxis.label.get_text()
    figfont.fit(fig, quiet=True)
    assert ax.yaxis.label.get_text().count("\n") == 1
    fig.canvas.draw()
    box = ax.yaxis.label.get_window_extent()
    assert box.y0 >= 0 and box.y1 <= fig.bbox.y1


def test_label_longer_than_its_panel_but_on_the_figure_stays():
    fig, ax = plt.subplots(figsize=(6, 4))
    fig.subplots_adjust(left=0.4, right=0.6)
    ax.set_xlabel("A label wider than this narrow panel")
    figfont.fit(fig, quiet=True)
    assert "\n" not in ax.xaxis.label.get_text()


def test_wide_tick_names_tilt_until_they_part():
    fig, ax = plt.subplots(figsize=(2.6, 2.6))
    names = ["Detached", "Semi-detached", "Terraced", "Apartment", "Mobile home", "Other"]
    ax.bar(names, [41, 23, 17, 12, 5, 2])
    ax.tick_params(labelsize=13)
    assert figfont.fit(fig, quiet=True) == 0
    angles = {t.get_rotation() for t in ax.get_xticklabels()}
    assert len(angles) == 1 and angles.pop() > 30  # 30 degrees was not enough here
