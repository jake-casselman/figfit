from figfont import scale


def test_round_trip():
    drawn = scale.drawn_pt_for(8, drawn_width=26.3, printed_width=5.15)
    assert abs(scale.printed_pt(drawn, 26.3, 5.15) - 8) < 1e-9


def test_ehdd_fig1_old_labels_print_near_3pt():
    assert 2.8 < scale.printed_pt(15, 26.3, 5.15) < 3.1


def test_panel_width():
    w = scale.panel_width_for(5.15, columns=2, gap=0.1, margin=0.05)
    assert abs(scale.stitched_width(w, 2, 0.1, 0.05) - 5.15) < 1e-9


def test_latex_textwidth():
    assert abs(scale.latex_length_in(372) - 5.147) < 0.001
