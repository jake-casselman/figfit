"""The quick start in the README: draw a figure wide, set the sizes it prints at, clear the collisions.

    python docs/examples/quickstart.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import figfont
from figfont.mpl import set_printed_fonts

PAGE = 5.15  # the width the figure gets on the page, inches

rng = np.random.default_rng(0)
fig, (a, b, c) = plt.subplots(1, 3, figsize=(13, 4.3), layout="constrained")
years = np.arange(1980, 2021)
a.plot(years, 3000 - 9 * (years - 1980) + rng.normal(0, 60, years.size), label="Observed")
a.plot(years, 2960 - 8 * (years - 1980), label="Modelled")
a.set_xlabel("Year")
a.set_ylabel("Heating degree days per year (°C day)")
a.legend(loc="lower left")
b.bar(["Detached", "Semi", "Terrace", "Flat", "Mobile", "Other"], [41, 23, 17, 12, 5, 2], width=0.7)
b.set_ylabel("Share of homes (%)")
month, hour = np.meshgrid(np.arange(12), np.arange(24))
demand = (1.2 + np.cos(2 * np.pi * month / 12)) * (1.3 + np.cos(2 * np.pi * (hour - 6) / 24))
image = c.imshow(demand, aspect="auto", cmap="Blues", origin="lower")
fig.colorbar(image, ax=c).set_label("Heating demand (kWh per hour)")
c.set_xlabel("Month of the year")
c.set_ylabel("Hour of day")
for letter, ax in zip("abc", (a, b, c)):
    ax.set_title(letter, loc="left", fontweight="bold")

print("as drawn, 10 pt prints at", round(figfont.printed_pt(10, 13, PAGE), 2), "pt")
set_printed_fonts(fig, PAGE)         # ticks 7 pt, everything else 8 pt, as printed
figfont.fit(fig, "fig01")            # clear the collisions the bigger text made
fig.savefig("fig01.pdf")
print(figfont.verdict(figfont.figure("fig01.pdf", PAGE)))
