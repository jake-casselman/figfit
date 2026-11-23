import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest

from figfit import colour
from figfit.cli import main


def test_simulation_keeps_greys_and_merges_red_and_green():
    for kind in colour.KINDS:
        assert colour.difference((0.5, 0.5, 0.5), colour.simulate((0.5, 0.5, 0.5), kind)) < 1
    red, green, blue = (0.84, 0.15, 0.16), (0.17, 0.63, 0.17), (0.12, 0.47, 0.71)
    assert colour.difference(red, green) > 30
    assert colour.worst(red, green)[1] < 8          # red and green: hard for deutan readers
    assert colour.worst(blue, (1.0, 0.5, 0.05))[1] > 15   # blue and orange: fine for everyone


@pytest.mark.parametrize("name, bad", [("viridis", False), ("cividis", False), ("RdBu_r", False), ("PuOr", False),
                                       ("Blues", False), ("jet", True), ("turbo", True), ("RdYlGn", True)])
def test_colour_maps(name, bad):
    assert bool(colour.colormap_problems(name)) == bad


def test_figure_pairs_and_line_style_note():
    fig, (a, b) = plt.subplots(1, 2)
    x = np.arange(10)
    a.plot(x, x, color="tab:red", label="obs")
    a.plot(x, x + 1, color="tab:green", label="model")
    a.plot(x, x + 2, color="tab:purple", label="other")
    b.plot(x, x, color="tab:red")
    b.plot(x, x + 1, "--", color="tab:green")
    b.pcolormesh(np.random.default_rng(0).random((4, 4)), cmap="jet")
    problems = colour.colour_problems(fig)
    serious = [p for p in problems if p.serious]
    notes = [p for p in problems if not p.serious]
    assert any("'obs' and 'model'" in p.what and p.kind == "deutan" for p in serious)
    assert not any("'other'" in p.what for p in problems)
    assert len(notes) == 1 and notes[0].what.startswith("panel b")
    assert any("jet" in p.what for p in serious)
    plt.close(fig)


def test_files_and_sheet(tmp_path, capsys):
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.bar([0, 1], [1, 2], color=["tab:red", "tab:green"])
    bad = tmp_path / "bad.png"
    fig.savefig(bad)
    ax.cla()
    ax.bar([0, 1], [1, 2], color=["tab:blue", "tab:orange"])
    good = tmp_path / "good.png"
    fig.savefig(good)
    plt.close(fig)
    assert colour.image_problems(bad) and not colour.image_problems(good)
    assert main(["colours", str(good)]) == 0
    assert main(["colours", str(bad), "--sheet"]) == 1
    out = capsys.readouterr().out
    assert "look alike" in out and (tmp_path / "bad.colourblind.png").exists()
